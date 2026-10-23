from dataclasses import replace
from datetime import date
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from playwright.sync_api import TimeoutError as PWTimeout
from src import service
from src.ade_login import effettua_login, is_portal_home
from src.cambia_utenza import esegui_cambio_utenza
from src.f24_downloader import safe_url, get_pdf_url_from_detail, scarica_f24
from src.models import DownloadRequest, DownloadResult, Cancelled

@pytest.mark.parametrize("url", [
    "https://example.com/a", "http://cassetto.agenziaentrate.gov.it/a",
    "javascript:alert(1)", "https://user:pass@cassetto.agenziaentrate.gov.it/a",
    "https://cassetto.agenziaentrate.gov.it.evil.invalid/a",
    "https://cassetto.agenziaentrate.gov.it:444/a",
])
def test_download_rejects_external_urls(url):
    with pytest.raises(ValueError):
        safe_url(url)

def test_relative_urls_and_quietanza_parameter():
    url = get_pdf_url_from_detail("/cassfisc-web/view?Ric=DetF24&stampa=P&indice=2")
    assert url.startswith("https://cassetto.agenziaentrate.gov.it/")
    assert "stampa=Q" in url and "stampa=P" not in url and "indice=2" in url

def test_portal_return_requires_exact_trusted_host():
    assert is_portal_home("https://portale.agenziaentrate.gov.it/PortaleWeb/home")
    assert not is_portal_home("https://evil.invalid/PortaleWeb/home")
    assert not is_portal_home("https://portale.agenziaentrate.gov.it/PortaleWeb/home/other")

def test_cancel_before_login_makes_no_network_request():
    page = Mock()
    cancel = Event()
    cancel.set()
    with pytest.raises(Cancelled):
        effettua_login(page, "SPID", "sielte", cancel=cancel)
    page.goto.assert_not_called()

def test_missing_authorized_user_stops_immediately():
    page = Mock()
    selector = page.locator.return_value
    selector.locator.return_value.evaluate_all.return_value = [{"value": "", "label": ""}, {"value": "DEMO123", "label": "Azienda demo"}]
    with pytest.raises(RuntimeError, match="non disponibile"):
        esegui_cambio_utenza(page, "NOT_ALLOWED", log=lambda _: None)
    selector.select_option.assert_not_called()

def test_confirmed_change_does_not_reopen_selector(monkeypatch):
    from src import cambia_utenza
    monkeypatch.setattr(cambia_utenza, "wait_seconds", lambda *args: None)
    page = Mock()
    page.url = "https://portale.agenziaentrate.gov.it/PortaleWeb/home"
    selector = page.locator.return_value
    selector.locator.return_value.evaluate_all.return_value = [{"value": "DEMO123", "label": "Azienda demo"}]
    selector.select_option.return_value = ["DEMO123"]
    # La seconda lettura simulerebbe un menu reimpostato: non deve avvenire.
    selector.input_value.side_effect = ["DEMO123", ""]
    esegui_cambio_utenza(page, "DEMO123", log=lambda _: None)
    assert selector.input_value.call_count == 1
    assert page.goto.call_count == 1
    page.wait_for_url.assert_called_once()

def test_missing_confirmation_home_stops_change(monkeypatch):
    from src import cambia_utenza
    page = Mock()
    selector = page.locator.return_value
    selector.locator.return_value.evaluate_all.return_value = [{"value": "DEMO123", "label": "Azienda demo"}]
    selector.select_option.return_value = ["DEMO123"]
    selector.input_value.return_value = "DEMO123"
    page.wait_for_url.side_effect = PWTimeout("synthetic")
    with pytest.raises(RuntimeError, match="pagina iniziale"):
        esegui_cambio_utenza(page, "DEMO123", log=lambda _: None)
    assert page.goto.call_count == 1


