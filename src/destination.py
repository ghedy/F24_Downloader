"""Verifica della destinazione prima di richiedere l'autenticazione."""
import tempfile
from pathlib import Path

class DestinationError(ValueError):
    pass

def prepare_destination(path):
    path = Path(path)
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Verificare anche la scrittura: una cartella di rete può essere leggibile soltanto.
        with tempfile.TemporaryFile(prefix=".f24-write-check-", dir=path) as stream:
            stream.write(b"F24")
            stream.flush()
    except FileNotFoundError:
        drive = path.drive
        location = f" L'unità {drive} non è raggiungibile." if len(drive) == 2 and drive.endswith(":") else ""
        raise DestinationError("Cartella di destinazione non disponibile." + location +
            " Verifica il collegamento all'unità di rete oppure scegli una cartella accessibile con Sfoglia, "
            "poi avvia nuovamente il download.") from None
    except PermissionError:
        raise DestinationError("Impossibile scrivere nella cartella di destinazione. "
            "Verifica i permessi oppure scegli un'altra cartella con Sfoglia.") from None
    except (NotADirectoryError, FileExistsError):
        raise DestinationError("Il percorso di destinazione contiene un file al posto di una cartella. "
            "Scegli una cartella valida con Sfoglia.") from None
    except OSError:
        raise DestinationError("Impossibile preparare la cartella di destinazione. "
            "Verifica percorso, disponibilità dell'unità e permessi di scrittura.") from None
    return path
