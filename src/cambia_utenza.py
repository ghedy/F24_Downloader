"""Conferma il cambio utenza tramite il form del portale, senza riaprirlo."""
import re
from playwright.sync_api import TimeoutError as PWTimeout
from src.ade_login import is_portal_home
from src.models import check_cancel
from src.browser_wait import navigate, wait_seconds

CAMBIO_URL = "https://portale.agenziaentrate.gov.it/PortaleWeb/cambiautenza"

def risolvi_codice_utenza(options, codice_fiscale):
    """Trova il codice interno tramite l'identificativo fiscale visibile nel menu."""
    requested = codice_fiscale.strip().upper()
    token = re.compile(r"(?<![A-Z0-9])" + re.escape(requested) + r"(?![A-Z0-9])")
    available = [option for option in options if option.get("value") and not option.get("disabled")]
    labelled = {option["value"] for option in available
                if token.search(option.get("label", "").upper())}
    if len(labelled) == 1:
        return labelled.pop()
    if len(labelled) > 1:
        raise RuntimeError("Il codice fiscale o la partita IVA corrisponde a più utenze sul portale. "
                           "Impossibile scegliere automaticamente: controlla le posizioni autorizzate.")
    # Compatibilità con i codici interni già presenti nella rubrica locale.
    direct = {option["value"] for option in available if option["value"].upper() == requested}
    if len(direct) == 1:
        return direct.pop()
    raise RuntimeError("Utenza non disponibile tra quelle autorizzate per il codice fiscale o la partita IVA indicati. "
                       "Download interrotto.")


def esegui_cambio_utenza(page, utenza_codice, cancel=None, log=print):
    check_cancel(cancel)
    if not utenza_codice or not utenza_codice.strip():
        log("Profilo personale: nessun cambio utenza richiesto.")
        return
    check_cancel(cancel)
    log("Apertura della pagina Cambia utenza…")
    navigate(page, CAMBIO_URL, timeout=30_000, cancel=cancel)
    select = page.locator("#utenza")
    select.wait_for(state="visible", timeout=15_000)
    options = select.locator("option").evaluate_all("""items => items.map(item => ({
        value: item.value, label: item.label,
        disabled: item.disabled || !!item.parentElement.disabled
    }))""")
    codice_interno = risolvi_codice_utenza(options, utenza_codice)
    log("Utenza autorizzata individuata: selezione della posizione corrispondente…")
    selected = select.select_option(value=codice_interno)
    if selected != [codice_interno] or select.input_value() != codice_interno:
        raise RuntimeError("Selezione utenza non confermata. Download interrotto.")
    check_cancel(cancel)
    log("Invio della conferma dell'utenza selezionata…")
    page.locator('button[type="submit"]').click()
    try:
        page.wait_for_url(lambda url: is_portal_home(str(url)), timeout=30_000)
    except PWTimeout:
        raise RuntimeError("Il portale non è tornato alla pagina iniziale dopo la conferma utenza. "
                           "Controlla il messaggio visibile nel browser.") from None
    if not is_portal_home(page.url):
        raise RuntimeError("Ritorno al portale dopo il cambio utenza non confermato. Download interrotto.")
    log("Conferma utenza completata sul portale. Attendo la propagazione…")
    wait_seconds(page, 5, cancel)
    # Non riaprire il selettore: il suo valore iniziale non prova l'utenza attiva.
    log("Cambio utenza confermato; proseguo verso il Cassetto fiscale.")