def test_failed_user_change_prevents_download_and_closes_browser(monkeypatch):
    monkeypatch.setattr(service, "prepare_destination", lambda path: path)
    browser = Mock()
    context = Mock()
    context.__enter__ = Mock(return_value=context)
    context.__exit__ = Mock(return_value=False)
    context.firefox.launch.return_value = browser
    monkeypatch.setattr(service, "sync_playwright", lambda: context)
    monkeypatch.setattr(service, "effettua_login", lambda *a, **k: None)
    def fail(*args, **kwargs):
        raise RuntimeError("Utenza non verificata")
    monkeypatch.setattr(service, "esegui_cambio_utenza", fail)
    download = Mock()
    monkeypatch.setattr(service, "scarica_f24", download)
    request = DownloadRequest("SPID", "sielte", "DEMO123", 2025,
                              date(2025, 1, 1), date(2025, 12, 31), Path("output"))
    with pytest.raises(RuntimeError):
        service.run_download(request, log=lambda _: None)
    download.assert_not_called()
    browser.close.assert_called_once()

def test_timeout_on_quietanza_tries_model_and_counts_only_one_error(tmp_path, monkeypatch):
    from src import f24_downloader as downloader
    monkeypatch.setattr(downloader, "apri_cassetto_e_scegli_date", lambda *a: None)
    monkeypatch.setattr(downloader, "collect_all_rows",
                        lambda *a: [{"url": "https://cassetto.agenziaentrate.gov.it/view?stampa=Q"}])
    attempted = []
    def fail(page, url, target):
        attempted.append(url)
        raise PWTimeout("synthetic timeout")
    monkeypatch.setattr(downloader, "download_pdf", fail)
    result = scarica_f24(Mock(), "2025", "", "", tmp_path, log=lambda _: None)
    assert result.errors == 1 and result.downloaded == 0
    assert len(attempted) == 2 and "stampa=Q" in attempted[0] and "stampa=P" in attempted[1]
    assert not list(tmp_path.glob("*.pdf"))



def test_cassetto_restores_session_before_retrying_list(monkeypatch):
    from src import f24_downloader as downloader
    monkeypatch.setattr(downloader, "seleziona_anno", lambda page, *args, **kwargs: page)
    monkeypatch.setattr(downloader, "apri_servizio_cassetto", lambda page, **kwargs: page)
    monkeypatch.setattr(downloader, "apri_consultazioni_e_versamenti", lambda page, **kwargs: page)
    page = Mock()
    page.url = downloader.BASE_URL
    page.locator.return_value.all.return_value = []
    broken = True
    def navigate(url, **kwargs):
        nonlocal broken
        page.url = url
        if url == downloader.BASE_URL:
            broken = False
    page.goto.side_effect = navigate
    page.locator.return_value.inner_text.side_effect = lambda **kwargs: (
        "La sessione deve essere ripristinata" if broken else "Elenco versamenti")
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    downloader.apri_cassetto_e_scegli_date(page, "2026", log=lambda _: None)
    assert page.goto.call_args_list[0].args[0] == downloader.BASE_URL
    assert "Anno=2026" in page.goto.call_args_list[-1].args[0]
    assert page.goto.call_count == 2


def test_cassetto_does_not_retry_an_unrecognized_page(monkeypatch):
    from src import f24_downloader as downloader
    monkeypatch.setattr(downloader, "seleziona_anno", lambda page, *args, **kwargs: page)
    monkeypatch.setattr(downloader, "apri_servizio_cassetto", lambda page, **kwargs: page)
    monkeypatch.setattr(downloader, "apri_consultazioni_e_versamenti", lambda page, **kwargs: page)
    page = Mock()
    page.locator.return_value.first.wait_for.side_effect = PWTimeout("synthetic")
    page.locator.return_value.inner_text.return_value = "Servizio non disponibile"
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    with pytest.raises(RuntimeError, match="non riconosciuto"):
        downloader.apri_cassetto_e_scegli_date(page, "2026", log=lambda _: None)
    assert page.goto.call_count == 1

