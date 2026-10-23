"""Configurazione locale. Segreti separati e protetti con Windows DPAPI."""
import json
import os
import sys
import uuid
from pathlib import Path
from src.security import protect, unprotect

def default_config_file():
    """Installazioni: dati per utente, separati dai file del programma."""
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA")
        base = Path(local) if local else Path.home() / "AppData/Local"
        return base / "F24Downloader/config.json"
    return Path(__file__).parent / "config.json"


CONFIG_FILE = default_config_file()


class CredentialsUnavailableError(ValueError):
    """Archivio presente ma non decifrabile o non valido per questa sessione."""


def _atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def carica_config(path=None):
    path = Path(path or CONFIG_FILE)
    config = {"utenze": [], "impostazioni": {}, "credenziali": {}}
    if path.exists():
        settings = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(settings, dict):
            raise ValueError("Configurazione non valida")
        config.update(settings)
    if (not isinstance(config.get("utenze"), list)
            or not isinstance(config.get("impostazioni"), dict)
            or not isinstance(config.get("credenziali"), dict)):
        raise ValueError("Configurazione non valida")
    secrets = path.with_name("credentials.bin")
    if secrets.exists():
        encrypted = secrets.read_bytes()  # Gli errori di accesso restano distinti.
        try:
            stored = json.loads(unprotect(encrypted).decode("utf-8"))
            if not isinstance(stored, dict) or any(not isinstance(value, dict) for value in stored.values()):
                raise ValueError("Archivio credenziali non valido")
        except (OSError, RuntimeError, ValueError, UnicodeError):
            raise CredentialsUnavailableError("Credenziali salvate non utilizzabili su questo account Windows.") from None
        stored.update(config.get("credenziali", {}))
        config["credenziali"] = stored
    return config

def carica_config_avvio(path=None):
    """Recupero solo all'avvio: conservare l'archivio illeggibile prima di proseguire."""
    path = Path(path or CONFIG_FILE)
    try:
        return carica_config(path), None
    except CredentialsUnavailableError:
        secrets = path.with_name("credentials.bin")
        backup = secrets.with_name("credentials.bin.non-utilizzabile-" + uuid.uuid4().hex)
        # Il file resta cifrato; nessuna eliminazione o sovrascrittura.
        # Se la cartella non è scrivibile l'avvio si ferma con l'errore di accesso.
        secrets.rename(backup)
        try:
            config = carica_config(path)
        except Exception:
            if not secrets.exists():
                backup.rename(secrets)
            raise
        warning = (
            "Le credenziali salvate non sono utilizzabili su questo account Windows. "
            "Può accadere dopo aver copiato il programma su un altro computer o se il file è danneggiato.\n\n"
            "Il file originale è stato conservato nella cartella della configurazione con nome "
            "credentials.bin.non-utilizzabile-… Le utenze e le impostazioni sono state mantenute.\n\n"
            "Reinserisci le credenziali su questo PC e, se desideri, scegli di ricordarle. "
            "Controlla anche la cartella di destinazione dei PDF."
        )
        return config, warning


def salva_config(config, path=None):
    path = Path(path or CONFIG_FILE)
    credentials = config.get("credenziali", {})
    if credentials:
        payload = json.dumps(credentials, ensure_ascii=False).encode("utf-8")
        encrypted = protect(payload)
        if unprotect(encrypted) != payload:
            raise RuntimeError("Verifica archivio credenziali fallita")
        _atomic_write(path.with_name("credentials.bin"), encrypted)
    settings = {k: v for k, v in config.items() if k != "credenziali"}
    _atomic_write(path, json.dumps(settings, indent=2, ensure_ascii=False).encode("utf-8"))
    if not credentials:
        path.with_name("credentials.bin").unlink(missing_ok=True)

def get_utenze(config):
    return config.get("utenze", [])

def get_impostazioni(config):
    return config.get("impostazioni", {})

def get_credenziali(config, metodo):
    return config.get("credenziali", {}).get(metodo, {})
