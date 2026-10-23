from pathlib import Path
import json
import uuid
from zipfile import ZipFile
from tools.prepare_release import release_files, build_release, ROOT

def test_release_allowlist_excludes_local_data():
    names = [path.relative_to(ROOT).as_posix() for path in release_files()]
    assert "main.py" in names and "config/config.example.json" in names
    assert "src/ui/icons/chevron-up.svg" in names and "src/ui/icons/chevron-down.svg" in names
    assert "config/config.json" not in names
    assert not any("_legacy" in name or "credentials.bin" in name
                   or "f24_output" in name or "__pycache__" in name for name in names)

def test_archive_contains_selected_files_only(tmp_path):
    # Copia esclusivamente i file pubblicabili, con un falso segreto extra.
    for source in release_files():
        target = tmp_path / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    private = tmp_path / "config/config.json"
    secret = "private-" + uuid.uuid4().hex
    private.write_text(json.dumps({"credenziali": {"SPID_SIELTE": {"password": secret}}}))
    (tmp_path / "config/credentials.bin.non-utilizzabile-demo").write_bytes(b"encrypted-private-backup")
    archive, count = build_release(tmp_path)
    with ZipFile(archive) as bundle:
        assert len(bundle.namelist()) == count
        assert "config/config.json" not in bundle.namelist()
        assert not any("credentials.bin" in name for name in bundle.namelist())
        assert not any(secret.encode() in bundle.read(name) for name in bundle.namelist())
