"""Accesso assistito: l'utente completa il secondo fattore, l'app prosegue come nel flusso originale."""
import time
from urllib.parse import urlsplit
from playwright.sync_api import TimeoutError as PWTimeout
from src.models import check_cancel, AVAILABLE_LOGIN_METHODS
from src.browser_wait import navigate, wait_seconds

PORTAL_HOSTS = {"portale.agenziaentrate.gov.it", "iampe.agenziaentrate.gov.it"}
LOGIN_URL = "https://iampe.agenziaentrate.gov.it/sam/UI/Login?realm=/agenziaentrate"

def is_portal_home(url):
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname in PORTAL_HOSTS
            and parsed.path.rstrip("/") == "/PortaleWeb/home")

def _visible(page, selector):
    locator = page.locator(selector).first
    return locator if locator.is_visible() else None

def _advance_sielte(page, completed, log):
    if "consent" in completed:
        return
    # Non leggere né registrare il codice OTP: controllare solo che sia completo.
    otp = _visible(page, "input#password")
    submit = _visible(page, "button#autorizza")
    if otp is not None and submit is not None:
        if "otp" not in completed and otp.evaluate(r"el => /^\d{6}$/.test(el.value)"):
            submit.click(timeout=1500)
            completed.add("otp")
            log("Secondo fattore inserito: conferma inviata.")
        return
    app_link = _visible(page, 'a[onclick="useAPP()"]')
    if otp is None and app_link is not None and "app" not in completed:
        app_link.click(timeout=1500)
        completed.add("app")
        log("Inserisci nel browser il codice generato dall'app MySielteID.")
        return
    consent = _visible(page, 'button[type="submit"]:has-text("Autorizza")')
    if consent is not None:
        consent.click(timeout=1500)
        completed.add("consent")
        log("Conferma finale Autorizza inviata. Attendo il rientro in AdE.")

def _advance_cie(page, completed, log):
    if "consent" in completed:
        return
    consent = _visible(page, 'button[name="_eventId_proceed"]')
    if consent is not None:
        consent.click(timeout=1500)
        completed.add("consent")
        log("Conferma finale Prosegui inviata. Attendo il rientro in AdE.")

def effettua_login(page, metodo, provider=None, credenziali=None,
                   automatico=False, cancel=None, log=print, timeout=240):
    if metodo not in AVAILABLE_LOGIN_METHODS:
        raise ValueError("Metodo di accesso non ancora disponibile: in attesa di collaudo.")
    credentials = credenziali or {}
    targets = {
        "SPID": "https://sp.agenziaentrate.gov.it/rp/sielte/sel",
        "CIE": "https://sp.agenziaentrate.gov.it/rp/cie/sel",
        "CNS": "https://cns.agenziaentrate.gov.it/pi",
        "FISCONLINE": LOGIN_URL, "PORTALE": LOGIN_URL,
    }
    if metodo not in targets or (metodo == "SPID" and provider != "sielte"):
        raise ValueError("Metodo di accesso non supportato")
    navigate(page, targets[metodo], timeout=60_000, cancel=cancel)
    if automatico:
        if metodo not in {"SPID", "CIE"}:
            raise ValueError("Per questo metodo completa l'accesso nel browser.")
        if not credentials.get("username") or not credentials.get("password"):
            raise ValueError("Inserisci nome utente e password oppure usa l'accesso manuale.")
        page.locator("#username").fill(credentials["username"])
        page.locator("#password").fill(credentials["password"])
        if metodo == "SPID":
            page.get_by_text("Prosegui", exact=True).click()
        else:
            page.locator('button[type="submit"]:has-text("Procedi")').click()
    if metodo in {"SPID", "CIE"}:
        log("Completa il secondo fattore nel browser o nell'app. Le conferme successive sono automatiche.")
    else:
        log("Completa autenticazione e consenso nel browser (entro 4 minuti).")
    deadline = time.monotonic() + timeout
    completed = set()
    while time.monotonic() < deadline:
        check_cancel(cancel)
        if is_portal_home(page.url):
            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            log("Accesso completato. Attendo la stabilizzazione della sessione AdE…")
            wait_seconds(page, 5, cancel)
            return
        try:
            if metodo == "SPID":
                _advance_sielte(page, completed, log)
            elif metodo == "CIE":
                _advance_cie(page, completed, log)
        except PWTimeout:
            # Un controllo può sparire durante un redirect: rivalutare la nuova pagina.
            pass
        page.wait_for_timeout(250)
    raise RuntimeError("Accesso non completato entro 4 minuti. Avvia una nuova sessione.")
