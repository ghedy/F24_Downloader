from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import Mock
import pytest
from playwright.sync_api import sync_playwright
from src.models import DownloadRequest, DownloadResult
from src import service, f24_downloader as downloader
from tests.test_pdf_files import make_pdf

def test_multi_year_splits_boundaries_and_folders(tmp_path):
    request = DownloadRequest("CIE", "", "DEMO123", 2023, date(2023, 3, 15),
        date(2025, 2, 10), tmp_path, anno_fine=2025)
    request.validate()
    annual = request.year_requests()
    assert [(item.anno, item.dal, item.al) for item in annual] == [
        (2023, date(2023, 3, 15), date(2023, 12, 31)),
        (2024, date(2024, 1, 1), date(2024, 12, 31)),
        (2025, date(2025, 1, 1), date(2025, 2, 10))]
    assert request.destination == tmp_path / "DEMO123"
    assert [item.destination.name for item in annual] == ["2023", "2024", "2025"]

@pytest.mark.parametrize("last,end", [(2022, date(2022, 12, 31)), (2099, date(2099, 1, 1)),
                                    (2025, date(2024, 12, 31))])
def test_invalid_multi_year_range_is_rejected(tmp_path, last, end):
    request = DownloadRequest("CIE", "", "", 2023, date(2023, 1, 1), end, tmp_path, anno_fine=last)
    with pytest.raises(ValueError):
        request.validate()

def test_multi_year_uses_one_login_and_continues_after_unavailable_year(tmp_path, monkeypatch):
    playwright = Mock()
    playwright.__enter__ = Mock(return_value=playwright)
    playwright.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(service, "sync_playwright", lambda: playwright)
    login, user = Mock(), Mock()
    monkeypatch.setattr(service, "effettua_login", login)
    monkeypatch.setattr(service, "esegui_cambio_utenza", user)
    monkeypatch.setattr(service, "apri_servizio_cassetto", lambda page, **kwargs: page)
    calls = []
    def download(page, year, start, end, output, cancel, log, progress, pause):
        calls.append((year, start, end, output.name))
        result = (DownloadResult(unavailable_years=(2024,)) if year == "2024"
                  else DownloadResult(total=1, downloaded=1))
        progress(result)
        return result
    monkeypatch.setattr(service, "scarica_f24", download)
    request = DownloadRequest("CIE", "", "DEMO123", 2023, date(2023, 3, 15),
        date(2025, 2, 10), tmp_path, anno_fine=2025)
    result = service.run_download(request, log=lambda _: None)
    login.assert_called_once()
    user.assert_called_once()
    assert calls == [("2023", "15/03/2023", "31/12/2023", "2023"),
                     ("2024", "01/01/2024", "31/12/2024", "2024"),
                     ("2025", "01/01/2025", "10/02/2025", "2025")]
    assert result.downloaded == result.total == 2
    assert result.unavailable_years == (2024,)
    assert result.processed_years == (2023, 2024, 2025)

@pytest.fixture(scope="module")
def year_browser():
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=True)
        yield browser
        browser.close()

