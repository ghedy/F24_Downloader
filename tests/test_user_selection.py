"""Scelta dell'utenza per identificativo fiscale: Firefox e dati sintetici."""
from urllib.parse import urlsplit, parse_qs
from unittest.mock import Mock
import pytest
from playwright.sync_api import sync_playwright
from src import cambia_utenza, ade_login


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.firefox.launch(headless=True)
        yield instance
        instance.close()


@pytest.mark.parametrize("requested,value,label", [
    ("01234567890", "TDEMO77", "01234567890 - 000"),
    ("demorss80a01h501x", "INTERNAL99", "DEMORSS80A01H501X - 000"),
    ("DEMORSS80A01H501X", "DEMORSS80A01H501X", "Profilo demo"),
    ("TDEMO77", "TDEMO77", "01234567890 - 000"),  # Rubrica preesistente.
])
def test_tax_identifier_selects_the_matching_internal_value(browser, monkeypatch, requested, value, label):
    monkeypatch.setattr(cambia_utenza, "wait_seconds", lambda *args: None)
    visits, logs = [], []
    with browser.new_context() as context:
        page = context.new_page()
        def respond(route):
            url = urlsplit(route.request.url)
            visits.append(url.path)
            if url.path.endswith("/cambiautenza"):
                # Ignorare un codice più lungo, una voce vuota e una disabilitata.
                html = ('<form action="/PortaleWeb/home"><select id="utenza" name="utenza">'
                        '<option value="" selected>Personale</option>'
                        '<option value="OTHER">X' + requested.upper() + 'X</option>'
                        '<option value="DISABLED" disabled>' + label + '</option>'
                        '<option value="' + value + '">' + label + '</option></select>'
                        '<button type="submit">Conferma</button></form>')
            else:
                assert parse_qs(url.query)["utenza"] == [value]
                html = "Utenza confermata"
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
        context.route("**/*", respond)
        cambia_utenza.esegui_cambio_utenza(page, requested, log=logs.append)
        assert urlsplit(page.url).path == "/PortaleWeb/home"
    assert visits == ["/PortaleWeb/cambiautenza", "/PortaleWeb/home"]
    assert all(requested.upper() not in line.upper() and value not in line for line in logs)


@pytest.mark.parametrize("options,message", [
    ('<option value="A">01234567890 - 000</option><option value="B">01234567890 - 001</option>',
     "più utenze"),
    ('<option value="A">901234567890</option>', "non disponibile"),
    ('<optgroup disabled><option value="A">01234567890 - 000</option></optgroup>', "non disponibile"),
    ('<option value="A" disabled>01234567890 - 000</option>', "non disponibile"),
])
def test_ambiguous_partial_or_disabled_matches_never_submit(browser, monkeypatch, options, message):
    monkeypatch.setattr(cambia_utenza, "wait_seconds", lambda *args: None)
    visits = []
    with browser.new_context() as context:
        page = context.new_page()
        def respond(route):
            visits.append(route.request.url)
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=
                '<form action="/PortaleWeb/home"><select id="utenza"><option value=""></option>' +
                options + '</select><button type="submit">Conferma</button></form>')
        context.route("**/*", respond)
        with pytest.raises(RuntimeError, match=message):
            cambia_utenza.esegui_cambio_utenza(page, "01234567890", log=lambda _: None)
        assert page.locator("#utenza").input_value() == ""
    assert len(visits) == 1


@pytest.mark.parametrize("method", ["CNS", "FISCONLINE", "PORTALE"])
def test_untested_login_methods_make_no_requests(method):
    page = Mock()
    with pytest.raises(ValueError, match="in attesa di collaudo"):
        ade_login.effettua_login(page, method, log=lambda _: None)
    page.goto.assert_not_called()
