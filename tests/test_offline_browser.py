"""Integrazione con Firefox reale; ogni richiesta è intercettata in locale."""
from urllib.parse import urlsplit, parse_qs
import pytest
from playwright.sync_api import sync_playwright
from src.f24_downloader import scarica_f24, download_pdf
from tests.test_pdf_files import quietanza


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.firefox.launch(headless=True)
        yield instance
        instance.close()


@pytest.mark.parametrize("new_tab", [False, True])
def test_two_result_pages_download_real_synthetic_pdfs(browser, tmp_path, monkeypatch, new_tab):
    from src import f24_downloader
    monkeypatch.setattr(f24_downloader, "wait_seconds", lambda *args: None)
    source = tmp_path / "fixture.pdf"
    quietanza(source)
    first = source.read_bytes()
    quietanza(source, "99,00")
    second = source.read_bytes()
    output = tmp_path / "output"
    visited = []
    selected_year = None
    with browser.new_context(accept_downloads=True) as context:
        page = context.new_page()

        def respond(route):
            nonlocal selected_year
            url = urlsplit(route.request.url)
            query = parse_qs(url.query)
            visited.append(url.path)
            if query.get("stampa") == ["Q"]:
                route.fulfill(status=200, content_type="application/pdf",
                    headers={"Content-Disposition": 'attachment; filename="quietanza.pdf"'},
                    body=second if query.get("indice") == ["2"] else first)
            elif query.get("Ric") == ["VERS"]:
                selected_year = None
                route.fulfill(status=200, content_type="text/html",
                    body='<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=F24&amp;Anno=2026" title="Documenti presenti">2026</a>')
            elif query.get("Ric") == ["F24"]:
                if "dataDal" not in query and "pagina" not in query:
                    selected_year = query["Anno"][0]
                assert selected_year == query["Anno"][0]
                number = "2" if query.get("pagina") == ["2"] else "1"
                next_link = ('' if number == "2" else
                    '<a rel="next" href="?Ric=F24&amp;Anno=2026&amp;pagina=2">Successiva</a>')
                body = ('<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=VERS">Versamenti</a><table><tbody><tr><td>F24</td><td><a href="/quietanza?indice='
                    + number + '&amp;stampa=Q">Quietanza</a></td></tr></tbody></table>' + next_link)
                route.fulfill(status=200, content_type="text/html", body=body)
            elif url.path == "/PortaleWeb/home":
                target = ' target="_blank"' if new_tab else ""
                html = ('<a href="https://cassetto.agenziaentrate.gov.it/CassHomeWeb/"' +
                        target + '>Vai al servizio</a>')
                route.fulfill(status=200, content_type="text/html", body=html)
            elif url.path == "/CassHomeWeb/":
                route.fulfill(status=200, content_type="text/html",
                    body='<a href="https://cassetto.agenziaentrate.gov.it/cassfisc-web">Vai a Consultazioni</a>')
            elif url.path == "/cassfisc-web":
                route.fulfill(status=200, content_type="text/html",
                    body='<a href="/cassfisc-web/CassettoFiscaleServlet?Ric=VERS" class="nav-link px-md-3">Versamenti</a>')
            else:
                route.abort()
                raise AssertionError("Richiesta sintetica non prevista")

        context.route("**/*", respond)
        page.goto("https://portale.agenziaentrate.gov.it/PortaleWeb/home")
        result = scarica_f24(page, "2026", "01/01/2026", "31/12/2026", output, log=lambda _: None)
        first_visits = list(visited)
        # Seconda sessione: il portale rigenera gli stessi documenti con byte diversi.
        first += b"\n% regenerated first quietanza\n"
        second += b"\n% regenerated second quietanza\n"
        page.goto("https://portale.agenziaentrate.gov.it/PortaleWeb/home")
        repeated = scarica_f24(page, "2026", "01/01/2026", "31/12/2026", output, log=lambda _: None)
    assert repeated.total == repeated.skipped == 2
    assert repeated.downloaded == repeated.errors == 0
    assert result.total == result.downloaded == 2
    assert result.errors == result.unclassified == 0
    assert len(list(output.glob("F24_*.pdf"))) == 2
    assert not list(output.glob(".f24-*"))
    assert first_visits.count("/quietanza") == 2
    assert first_visits[:4] == ["/PortaleWeb/home", "/CassHomeWeb/", "/cassfisc-web",
                           "/cassfisc-web/CassettoFiscaleServlet"]


def test_html_attachment_is_rejected_as_pdf(browser, tmp_path):
    with browser.new_context(accept_downloads=True) as context:
        page = context.new_page()
        page.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html",
            headers={"Content-Disposition": 'attachment; filename="quietanza.pdf"'}, body="Sessione scaduta"))
        with pytest.raises(RuntimeError, match="PDF valido"):
            download_pdf(page, "https://cassetto.agenziaentrate.gov.it/quietanza?stampa=Q", tmp_path / "invalid.pdf")


def test_confirmed_user_stays_on_home_without_reopening_reset_menu(browser, monkeypatch):
    from src import cambia_utenza
    monkeypatch.setattr(cambia_utenza, "wait_seconds", lambda *args: None)
    visits = []
    with browser.new_context() as context:
        page = context.new_page()
        def respond(route):
            url = urlsplit(route.request.url)
            visits.append(url.path)
            if url.path.endswith("/cambiautenza"):
                # Il selettore riparte da Personale ogni volta che viene aperto.
                html = """<form action="/PortaleWeb/home"><select id="utenza" name="utenza">
                    <option value="" selected>Personale</option>
                    <option value="DEMO123">Azienda demo</option></select>
                    <button type="submit">Conferma</button></form>"""
            else:
                assert parse_qs(url.query).get("utenza") == ["DEMO123"]
                html = "<p>Utenza selezionata confermata</p>"
            route.fulfill(status=200, content_type="text/html", body=html)
        page.route("**/*", respond)
        cambia_utenza.esegui_cambio_utenza(page, "DEMO123", log=lambda _: None)
        assert urlsplit(page.url).path == "/PortaleWeb/home"
        assert visits == ["/PortaleWeb/cambiautenza", "/PortaleWeb/home"]


def test_pdf_in_model_format_without_attachment_header_is_saved(browser, tmp_path, monkeypatch):
    from src import f24_downloader as downloader
    monkeypatch.setattr(downloader, "DOWNLOAD_TIMEOUT_SECONDS", 3)
    source = tmp_path / "fixture.pdf"
    quietanza(source)
    with browser.new_context(accept_downloads=True) as context:
        page = context.new_page()
        context.route("**/*", lambda route: route.fulfill(status=200,
            content_type="application/pdf", body=source.read_bytes()))
        target = tmp_path / "model.pdf"
        download_pdf(page, downloader.BASE_URL + "?stampa=P", target)
    assert target.read_bytes() == source.read_bytes()