@pytest.mark.parametrize("empty", [False, True])
def test_select_2025_before_applying_period_and_accept_no_occurrences(year_browser, tmp_path, monkeypatch, empty):
    from urllib.parse import urlsplit, parse_qs
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    pdf = tmp_path / "fixture.pdf"
    make_pdf(pdf, ["QUIETANZA DI VERSAMENTO", "DATA DEL VERSAMENTO 18 10 2025 ABI",
                   "Saldo delega 100,00", "PROTOCOLLO TELEMATICO 123 7"])
    selected = False
    events = []
    with year_browser.new_context(accept_downloads=True) as context:
        page = context.new_page()
        def respond(route):
            nonlocal selected
            url = urlsplit(route.request.url)
            query = parse_qs(url.query)
            if url.path == "/pdf":
                route.fulfill(status=200, content_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="quietanza.pdf"'}, body=pdf.read_bytes())
            elif query.get("Ric") == ["VERS"]:
                route.fulfill(status=200, content_type="text/html", body=
                    '<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=F24&amp;Anno=2025" title="Documenti presenti"><span>2025</span></a>')
            elif query.get("Ric") == ["F24"]:
                assert query["Anno"] == ["2025"]
                if "dataDal" not in query:
                    selected = True
                    events.append("year")
                else:
                    assert selected, "Il filtro non deve precedere il click sull'anno"
                    assert query["dataDal"] == ["01/03/2025"]
                    assert query["dataAl"] == ["30/11/2025"]
                    events.append("period")
                html = ("NESSUNA OCCORRENZA trovata per la selezione effettuata" if empty
                        else '<table><tbody><tr><td><a href="/pdf?stampa=Q">Quietanza</a></td></tr></tbody></table>')
                route.fulfill(status=200, content_type="text/html", body=html)
            else:
                route.abort()
                raise AssertionError("Richiesta non prevista")
        context.route("**/*", respond)
        page.goto(downloader.BASE_URL + "?Ric=VERS")
        result = downloader.scarica_f24(page, "2025", "01/03/2025", "30/11/2025",
            tmp_path / "output", log=lambda _: None)
    assert events[:2] == ["year", "period"]
    assert result.errors == 0
    if empty:
        assert result.empty_years == (2025,)
        assert result.total == result.downloaded == 0
    else:
        assert result.downloaded == 1
        assert len(list((tmp_path / "output").glob("F24_2025*.pdf"))) == 1

def test_absent_year_selector_is_skipped_without_guessing_url(year_browser, tmp_path, monkeypatch):
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    visits = []
    with year_browser.new_context() as context:
        page = context.new_page()
        def respond(route):
            visits.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=
                '<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=F24&amp;Anno=2025">2025</a>')
        context.route("**/*", respond)
        page.goto(downloader.BASE_URL + "?Ric=VERS")
        result = downloader.scarica_f24(page, "2024", "01/01/2024", "31/12/2024",
            tmp_path / "output", log=lambda _: None)
    assert result.unavailable_years == (2024,)
    assert result.errors == result.downloaded == 0
    assert len(visits) == 1


def test_sequential_years_reopen_selector_and_skip_missing_middle_year(year_browser, tmp_path, monkeypatch):
    from urllib.parse import urlsplit, parse_qs
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    pdfs = {}
    for year in (2023, 2025):
        fixture = tmp_path / f"fixture-{year}.pdf"
        make_pdf(fixture, ["QUIETANZA DI VERSAMENTO", f"DATA DEL VERSAMENTO 18 10 {year} ABI",
                          "Saldo delega 100,00", f"PROTOCOLLO TELEMATICO {year} 7"])
        pdfs[str(year)] = fixture.read_bytes()
    selected = []
    with year_browser.new_context(accept_downloads=True) as context:
        page = context.new_page()
        def respond(route):
            url = urlsplit(route.request.url)
            query = parse_qs(url.query)
            if url.path == "/pdf":
                route.fulfill(status=200, content_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="quietanza.pdf"'},
                    body=pdfs[query["year"][0]])
            elif url.path == "/cassfisc-web/CassettoFiscaleServlet" and not url.query:
                route.fulfill(status=200, content_type="text/html", body=
                    '<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=VERS">Versamenti</a>')
            elif query.get("Ric") == ["VERS"]:
                links = "".join(f'<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=F24&amp;Anno={year}">{year}</a>'
                                for year in (2023, 2025))
                route.fulfill(status=200, content_type="text/html", body=links)
            elif query.get("Ric") == ["F24"]:
                year = query["Anno"][0]
                assert year in pdfs
                if "dataDal" not in query:
                    selected.append(year)
                else:
                    assert selected[-1] == year
                html = ('<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=VERS">Versamenti</a>'
                        '<table><tbody><tr><td><a href="/pdf?year=' + year +
                        '&amp;stampa=Q">Quietanza</a></td></tr></tbody></table>')
                route.fulfill(status=200, content_type="text/html", body=html)
            else:
                route.abort()
        context.route("**/*", respond)
        page.goto(downloader.BASE_URL + "?Ric=VERS")
        results = [downloader.scarica_f24(page, str(year), f"01/01/{year}", f"31/12/{year}",
                   tmp_path / "output" / str(year), log=lambda _: None) for year in (2023, 2024, 2025)]
    assert selected == ["2023", "2025"]
    assert [result.downloaded for result in results] == [1, 0, 1]
    assert results[1].unavailable_years == (2024,)
    assert all(result.errors == 0 for result in results)
    assert len(list((tmp_path / "output" / "2023").glob("*.pdf"))) == 1
    assert len(list((tmp_path / "output" / "2025").glob("*.pdf"))) == 1



