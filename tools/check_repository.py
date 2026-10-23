"""Verifica i file destinati a GitHub, senza stampare dati privati o creare archivi."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.prepare_release import release_files, private_values


class RepositoryCheckError(RuntimeError):
    pass


def _git(root, *args, data=None):
    result = subprocess.run(["git", "-C", str(root), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RepositoryCheckError("Operazione Git non riuscita. Verifica il repository locale.")
    return result.stdout


def check_repository(root=ROOT, staged=False):
    root = Path(root)
    allowed = {path.relative_to(root).as_posix() for path in release_files(root)}
    tracked = set(_git(root, "ls-files", "-z").decode("utf-8").rstrip("\0").split("\0")) - {""}
    if tracked - allowed:
        raise RepositoryCheckError("Git contiene file non ammessi alla pubblicazione. Nessun dato privato viene mostrato.")
    if allowed - tracked:
        raise RepositoryCheckError("Alcuni sorgenti pubblicabili non sono ancora stati aggiunti a Git.")
    try:
        private = private_values(root)
    except Exception:
        raise RepositoryCheckError("Non è stato possibile verificare la configurazione privata locale.") from None
    needles = set()
    for value in private:
        for candidate in (value, json.dumps(value, ensure_ascii=False)[1:-1],
                          json.dumps(value, ensure_ascii=True)[1:-1]):
            needles.add(candidate.encode("utf-8"))
    payloads = {}
    for name in sorted(tracked):
        payload = _git(root, "show", ":" + name) if staged else (root / name).read_bytes()
        if any(needle and needle in payload for needle in needles):
            raise RepositoryCheckError("Possibile dato privato in un sorgente destinato a GitHub: " + name)
        payloads[name] = payload
    example = json.loads(payloads["config/config.example.json"].decode("utf-8-sig"))
    if (example.get("utenze") or example.get("credenziali")
            or "output_dir" in example.get("impostazioni", {})):
        raise RepositoryCheckError("La configurazione di esempio deve essere senza utenze, credenziali e cartella di download.")
    ignored = ["config/config.json", "config/config.json.bak", "config/credentials.bin",
               "config/credentials.bin.non-utilizzabile-demo", "f24_output/demo/2025/quietanza.pdf",
               "download_privati/documento.txt", ".release/source.zip", "docs/documento.pdf"]
    data = ("\0".join(ignored) + "\0").encode("utf-8")
    actual = _git(root, "check-ignore", "--no-index", "-z", "--stdin", data=data)
    if set(actual.decode("utf-8").rstrip("\0").split("\0")) != set(ignored):
        raise RepositoryCheckError("Le esclusioni Git dei dati locali sono incomplete.")
    return len(tracked)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged", action="store_true", help="Verifica il contenuto effettivamente aggiunto a Git.")
    args = parser.parse_args()
    try:
        count = check_repository(staged=args.staged)
    except Exception as error:
        print(str(error) if isinstance(error, RepositoryCheckError) else "Verifica non riuscita. Controllare i file pubblicabili.")
        return 1
    print(f"Verifica completata: {count} file pubblicabili. Utenze, credenziali, destinazione personale e documenti esclusi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
