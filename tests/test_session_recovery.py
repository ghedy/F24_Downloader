"""Regressioni Firefox locali: CICS, stampa P e cambio dell'anno."""
from urllib.parse import urlsplit, parse_qs
import pytest
from playwright.sync_api import sync_playwright
from src import f24_downloader as downloader
from tests.test_pdf_files import quietanza

CICS_ERROR = """<div class="row py-3"><div class="notification alert alert-danger" role="alert">
<h3>Attenzione</h3>Problemi di collegamento col CICS: ABEND - IUWX
<p>Si è verificato un errore interno</p><p>E' possibile tentare il rispristino della sessione utente
<a href="/cassfisc-web/CassettoFiscaleServlet">Ripristina il cassetto fiscale</a></p></div></div>"""
MENU = '<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=VERS" data-toggle="collapse" onclick="event.preventDefault()">Versamenti</a>'

@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.firefox.launch(headless=True)
        yield instance
        instance.close()


@pytest.mark.parametrize("failure", ["message", "timeout"])
@pytest.mark.parametrize("break_at", ["year", "period", "q", "p"])
def test_print_and_cics_recovery_preserve_document_and_next_year(browser, tmp_path, monkeypatch, failure, break_at):
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    monkeypatch.setattr(downloader, "DOWNLOAD_TIMEOUT_SECONDS", 0.8)
    fixture = tmp_path / "fixture.pdf"
    quietanza(fixture)
    pdf = fixture.read_bytes()
    events, logs = [], []
    print_mode, broken, error_injected = False, False, False
    with browser.new_context(accept_downloads=True) as context:
        page = context.new_page()
        def respond(route):
            nonlocal print_mode, broken, error_injected
            url = urlsplit(route.request.url)
            query = parse_qs(url.query)
            def html(body):
                route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)
            def inject(where):
                nonlocal broken, error_injected
                if where == break_at and not error_injected:
                    broken = error_injected = True
                    html(CICS_ERROR)
                    return True
                return False
            if url.path == "/cassfisc-web/print":
                kind, year = query["stampa"][0], query["year"][0]
                events.append((kind, year))
                if broken:
                    html(CICS_ERROR)
                elif year == "2025" and kind == "Q":
                    if inject("q"):
                        return
                    if break_at == "q" and error_injected:
                        route.fulfill(status=200, content_type="application/pdf",
                            headers={"Content-Disposition": "attachment"}, body=pdf)
                    else:
                        message = ("La delega richiesta non e' stampabile nel formato QUIETANZA"
                                   if failure == "message" else "Documento non ricevuto")
                        html("<p>" + message + "</p>")
                elif kind == "P":
                    if inject("p"):
                        return
                    print_mode = True
                    route.fulfill(status=200, content_type="application/pdf",
                        headers={"Content-Disposition": "attachment"}, body=pdf)
                else:
                    route.fulfill(status=200, content_type="application/pdf",
                        headers={"Content-Disposition": "attachment"}, body=pdf)
            elif not url.query:
                assert url.path == "/cassfisc-web/CassettoFiscaleServlet"
                events.append(("main", ""))
                broken = print_mode = False
                html(MENU)
            elif query.get("Ric") == ["VERS"]:
                events.append(("vers", ""))
                if broken or print_mode:
                    html(CICS_ERROR)
                else:
                    html(MENU + ''.join(f'<a href="?Ric=F24&amp;Anno={year}">{year}</a>' for year in (2025, 2026)))
            elif query.get("Ric") == ["F24"]:
                year = query["Anno"][0]
                event = "period" if "dataDal" in query else "year"
                events.append((event, year))
                if year == "2026" and inject(event):
                    return
                if broken or print_mode:
                    html(CICS_ERROR)
                else:
                    if event == "period":
                        assert query["dataDal"] == [f"01/01/{year}"]
                        assert query["dataAl"] == [f"31/12/{year}"]
                    html(MENU + '<table><tbody><tr><td><a href="/cassfisc-web/print?year=' + year +
                         '&amp;stampa=Q">Quietanza</a></td></tr></tbody></table>')
            else:
                route.abort()
                raise AssertionError("Richiesta non prevista")
        context.route("**/*", respond)
        page.goto(downloader.BASE_URL + "?Ric=VERS")
        results = [downloader.scarica_f24(page, str(year), f"01/01/{year}", f"31/12/{year}",
                   tmp_path / str(year), log=logs.append) for year in (2025, 2026)]
    assert error_injected
    assert all(result.downloaded == 1 and result.errors == 0 for result in results), logs
    assert results[0].models == (0 if break_at == "q" else 1)
    assert results[1].models == 0
    assert events.count(("main", "")) == 2
    assert any("Ripristina il cassetto fiscale" in line for line in logs)
    assert any("Ritorno alla pagina principale" in line for line in logs)
    if break_at == "q":
        assert ("P", "2025") not in events  # Ripristinare prima di riprovare Q.
    else:
        assert ("P", "2025") in events
        assert len(list((tmp_path / "2025").glob("F24_modello_*.pdf"))) == 1
    assert len(list((tmp_path / "2026").glob("F24_*.pdf"))) == 1


def test_persistent_cics_error_is_bounded_and_not_reported_as_missing_year(browser, monkeypatch):
    monkeypatch.setattr(downloader, "wait_seconds", lambda *args: None)
    visits = []
    with browser.new_context() as context:
        page = context.new_page()
        def respond(route):
            visits.append(route.request.url)
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=CICS_ERROR)
        context.route("**/*", respond)
        page.goto(downloader.BASE_URL + "?Ric=VERS")
        with pytest.raises(downloader.SessionRestoreFailed, match="3 tentativi"):
            downloader.apri_cassetto_e_scegli_date(page, "2026", log=lambda _: None)
    assert len(visits) == 3  # Una visita iniziale e due ripristini.
    assert visits[1:] == [downloader.BASE_URL, downloader.BASE_URL]


def test_restore_link_cannot_send_browser_outside_cassetto(browser):
    visits = []
    with browser.new_context() as context:
        page = context.new_page()
        def respond(route):
            visits.append(route.request.url)
            route.fulfill(status=200, content_type="text/html", body=
                '<a href="https://example.invalid/reset">Ripristina il cassetto fiscale</a>')
        context.route("**/*", respond)
        page.goto(downloader.BASE_URL)
        with pytest.raises(ValueError, match="esterno"):
            downloader.ripristina_cassetto(page, log=lambda _: None)
    assert visits == [downloader.BASE_URL]


@pytest.mark.parametrize("message", [
    "La delega richiesta non è stampabile nel formato QUIETANZA",
    "La delega richiesta non e' stampabile nel formato QUIETANZA",
    "La delega richiesta non e’ stampabile nel formato QUIETANZA",
    "La delega richiesta non &egrave; stampabile nel formato QUIETANZA",
    'La delega non è stampabile nel formato \"QUIETANZA\"',
])
def test_quietanza_rejection_variants(message):
    assert downloader._quietanza_not_printable(message)
