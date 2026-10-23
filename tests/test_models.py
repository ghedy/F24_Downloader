from dataclasses import replace
from datetime import date
from pathlib import Path
import pytest
from src.models import DownloadRequest

@pytest.fixture
def download_request():
    return DownloadRequest("SPID", "sielte", "", 2025, date(2025, 1, 1), date(2025, 12, 31), Path("output"))

def test_valid_period_and_separate_destination(download_request):
    download_request.validate()
    assert download_request.destination == Path("output/profilo_personale/2025")
    assert replace(download_request, utenza="DEMO123").destination == Path("output/DEMO123/2025")

@pytest.mark.parametrize("changes", [
    {"al": date(2024, 12, 31)}, {"dal": date(2025, 12, 31), "al": date(2025, 1, 1)},
    {"anno": 1999}, {"utenza": "../altra_cartella"}, {"utenza": "A/B"},
    {"pausa": 0}, {"provider": "sconosciuto"}, {"metodo": "altro"},
])
def test_invalid_inputs_stop_before_browser(download_request, changes):
    with pytest.raises(ValueError):
        replace(download_request, **changes).validate()

@pytest.mark.parametrize("method", ["CNS", "FISCONLINE", "PORTALE"])
def test_untested_methods_are_unavailable(download_request, method):
    with pytest.raises(ValueError, match="in attesa di collaudo"):
        replace(download_request, metodo=method, provider="", automatico=False).validate()