@pytest.mark.parametrize("error_attachment", [False, True])
def test_full_2020_2026_range_recovers_from_q_error_and_collapsing_menu(year_browser, tmp_path, monkeypatch, error_attachment):
    from urllib.parse import urlsplit, parse_qs
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    monkeypatch.setattr(downloader, "DOWNLOAD_TIMEOUT_SECONDS", 3)
    pdf = tmp_path / "fixture.pdf"
    make_pdf(pdf, ["QUIETANZA DI VERSAMENTO", "DATA DEL VERSAMENTO 18 10 2020 ABI",
                   "Saldo delega 100,00", "PROTOCOLLO TELEMATICO 123 7"])
    selected, filters, returns, attempts = [], [], [], []
    output = tmp_path / "output"
    menu = ('<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=VERS" '
            'class="collapsed nav-link active" data-toggle="collapse" '
            'onclick="event.preventDefault();document.body.dataset.collapsed=1">Versamenti</a>')
    logs = []
    with year_browser.new_context(accept_downloads=True) as context:
        page = context.new_page()
        def respond(route):
            url = urlsplit(route.request.url)
            query = parse_qs(url.query)
            if url.path == "/cassfisc-web/pdf":
                kind = query["stampa"][0]
                year = query["year"][0]
                attempts.append((year, kind))
                if year == "2020" and kind == "Q":
                    # Nessun menu sulla pagina di errore del portale.
                    headers = ({"Content-Disposition": 'attachment; filename="quietanza.pdf"'}
                               if error_attachment else {})
                    route.fulfill(status=200, content_type="text/html; charset=utf-8", headers=headers,
                        body="<p>La delega richiesta non è stampabile nel formato QUIETANZA</p>")
                else:
                    route.fulfill(status=200, content_type="application/pdf",
                        headers={"Content-Disposition": 'attachment; filename="documento.pdf"'}, body=pdf.read_bytes())
            elif url.path == "/cassfisc-web/CassettoFiscaleServlet" and not url.query:
                route.fulfill(status=200, content_type="text/html", body=
                    '<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=VERS">Versamenti</a>')
            elif query.get("Ric") == ["VERS"]:
                returns.append("VERS")
                links = "".join(f'<a href="?Ric=F24&amp;Anno={year}">{year}</a>'
                                for year in range(2020, 2027) if year != 2023)
                route.fulfill(status=200, content_type="text/html; charset=utf-8", body=menu + links)
            elif query.get("Ric") == ["F24"]:
                year = query["Anno"][0]
                if "dataDal" not in query:
                    selected.append(year)
                else:
                    assert selected[-1] == year
                    assert query["dataDal"] == [f"01/01/{year}"]
                    assert query["dataAl"] == [f"31/12/{year}"]
                    filters.append(year)
                html = ("NESSUNA OCCORRENZA trovata per la selezione effettuata" if year == "2024"
                        else '<table><tbody><tr><td><a href="/cassfisc-web/pdf?year=' + year +
                             '&amp;stampa=Q">Quietanza</a></td></tr></tbody></table>')
                route.fulfill(status=200, content_type="text/html; charset=utf-8", body=menu + html)
            else:
                route.abort()
                raise AssertionError("Richiesta non prevista")
        context.route("**/*", respond)
        page.goto(downloader.BASE_URL + "?Ric=VERS")
        results = [downloader.scarica_f24(page, str(year), f"01/01/{year}", f"31/12/{year}",
                   output / str(year), log=logs.append) for year in range(2020, 2027)]
        # Una seconda ricerca riconosce anche il modello P già salvato.
        repeated = downloader.scarica_f24(page, "2020", "01/01/2020", "31/12/2020",
                   output / "2020", log=logs.append)
    assert selected == filters == ["2020", "2021", "2022", "2024", "2025", "2026", "2020"]
    assert len(returns) == 7  # 2024 resta su VERS dopo il selettore assente del 2023.
    assert all((output / str(year)).is_dir() for year in range(2020, 2027))
    assert results[0].errors == 0, (attempts, logs)
    assert [result.downloaded for result in results] == [1, 1, 1, 0, 0, 1, 1]
    assert all(result.errors == 0 for result in results)
    assert results[0].models == 1 and results[3].unavailable_years == (2023,)
    assert results[4].empty_years == (2024,)
    assert len(list((output / "2020").glob("F24_modello_*.pdf"))) == 1
    assert repeated.skipped == 1 and repeated.downloaded == repeated.models == 0
    assert attempts[:2] == [("2020", "Q"), ("2020", "P")]
    assert any("Modello F24 salvato" in line for line in logs)
