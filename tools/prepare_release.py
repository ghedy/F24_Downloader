"""Crea un archivio sorgente selezionato. Nessuna operazione Git o di rete."""
import json
from pathlib import Path
import sys
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import __version__

TOP_LEVEL = {
    "main.py", "README.md", "LICENSE", "SECURITY.md", "requirements.txt",
    "requirements-dev.txt", "pyproject.toml", "avvia.bat", ".gitignore", ".gitattributes",
}
CONFIG = {"config/__init__.py", "config/config_manager.py", "config/config.example.json"}
TREES = {"src": {".py", ".svg"}, "tests": {".py"}, "tools": {".py"}, "docs": {".md"},
         ".github": {".md", ".yml", ".yaml"}, "packaging": {".txt", ".iss"}}

def release_files(root=ROOT):
    root = Path(root)
    paths = [root / name for name in TOP_LEVEL | CONFIG]
    for tree, extensions in TREES.items():
        paths.extend(path for path in (root / tree).rglob("*")
                     if path.is_file() and path.suffix in extensions
                     and "__pycache__" not in path.parts)
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise RuntimeError("File esterno alla cartella sorgente rifiutato")
        if not path.is_file():
            raise RuntimeError("Manca un file necessario: " + str(path.relative_to(root)))
    return sorted(set(paths))

def private_values(root):
    from config.config_manager import carica_config
    config = carica_config(Path(root) / "config/config.json")
    values = []
    for entry in config.get("credenziali", {}).values():
        for key in ("username", "password", "pin", "word"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                values.append(value)
    for user in config.get("utenze", []):
        values.extend(str(user[key]) for key in ("codice", "descrizione") if user.get(key))
    output_dir = config.get("impostazioni", {}).get("output_dir")
    if isinstance(output_dir, str) and output_dir.strip() not in {"", ".", "output", "./output", "f24_output", "./f24_output"}:
        values.append(output_dir)
        values.append(output_dir.replace("\\", "/"))
        values.append(output_dir.replace("/", "\\"))
    return list(set(values))

def build_release(root=ROOT, check_private=True):
    root = Path(root)
    paths = release_files(root)
    private = private_values(root) if check_private else []
    payloads = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        if any(value.encode("utf-8") in data for value in private):
            raise RuntimeError("Possibile dato privato nel file " + relative + ". Archivio non creato.")
        payloads[relative] = data
    target = root / ".release"
    target.mkdir(exist_ok=True)
    archive = target / f"f24-downloader-{__version__}-source.zip"
    temporary = archive.with_suffix(".zip.tmp")
    try:
        with ZipFile(temporary, "w", ZIP_DEFLATED) as bundle:
            for relative, data in payloads.items():
                bundle.writestr(relative, data)
        temporary.replace(archive)
    finally:
        temporary.unlink(missing_ok=True)
    (target / "manifest.txt").write_text("\n".join(payloads) + "\n", encoding="utf-8")
    return archive, len(paths)

if __name__ == "__main__":
    try:
        archive, count = build_release()
    except Exception:
        print("Preparazione non riuscita: verifica i file selezionati e i dati privati. Nessun invio in rete.")
        raise SystemExit(1)
    print(f"Archivio creato: {archive}")
    print(f"File selezionati: {count}. Controllare .release/manifest.txt prima del rilascio.")
