import json
import os
import pytest
from config import config_manager as manager
from src.security import protect, unprotect

def synthetic_config():
    return {"utenze": [{"descrizione": "Demo", "codice": "DEMO123"}],
            "credenziali": {"SPID_SIELTE": {"username": "utente-sintetico", "password": "segreto-sintetico"}},
            "impostazioni": {"output_dir": "./output"}}

@pytest.fixture
def fake_crypto(monkeypatch):
    monkeypatch.setattr(manager, "protect", lambda value: b"encrypted:" + value[::-1])
    monkeypatch.setattr(manager, "unprotect", lambda value: value[len(b"encrypted:"):][::-1])

def test_plaintext_migration_preserves_credentials_and_removes_json_secrets(tmp_path, fake_crypto):
    path = tmp_path / "config.json"
    config = synthetic_config()
    path.write_text(json.dumps(config), encoding="utf-8")
    manager.salva_config(manager.carica_config(path), path)
    assert "credenziali" not in json.loads(path.read_text())
    assert b"segreto-sintetico" not in (tmp_path / "credentials.bin").read_bytes()
    assert manager.carica_config(path) == config

def test_failed_encryption_preserves_original_plaintext(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    original = json.dumps(synthetic_config())
    path.write_text(original, encoding="utf-8")
    def fail(_):
        raise RuntimeError("Simulazione")
    monkeypatch.setattr(manager, "protect", fail)
    with pytest.raises(RuntimeError):
        manager.salva_config(synthetic_config(), path)
    assert path.read_text() == original
    assert not (tmp_path / "credentials.bin").exists()

def test_empty_credentials_remove_archive(tmp_path, fake_crypto):
    path = tmp_path / "config.json"
    manager.salva_config(synthetic_config(), path)
    updated = synthetic_config()
    updated["credenziali"] = {}
    manager.salva_config(updated, path)
    assert not (tmp_path / "credentials.bin").exists()
    assert manager.carica_config(path)["credenziali"] == {}

def test_verification_failure_does_not_overwrite_json(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(manager, "protect", lambda _: b"invalid")
    monkeypatch.setattr(manager, "unprotect", lambda _: b"wrong")
    with pytest.raises(RuntimeError):
        manager.salva_config(synthetic_config(), path)
    assert path.read_text() == "{}"

@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI")
def test_real_windows_protection_roundtrip():
    payload = b"synthetic-secret-for-dpapi-test"
    encrypted = protect(payload)
    assert payload not in encrypted
    assert unprotect(encrypted) == payload



def test_other_windows_account_keeps_settings_and_preserves_encrypted_archive(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    settings = {"utenze": [{"codice": "DEMO123", "descrizione": "Demo"}],
                "impostazioni": {"output_dir": "./output", "pausa_download": 3}}
    original = json.dumps(settings).encode("utf-8")
    path.write_bytes(original)
    archive = tmp_path / "credentials.bin"
    archive.write_bytes(b"encrypted-on-another-computer")
    def foreign_account(_):
        raise OSError("Synthetic DPAPI failure")
    monkeypatch.setattr(manager, "unprotect", foreign_account)
    # Una semplice lettura non deve modificare alcun file.
    with pytest.raises(manager.CredentialsUnavailableError):
        manager.carica_config(path)
    assert archive.exists() and not list(tmp_path.glob("*.non-utilizzabile-*"))
    loaded, warning = manager.carica_config_avvio(path)
    assert loaded == {**settings, "credenziali": {}}
    assert "Reinserisci le credenziali" in warning
    assert path.read_bytes() == original and not archive.exists()
    backups = list(tmp_path.glob("credentials.bin.non-utilizzabile-*"))
    assert len(backups) == 1 and backups[0].read_bytes() == b"encrypted-on-another-computer"
    manager.salva_config(loaded, path)
    assert backups[0].read_bytes() == b"encrypted-on-another-computer"
    again, warning = manager.carica_config_avvio(path)
    assert again == loaded and warning is None


def test_current_account_opens_normally_without_backups(tmp_path, fake_crypto):
    path = tmp_path / "config.json"
    expected = synthetic_config()
    manager.salva_config(expected, path)
    original = (tmp_path / "credentials.bin").read_bytes()
    loaded, warning = manager.carica_config_avvio(path)
    assert loaded == expected and warning is None
    assert (tmp_path / "credentials.bin").read_bytes() == original
    assert not list(tmp_path.glob("*.non-utilizzabile-*"))


@pytest.mark.parametrize("payload", [b"not-json", b"[]", b'{"SPID_SIELTE":"invalid"}'])
def test_corrupt_credential_payload_can_be_recovered_without_destroying_it(tmp_path, monkeypatch, payload):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    (tmp_path / "credentials.bin").write_bytes(b"damaged-encrypted-archive")
    monkeypatch.setattr(manager, "unprotect", lambda _: payload)
    loaded, warning = manager.carica_config_avvio(path)
    assert loaded["credenziali"] == {} and warning
    assert next(tmp_path.glob("*.non-utilizzabile-*")).read_bytes() == b"damaged-encrypted-archive"


def test_permission_error_reading_credentials_is_not_recovered_as_wrong_account(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    archive = tmp_path / "credentials.bin"
    archive.write_bytes(b"encrypted")
    original_read = type(path).read_bytes
    def locked(p):
        if p == archive:
            raise PermissionError("Synthetic locked file")
        return original_read(p)
    monkeypatch.setattr(type(path), "read_bytes", locked)
    with pytest.raises(PermissionError):
        manager.carica_config_avvio(path)
    assert archive.exists() and not list(tmp_path.glob("*.non-utilizzabile-*"))


def test_failure_to_preserve_foreign_credentials_does_not_overwrite_them(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text("{}", encoding="utf-8")
    archive = tmp_path / "credentials.bin"
    archive.write_bytes(b"foreign-encrypted")
    def fail(_):
        raise OSError("Synthetic DPAPI failure")
    def locked(*_):
        raise PermissionError("Synthetic read-only folder")
    monkeypatch.setattr(manager, "unprotect", fail)
    monkeypatch.setattr(type(path), "rename", locked)
    with pytest.raises(PermissionError):
        manager.carica_config_avvio(path)
    assert archive.read_bytes() == b"foreign-encrypted"
    assert path.read_text() == "{}"


@pytest.mark.parametrize("settings", ["[]", "null", '{"credenziali": []}', "{broken"])
def test_invalid_configuration_is_not_mistaken_for_foreign_credentials(tmp_path, settings):
    path = tmp_path / "config.json"
    path.write_text(settings, encoding="utf-8")
    (tmp_path / "credentials.bin").write_bytes(b"keep")
    with pytest.raises(ValueError):
        manager.carica_config_avvio(path)
    assert (tmp_path / "credentials.bin").read_bytes() == b"keep"
    assert not list(tmp_path.glob("*.non-utilizzabile-*"))


def test_new_computer_can_save_its_own_credentials_and_keep_foreign_backup(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    path.write_text('{"utenze": [], "impostazioni": {}}', encoding="utf-8")
    (tmp_path / "credentials.bin").write_bytes(b"foreign-archive")
    def local_unprotect(value):
        if not value.startswith(b"local:"):
            raise OSError("Foreign account")
        return value[len(b"local:"):][::-1]
    monkeypatch.setattr(manager, "protect", lambda value: b"local:" + value[::-1])
    monkeypatch.setattr(manager, "unprotect", local_unprotect)
    config, warning = manager.carica_config_avvio(path)
    assert warning
    config["credenziali"] = synthetic_config()["credenziali"]
    manager.salva_config(config, path)
    loaded, warning = manager.carica_config_avvio(path)
    assert loaded == config and warning is None
    assert next(tmp_path.glob("*.non-utilizzabile-*")).read_bytes() == b"foreign-archive"
    assert "segreto-sintetico" not in path.read_text()


def test_failed_recovery_restores_original_archive(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    archive = tmp_path / "credentials.bin"
    archive.write_bytes(b"keep-original")
    calls = 0
    def fail_twice(_):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise manager.CredentialsUnavailableError("Foreign account")
        raise OSError("Settings became inaccessible")
    monkeypatch.setattr(manager, "carica_config", fail_twice)
    with pytest.raises(OSError):
        manager.carica_config_avvio(path)
    assert archive.read_bytes() == b"keep-original"
    assert not list(tmp_path.glob("*.non-utilizzabile-*"))


def test_frozen_settings_are_outside_installation(monkeypatch, tmp_path):
    monkeypatch.setattr(manager.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    path = manager.default_config_file()
    assert path == tmp_path / "user/F24Downloader/config.json"
    assert not path.exists()
    manager.salva_config({"utenze": [], "impostazioni": {}}, path)
    assert manager.carica_config(path)["utenze"] == []


def test_source_settings_keep_existing_location(monkeypatch):
    monkeypatch.delattr(manager.sys, "frozen", raising=False)
    assert manager.default_config_file() == manager.Path(manager.__file__).parent / "config.json"