def test_failure_is_reported_before_closing_browser(monkeypatch):
    monkeypatch.setattr(service, "prepare_destination", lambda path: path)
    browser = Mock()
    context = Mock()
    context.__enter__ = Mock(return_value=context)
    context.__exit__ = Mock(return_value=False)
    context.firefox.launch.return_value = browser
    monkeypatch.setattr(service, "sync_playwright", lambda: context)
    monkeypatch.setattr(service, "effettua_login", lambda *a, **k: None)
    monkeypatch.setattr(service, "esegui_cambio_utenza", lambda *a, **k: None)
    def fail(*args, **kwargs):
        raise PWTimeout("raw page error with private-data-in-url")
    monkeypatch.setattr(service, "scarica_f24", fail)
    request = DownloadRequest("SPID", "sielte", "DEMO123", 2025,
                              date(2025, 1, 1), date(2025, 12, 31), Path("output"))
    cancel = Event()
    messages = []
    def on_error(message):
        assert not browser.close.called
        messages.append(message)
        cancel.set()
    with pytest.raises(PWTimeout):
        service.run_download(request, cancel=cancel, log=lambda _: None, on_error=on_error)
    assert len(messages) == 1
    assert "Apertura Cassetto e ricerca F24" in messages[0]
    assert "private-data-in-url" not in messages[0]
    browser.close.assert_called_once()


def test_explicit_quietanza_rejection_then_model_failure_counts_one_error(tmp_path, monkeypatch):
    from src import f24_downloader as downloader
    monkeypatch.setattr(downloader, "apri_cassetto_e_scegli_date", lambda *a: None)
    monkeypatch.setattr(downloader, "collect_all_rows",
        lambda *a: [{"url": downloader.BASE_URL + "?Ric=DetF24&indice=7&stampa=Q"}])
    attempted = []
    def fail(page, url, target):
        attempted.append(url)
        if "stampa=Q" in url:
            raise downloader.QuietanzaNotPrintable("Errore esplicito")
        raise PWTimeout("synthetic timeout")
    monkeypatch.setattr(downloader, "download_pdf", fail)
    result = downloader.scarica_f24(Mock(), "2020", "", "", tmp_path, log=lambda _: None)
    assert result.errors == 1 and result.downloaded == result.models == 0
    assert len(attempted) == 2 and "stampa=P" in attempted[1] and "indice=7" in attempted[1]
    assert not list(tmp_path.glob("*.pdf"))


def test_cancel_after_quietanza_timeout_does_not_attempt_model(tmp_path, monkeypatch):
    from src import f24_downloader as downloader
    monkeypatch.setattr(downloader, "apri_cassetto_e_scegli_date", lambda *args: None)
    monkeypatch.setattr(downloader, "collect_all_rows", lambda *args: [
        {"url": downloader.BASE_URL + "?Ric=DetF24&stampa=Q"}])
    cancel = Event()
    attempted = []
    def timed_out(page, url, destination):
        attempted.append(url)
        cancel.set()
        raise PWTimeout("Synthetic")
    monkeypatch.setattr(downloader, "download_pdf", timed_out)
    result = downloader.scarica_f24(Mock(), "2025", "", "", tmp_path,
        cancel=cancel, log=lambda _: None)
    assert result.cancelled and result.errors == result.downloaded == 0
    assert len(attempted) == 1 and "stampa=Q" in attempted[0]


def test_personal_profile_never_opens_user_selection():
    page = Mock()
    logs = []
    esegui_cambio_utenza(page, "", log=logs.append)
    assert not page.mock_calls
    assert any("nessun cambio utenza" in line for line in logs)


def test_personal_profile_service_goes_directly_from_login_to_cassetto(tmp_path, monkeypatch):
    playwright = Mock()
    playwright.__enter__ = Mock(return_value=playwright)
    playwright.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(service, "sync_playwright", lambda: playwright)
    login, change = Mock(), Mock()
    opened = Mock(side_effect=lambda page, **kwargs: page)
    download = Mock(return_value=DownloadResult(total=1, downloaded=1))
    monkeypatch.setattr(service, "effettua_login", login)
    monkeypatch.setattr(service, "esegui_cambio_utenza", change)
    monkeypatch.setattr(service, "apri_servizio_cassetto", opened)
    monkeypatch.setattr(service, "scarica_f24", download)
    stages, logs = [], []
    request = DownloadRequest("CIE", "", "", 2025, date(2025, 1, 1), date(2025, 12, 31), tmp_path)
    result = service.run_download(request, log=logs.append, stage=stages.append)
    login.assert_called_once()
    change.assert_not_called()
    opened.assert_called_once()
    download.assert_called_once()
    assert "Cambio utenza" not in stages
    assert stages[:2] == ["Accesso", "Apertura Cassetto e ricerca F24"]
    assert result.downloaded == 1
    assert any("Profilo personale" in line for line in logs)
