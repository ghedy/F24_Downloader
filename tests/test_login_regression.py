"""Regressioni del login: Firefox reale, pagine e OTP esclusivamente sintetici."""
from threading import Event
import pytest
from playwright.sync_api import sync_playwright
from src import ade_login
from src.models import Cancelled

@pytest.fixture(scope="module")
def login_browser():
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=True)
        yield browser
        browser.close()

@pytest.mark.parametrize("method,automatic", [("SPID", True), ("SPID", False), ("CIE", False)])
def test_original_login_sequence_reaches_portal(login_browser, monkeypatch, method, automatic):
    monkeypatch.setattr(ade_login, "wait_seconds", lambda *args: None)
    home = "https://portale.agenziaentrate.gov.it/PortaleWeb/home"
    consent = ('<form action="' + home + '"><button type="submit" ' +
               ('name="_eventId_proceed">Prosegui' if method == "CIE" else '>Autorizza') +
               '</button></form>')
    initial = consent
    if automatic:
        initial = """
        <input id="username"><input id="password" type="password">
        <button type="button" onclick="showOtp()">Prosegui</button>
        <script>
        function showOtp() {
            document.body.innerHTML = '<input id="password"><button id="autorizza" onclick="showConsent()">Prosegui</button>';
            setTimeout(() => document.getElementById('password').value = '123456', 150);
        }
        function showConsent() {
            document.body.innerHTML = CONSENT;
        }
        </script>
        """.replace("CONSENT", repr(consent))
    seen = []
    logs = []
    with login_browser.new_context() as context:
        page = context.new_page()
        def respond(route):
            seen.append(route.request.url)
            route.fulfill(status=200, content_type="text/html",
                          body="Portale sintetico" if "/PortaleWeb/home" in route.request.url else initial)
        page.route("**/*", respond)
        ade_login.effettua_login(page, method, "sielte",
            {"username": "demo-user", "password": "demo-password"},
            automatico=automatic, log=logs.append, timeout=10)
        assert ade_login.is_portal_home(page.url)
        assert any("Conferma finale" in message for message in logs)
        assert not any("123456" in message or "demo-password" in message for message in logs)
        if automatic:
            assert any("Secondo fattore inserito" in message for message in logs)

def test_incomplete_otp_is_not_submitted_even_if_button_says_autorizza(login_browser):
    with login_browser.new_context() as context:
        page = context.new_page()
        page.set_content("""<input id="password" value="12345">
            <button type="submit" id="autorizza" onclick="window.submitted=true">Autorizza</button>
            <script>window.submitted=false;</script>""")
        completed = set()
        ade_login._advance_sielte(page, completed, lambda _: None)
        assert page.evaluate("window.submitted") is False
        assert completed == set()

def test_app_otp_option_is_selected_as_in_original(login_browser):
    with login_browser.new_context() as context:
        page = context.new_page()
        page.set_content("""<a onclick="useAPP()">Usa codice OTP</a>
            <script>window.selected=false;function useAPP(){window.selected=true;}</script>""")
        completed = set()
        ade_login._advance_sielte(page, completed, lambda _: None)
        assert page.evaluate("window.selected") is True
        assert completed == {"app"}

def test_cancellation_remains_possible_during_login(login_browser):
    with login_browser.new_context() as context:
        page = context.new_page()
        page.route("**/*", lambda route: route.fulfill(status=200,
            content_type="text/html", body="<p>Attesa del secondo fattore</p>"))
        cancel = Event()
        def stop_after_prompt(_):
            cancel.set()
        with pytest.raises(Cancelled):
            ade_login.effettua_login(page, "SPID", "sielte", cancel=cancel,
                                    log=stop_after_prompt, timeout=10)
