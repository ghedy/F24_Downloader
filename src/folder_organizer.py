"""Riordino locale dei PDF: confronto del contenuto, rimozione copie e rinomina."""
from dataclasses import dataclass, replace
from pathlib import Path
import hashlib
import re
import shutil
from src.rinomina_f24 import _impronta_contenuto, estrai_dati

@dataclass
class FolderResult:
    total: int = 0
    processed: int = 0
    renamed: int = 0
    duplicates: int = 0
    unchanged: int = 0
    unclassified: int = 0
    errors: int = 0
    cancelled: bool = False

def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()

def _checked(path, folder):
    path = Path(path)
    if path.is_symlink() or path.resolve().parent != folder:
        raise ValueError("File esterno alla cartella selezionata.")
    return path

def _rename(source, destination, digest, folder):
    _checked(source, folder)
    _checked(destination, folder)
    created = False
    try:
        with destination.open("xb") as target:
            created = True
            with source.open("rb") as stream:
                shutil.copyfileobj(stream, target)
        if _sha(destination) != digest or _sha(source) != digest:
            raise RuntimeError("File modificato durante la rinomina.")
        source.unlink()
    except Exception:
        if created and source.exists():
            destination.unlink(missing_ok=True)
        raise
    return destination

def _standard_name(path, data, digest, folder):
    if data is None:
        return path
    prefix = "F24_modello" if path.name.startswith("F24_modello_") else "F24"
    day, amount, _ = data
    amount = amount.replace(",", ".")
    if re.fullmatch(rf"{prefix}_{day}_\d+_{re.escape(amount)}euro\.pdf", path.name, re.IGNORECASE):
        return path
    sequence = 1
    while True:
        target = folder / f"{prefix}_{day}_{sequence:03d}_{amount}euro.pdf"
        try:
            return _rename(path, target, digest, folder)
        except FileExistsError:
            sequence += 1

def organize_folder(folder, cancel=None, log=print, progress=None):
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise ValueError("Cartella da riordinare non disponibile.")
    files = sorted((p for p in folder.iterdir() if p.suffix.lower() == ".pdf" and p.is_file()),
        key=lambda p: (not bool(re.match(r"F24_(?:modello_)?\d{8}_\d+_", p.name)), p.name.casefold()))
    result = FolderResult(total=len(files))
    cache, binary_seen, content_seen = {}, {}, {}
    log(f"Riordino di tutta la cartella utenza/anno: {len(files)} PDF. Confronto per contenuto.")
    for index, source in enumerate(files, 1):
        if cancel is not None and cancel.is_set():
            result.cancelled = True
            break
        try:
            _checked(source, folder)
            digest = _sha(source)
            content = _impronta_contenuto(source, cache)
            keeper = binary_seen.get(digest) or (content_seen.get(content) if content else None)
            if keeper is not None:
                kept_path, kept_digest = keeper
                _checked(kept_path, folder)
                if _sha(kept_path) != kept_digest or _sha(source) != digest:
                    raise RuntimeError("Un file è cambiato durante il confronto.")
                # Eliminare solo la copia verificata; la copia conservata è ancora presente.
                source.unlink()
                result.duplicates += 1
                log(f"{index}/{len(files)} · Copia duplicata eliminata.")
            else:
                data = estrai_dati(str(source))
                final = _standard_name(source, data, digest, folder)
                if final != source:
                    result.renamed += 1
                    log(f"{index}/{len(files)} · PDF rinominato.")
                else:
                    result.unchanged += 1
                    if data is None:
                        result.unclassified += 1
                        log(f"{index}/{len(files)} · PDF non riconosciuto: nome conservato.")
                keeper = (final, digest)
                binary_seen[digest] = keeper
                if content is not None:
                    content_seen[content] = keeper
        except Exception:
            result.errors += 1
            log(f"{index}/{len(files)} · File non modificato o operazione non completata: verifica accesso e permessi.")
        result.processed += 1
        if progress:
            progress(replace(result))
    log(f"Riordino {'interrotto' if result.cancelled else 'completato'}: "
        f"{result.renamed} rinominati, {result.duplicates} duplicati eliminati, "
        f"{result.unchanged} invariati, {result.errors} errori.")
    return result



def organize_folders(folders, cancel=None, log=print, progress=None):
    aggregate = FolderResult()
    for folder in folders:
        if cancel is not None and cancel.is_set():
            aggregate.cancelled = True
            break
        if not Path(folder).is_dir():
            log(f"Anno {Path(folder).name}: cartella non presente, riordino saltato.")
            continue
        log(f"Riordino cartella dell'anno {Path(folder).name}.")
        baseline = replace(aggregate)
        def report(current):
            if progress:
                value = replace(current)
                for name in ("total", "processed", "renamed", "duplicates", "unchanged", "unclassified", "errors"):
                    setattr(value, name, getattr(baseline, name) + getattr(current, name))
                progress(value)
        current = organize_folder(folder, cancel, log, report)
        for name in ("total", "processed", "renamed", "duplicates", "unchanged", "unclassified", "errors"):
            setattr(aggregate, name, getattr(aggregate, name) + getattr(current, name))
        aggregate.cancelled = aggregate.cancelled or current.cancelled
        if aggregate.cancelled:
            break
    return aggregate
