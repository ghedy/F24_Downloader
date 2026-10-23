from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
import re

AVAILABLE_LOGIN_METHODS = frozenset({"SPID", "CIE"})


class Cancelled(Exception):
    """Interruzione richiesta dall'utente."""

def check_cancel(event):
    if event is not None and event.is_set():
        raise Cancelled()

@dataclass(frozen=True)
class DownloadRequest:
    metodo: str
    provider: str
    utenza: str
    anno: int
    dal: date
    al: date
    output_dir: Path
    automatico: bool = False
    pausa: float = 2.0
    riordina_cartella: bool = False
    anno_fine: int | None = None

    def validate(self):
        if self.metodo not in AVAILABLE_LOGIN_METHODS:
            raise ValueError("Sono disponibili solo SPID Sielte e CIE. Gli altri metodi sono in attesa di collaudo.")
        if self.metodo == "SPID" and self.provider != "sielte":
            raise ValueError("Per ora è disponibile solo il gestore SPID Sielte.")
        if not 2000 <= self.anno <= date.today().year:
            raise ValueError("Anno non valido.")
        if self.dal > self.al:
            raise ValueError("La data iniziale deve precedere quella finale.")
        if not self.anno <= self.last_year <= date.today().year:
            raise ValueError("L'anno finale deve essere compreso fra l'anno iniziale e quello corrente.")
        if self.dal.year != self.anno or self.al.year != self.last_year:
            raise ValueError("Le date devono appartenere rispettivamente all'anno iniziale e a quello finale.")
        if self.utenza and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.utenza):
            raise ValueError("Il codice utenza contiene caratteri non validi.")
        if self.pausa < 2:
            raise ValueError("La pausa minima tra i download è di 2 secondi.")

    @property
    def last_year(self):
        return self.anno if self.anno_fine is None else self.anno_fine

    @property
    def years(self):
        return tuple(range(self.anno, self.last_year + 1))

    def year_requests(self):
        return tuple(replace(self, anno=year, anno_fine=None,
            dal=max(self.dal, date(year, 1, 1)), al=min(self.al, date(year, 12, 31)))
            for year in self.years)

    @property
    def destination(self):
        root = self.output_dir / (self.utenza.upper() or "profilo_personale")
        return root / str(self.anno) if self.last_year == self.anno else root

    @property
    def destinations(self):
        return tuple(item.destination for item in self.year_requests())

@dataclass
class DownloadResult:
    total: int = 0
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    models: int = 0
    unclassified: int = 0
    cancelled: bool = False
    destination: Path | None = None
    renamed_existing: int = 0
    removed_existing_duplicates: int = 0
    cleanup_errors: int = 0
    unavailable_years: tuple[int, ...] = ()
    empty_years: tuple[int, ...] = ()
    processed_years: tuple[int, ...] = ()
