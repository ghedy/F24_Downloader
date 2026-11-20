"""Download sequenziale di quietanze, con URL verificati e PDF validati."""
import tempfile
import re
import time
import html
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit, parse_qsl, urlencode, urlunsplit
from playwright.sync_api import TimeoutError as PWTimeout, Error as PWError
from src.models import DownloadResult, check_cancel, Cancelled
from src.browser_wait import navigate, wait_seconds
from src.rinomina_f24 import processa_nuovo_file
from src.destination import prepare_destination

BASE_URL = "https://cassetto.agenziaentrate.gov.it/cassfisc-web/CassettoFiscaleServlet"
CASSETTO_HOME_URL = "https://cassetto.agenziaentrate.gov.it/CassHomeWeb/"
SECTION_TITLES = {"F24": "F24 ordinari", "VXX": "Altre disposizioni di pagamento", "F23": "F23"}

def safe_url(href, base=BASE_URL):
    url = urljoin(base, href)
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname != "cassetto.agenziaentrate.gov.it"
            or parts.username or parts.password or parts.port not in (None, 443)):
        raise ValueError("Collegamento di download esterno al Cassetto fiscale rifiutato.")
    return url

def get_pdf_url_from_detail(detail_url, stampa="Q"):
    if stampa not in {"Q", "P"}:
        raise ValueError("Formato di stampa non supportato.")
    parts = urlsplit(safe_url(detail_url))
    query = [(key, value) for key, value in parse_qsl(parts.query) if key != "stampa"]
    query.append(("stampa", stampa))
    return urlunsplit(parts._replace(query=urlencode(query)))

def list_url(anno, dal="", al=""):
    return _with_period(BASE_URL + "?" + urlencode({"Ric": "F24", "Anno": anno}), dal, al)


def _with_period(url, dal, al):
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
             if key not in {"dataDal", "dataAl"}]
    query.extend((("dataDal", dal), ("dataAl", al)))
    return urlunsplit(parts._replace(query=urlencode(query)))

def _is_cassetto(url):
    if not isinstance(url, str):
        return False
    parsed = urlsplit(url)
    return (parsed.scheme == "https" and parsed.hostname == "cassetto.agenziaentrate.gov.it"
            and parsed.path.startswith("/CassHomeWeb/"))

def _is_consultazioni(url):
    parsed = urlsplit(str(url))
    return (parsed.scheme == "https" and parsed.hostname == "cassetto.agenziaentrate.gov.it"
            and (parsed.path == "/cassfisc-web" or parsed.path.startswith("/cassfisc-web/")))

def _is_versamenti(url):
    return _is_consultazioni(url) and ("Ric", "VERS") in parse_qsl(urlsplit(str(url)).query)

def _click_service_link(page, selector, destination, title, cancel=None, log=print):
    check_cancel(cancel)
    log(f"Click su {title}…")
    link = (page.locator(selector) if isinstance(selector, str) else selector).first
    try:
        link.wait_for(state="visible", timeout=15_000)
    except PWTimeout:
        raise RuntimeError(f"Collegamento {title} non trovato. Controlla la pagina visibile nel browser.") from None
    check_cancel(cancel)
    if link.get_attribute("target") == "_blank":
        with page.expect_popup(timeout=30_000) as popup:
            link.click()
        opened = popup.value
    else:
        link.click()
        opened = page
    opened.wait_for_url(lambda url: destination(str(url)), timeout=60_000)
    opened.wait_for_load_state("domcontentloaded", timeout=30_000)
    check_cancel(cancel)
    log(f"Passaggio completato: {title}.")
    return opened

def apri_servizio_cassetto(page, cancel=None, log=print):
    if _is_cassetto(page.url) or _is_consultazioni(page.url):
        return page
    return _click_service_link(page, f'a[href="{CASSETTO_HOME_URL}"]',
        _is_cassetto, "Vai al servizio del Cassetto fiscale", cancel, log)

def apri_consultazioni_e_versamenti(page, cancel=None, log=print):
    _check_session(page)
    if not _is_consultazioni(page.url):
        page = _click_service_link(page,
            'a[href="https://cassetto.agenziaentrate.gov.it/cassfisc-web"]',
            _is_consultazioni, "Vai a Consultazioni", cancel, log)
    if not _is_versamenti(page.url):
        # Il menu del portale intercetta il click con data-toggle="collapse".
        # Aprire l'indirizzo del servizio ripristina anche la scelta dell'anno.
        log("Apertura di Versamenti e del selettore degli anni…")
        navigate(page, BASE_URL + "?Ric=VERS", cancel=cancel)
        page.wait_for_url(lambda url: _is_versamenti(str(url)), timeout=30_000)
        check_cancel(cancel)
        log("Passaggio completato: Versamenti.")
    _check_session(page)
    return page

class YearNotAvailable(Exception):
    pass

def _empty_result(text):
    normalized = re.sub(r"\s+", " ", text).lower()
    return any(message in normalized for message in (
        "nessun versamento", "nessuna quietanza", "nessun dato",
        "non risultano versamenti", "nessuna occorrenza",
        "nessuna disposizione", "non risultano disposizioni", "nessun pagamento", "non risultano pagamenti"))

class SessionNeedsRestore(RuntimeError):
    pass


class SessionRestoreFailed(RuntimeError):
    pass


SESSION_ATTEMPTS = 3


def _normalized_text(text):
    text = html.unescape(text).casefold().replace("’", "'")
    text = "".join(character for character in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", text).strip()


def _needs_restore(text):
    normalized = _normalized_text(text)
    return any(message in normalized for message in (
        "deve essere ripristinata", "necessario ripristino",
        "problemi di collegamento col cics", "abend - iuwx",
        "ripristino della sessione utente", "rispristino della sessione utente"))


def _check_session(page, text=None):
    if _needs_restore(text if text is not None else page.locator("body").inner_text(timeout=5_000)):
        raise SessionNeedsRestore("Il Cassetto fiscale richiede il ripristino della sessione.")


def ripristina_cassetto(page, cancel=None, log=print):
    check_cancel(cancel)
    target = BASE_URL
    for link in page.locator("a[href]").all():
        title = _normalized_text(link.inner_text())
        if "ripristina" not in title or "cassetto fiscale" not in title:
            continue
        candidate = safe_url(link.get_attribute("href") or "", page.url)
        parsed = urlsplit(candidate)
        if parsed.path != urlsplit(BASE_URL).path or parsed.query or parsed.fragment:
            raise ValueError("Collegamento di ripristino del Cassetto fiscale non riconosciuto.")
        target = candidate
        break
    log("Ripristina il cassetto fiscale: apertura della pagina principale…")
    navigate(page, target, timeout=30_000, cancel=cancel)
    wait_seconds(page, 3, cancel)
    return page


def _return_to_main(url):
    if not isinstance(url, str):
        return False
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "cassetto.agenziaentrate.gov.it":
        return False
    if _is_cassetto(url) or _is_versamenti(url) or parts.path == "/cassfisc-web":
        return False
    return parts.path != urlsplit(BASE_URL).path or bool(parts.query)


CAROUSEL_WAIT_SECONDS = 8
CAROUSEL_MAX_STEPS = 64

def _year_link_visible(link):
    if not link.is_visible():
        return False
    # Un elemento traslato fuori da un contenitore overflow:hidden può risultare
    # comunque "visible" per Playwright. Verificare il centro nel riquadro anni.
    return link.evaluate("""element => {
        const frame = element.closest('.carousel-inner') || element.closest('#service-slider');
        if (!frame) return true;
        const item = element.getBoundingClientRect(), area = frame.getBoundingClientRect();
        const x = item.left + item.width / 2, y = item.top + item.height / 2;
        return item.width > 0 && item.height > 0 &&
            x >= area.left && x <= area.right && y >= area.top && y <= area.bottom;
    }""")

def _visible_year_link(page, anno, section):
    present = False
    for link in page.locator(f'a[href*="Ric={section}"][href*="Anno={anno}"]').all():
        href = link.get_attribute("href") or ""
        query = dict(parse_qsl(urlsplit(safe_url(href, page.url)).query))
        if query.get("Ric") != section or query.get("Anno") != str(anno):
            continue
        present = True
        if _year_link_visible(link):
            return link, present
    return None, present

def _carousel_state(page):
    carousel = page.locator("#service-slider").first
    if not carousel.count():
        return None
    return carousel.evaluate("""root => {
        const items = [...root.querySelectorAll('.carousel-item, .item')];
        const active = items.flatMap((item, index) => item.classList.contains('active') ? [index] : []);
        const indicators = [...root.querySelectorAll('.carousel-indicators .active')]
            .map(item => item.getAttribute('data-slide-to') || item.getAttribute('data-bs-slide-to') || '');
        const frame = root.querySelector('.carousel-inner') || root;
        const area = frame.getBoundingClientRect();
        const visible = [...root.querySelectorAll('a[href*="Ric="][href*="Anno="]')]
            .filter(item => {
                const style = getComputedStyle(item), rect = item.getBoundingClientRect();
                const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
                return style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 &&
                    x >= area.left && x <= area.right && y >= area.top && y <= area.bottom;
            }).map(item => item.getAttribute('href')).sort();
        const busy = !!root.querySelector(
            '.carousel-item-next, .carousel-item-prev, .carousel-item-left, .carousel-item-right, ' +
            '.carousel-item-start, .carousel-item-end, .item.next, .item.prev, .item.left, .item.right');
        return {key: JSON.stringify([active, indicators, visible]), busy, slides: items.length};
    }""")

def _wait_carousel(page, previous=None, cancel=None):
    import time
    deadline = time.monotonic() + CAROUSEL_WAIT_SECONDS
    while time.monotonic() < deadline:
        check_cancel(cancel)
        state = _carousel_state(page)
        if state is None:
            raise RuntimeError("Il carosello degli anni non è più disponibile.")
        if not state["busy"] and (previous is None or state["key"] != previous):
            return state
        page.wait_for_timeout(100)
    raise RuntimeError("Il carosello degli anni non ha completato lo scorrimento. "
                       "Controlla la pagina visibile nel browser.")

def _carousel_control(page, direction):
    selector = (
        f'#service-slider .carousel-control-{direction}, '
        f'[href="#service-slider"][data-slide="{direction}"], '
        f'[data-target="#service-slider"][data-slide="{direction}"]')
    for control in page.locator(selector).all():
        if not control.is_visible():
            continue
        classes = (control.get_attribute("class") or "").split()
        if (control.get_attribute("aria-disabled") == "true" or
                control.get_attribute("disabled") is not None or "disabled" in classes):
            continue
        # aria-hidden=true è presente anche nei pulsanti funzionanti del portale.
        return control
    return None

def _find_year_in_carousel(page, anno, cancel=None, log=print, *, section="F24"):
    initial = _carousel_state(page)
    if initial is None:
        return _visible_year_link(page, anno, section)
    _wait_carousel(page, cancel=cancel)
    present = False
    for direction, title in (("next", "Anni successivi"), ("prev", "Anni precedenti")):
        visited = set()
        for _ in range(CAROUSEL_MAX_STEPS):
            check_cancel(cancel)
            state = _wait_carousel(page, cancel=cancel)
            link, found = _visible_year_link(page, anno, section)
            present = present or found
            if link is not None:
                return link, present
            if state["key"] in visited:
                log(f"Anno {anno}: giro completo del carosello, ricerca conclusa.")
                return None, present
            visited.add(state["key"])
            if state["slides"] == 1:
                break
            control = _carousel_control(page, direction)
            if control is None:
                break
            log(f"Anno {anno} non visibile: scorro {title}.")
            check_cancel(cancel)
            control.click(timeout=5_000)
            _wait_carousel(page, previous=state["key"], cancel=cancel)
        else:
            raise RuntimeError("Troppi scorrimenti del carosello: ricerca degli anni interrotta.")
    return None, present

def seleziona_anno(page, anno, cancel=None, log=print, *, section="F24"):
    check_cancel(cancel)
    _check_session(page)
    chosen, present = _find_year_in_carousel(page, anno, cancel=cancel, log=log, section=section)
    if chosen is None:
        text = page.locator("body").inner_text(timeout=5_000).lower()
        _check_session(page, text)
        expected = "VERS" if section == "F24" else section
        if not (_is_consultazioni(page.url) and ("Ric", expected) in parse_qsl(urlsplit(page.url).query)):
            raise RuntimeError("Pagina di selezione anni non riconosciuta.")
        if section != "F24" and not (
                SECTION_TITLES[section].casefold() in _normalized_text(text) or _empty_result(text)
                or page.locator(f'a[href*="Ric={section}"][href*="Anno="]').count()):
            raise RuntimeError(f"{SECTION_TITLES[section]}: selettore anni non riconosciuto.")
        if present:
            raise RuntimeError(f"Il collegamento dell'anno {anno} è presente ma resta nascosto dopo lo scorrimento.")
        raise YearNotAvailable(str(anno))
    # Usare proprio il collegamento visibile trovato, anche se esistono copie
    # nascoste dello stesso href in altri pannelli.
    return _click_service_link(page, chosen,
        lambda url: _is_consultazioni(url)
            and dict(parse_qsl(urlsplit(url).query)).get("Ric") == section
            and dict(parse_qsl(urlsplit(url).query)).get("Anno") == str(anno),
        f"anno {anno}", cancel, log)

def apri_cassetto_e_scegli_date(page, anno, dal="", al="", cancel=None, log=print, *, section="F24"):
    check_cancel(cancel)
    log("Apertura del Cassetto fiscale…")
    for attempt in range(1, SESSION_ATTEMPTS + 1):
        try:
            _check_session(page)
            if section == "F24" and _return_to_main(page.url):
                log("Ritorno alla pagina principale del Cassetto fiscale prima della scelta dell'anno…")
                navigate(page, BASE_URL, cancel=cancel)
                _check_session(page)
            page = apri_servizio_cassetto(page, cancel=cancel, log=log)
            if attempt == 1 and section == "F24":
                wait_seconds(page, 3, cancel)
            if section != "F24":
                if not _is_consultazioni(page.url):
                    page = apri_consultazioni_e_versamenti(page, cancel=cancel, log=log)
                navigate(page, BASE_URL + f"?Ric={section}", cancel=cancel)
                page = seleziona_anno(page, anno, cancel=cancel, log=log, section=section)
                period_url = _with_period(safe_url(page.url), dal, al)
            else:
                page = apri_consultazioni_e_versamenti(page, cancel=cancel, log=log)
                page = seleziona_anno(page, anno, cancel=cancel, log=log)
                period_url = list_url(anno, dal, al)
            _check_session(page)
            log("Ricerca delle quietanze per anno e periodo…")
            navigate(page, period_url, timeout=60_000, cancel=cancel)
            text = page.locator("body").inner_text(timeout=5_000)
            _check_session(page, text)
            if _empty_result(text):
                return page
            try:
                page.locator("table tbody tr").first.wait_for(timeout=15_000)
            except PWTimeout:
                check_cancel(cancel)
                text = page.locator("body").inner_text(timeout=5_000)
                _check_session(page, text)
                if _empty_result(text):
                    return page
                raise RuntimeError(f"Elenco {SECTION_TITLES[section]} non riconosciuto: verifica sessione, utenza e disponibilità del servizio.") from None
            log(f"Elenco {SECTION_TITLES[section]} caricato.")
            return page
        except SessionNeedsRestore:
            if attempt == SESSION_ATTEMPTS:
                raise SessionRestoreFailed("Impossibile ripristinare la sessione del Cassetto fiscale dopo 3 tentativi.") from None
            log(f"Errore di sessione del Cassetto fiscale. Ripristino {attempt}/{SESSION_ATTEMPTS - 1} e nuova selezione dell'anno {anno}…")
            page = ripristina_cassetto(page, cancel=cancel, log=log)


def collect_rows(page, anno="", dal="", al=""):
    rows = []
    for tr in page.query_selector_all("table tbody tr"):
        hrefs = [link.get_attribute("href") or "" for link in tr.query_selector_all("a")]
        direct = next((href for href in hrefs if "stampa=Q" in href), None)
        detail = next((href for href in hrefs if "DetF24" in href), None)
        if direct or detail:
            rows.append({"url": safe_url(direct or detail, page.url),
                         "tipo": "direct" if direct else "detail"})
    return rows

def _link_label(link):
    return _normalized_text(" ".join(
        [link.inner_text(), link.get_attribute("title") or "", link.get_attribute("aria-label") or ""]
        + [image.get_attribute("alt") or "" for image in link.locator("img[alt]").all()]))


def _is_print_link(parts, query, label):
    return (query.get("stampa") in {"Q", "P"} or parts.path.lower().endswith(".pdf")
            or bool(re.search(r"\bpdf\b", label)))


def _collect_payment_details(page, section):
    for row in page.locator("table tbody tr").all():
        direct = None
        for link in row.locator("a[href]").all():
            href = link.get_attribute("href") or ""
            if not href or href.startswith(("#", "javascript:")):
                continue
            parts = urlsplit(href)
            query = dict(parse_qsl(parts.query))
            label = _link_label(link)
            if section == "F23" and _is_print_link(parts, query, label):
                if direct is None or query.get("stampa") == "Q":
                    direct = href
            elif "stampa" not in query and (
                    query.get("Ric", "").casefold().startswith("det") or "dettaglio" in label):
                yield {"url": safe_url(href, page.url), "tipo": "detail"}
                break
        else:
            if direct:
                yield {"url": safe_url(direct, page.url), "tipo": "direct"}


def collect_all_rows(page, anno, dal, al, cancel=None, *, section="F24"):
    rows, seen, pages = [], set(), set()
    for _ in range(100):
        check_cancel(cancel)
        if page.url in pages:
            raise RuntimeError("Paginazione ciclica: ricerca interrotta per evitare un risultato incompleto.")
        pages.add(page.url)
        listed = (collect_rows(page, anno, dal, al) if section == "F24"
                  else _collect_payment_details(page, section))
        for row in listed:
            if section == "F24":
                row = {"url": get_pdf_url_from_detail(row["url"]), "tipo": "direct"}
            if row["url"] not in seen:
                seen.add(row["url"])
                rows.append(row)
        next_links = page.locator('a[rel="next"], a').all()
        next_url = None
        for link in next_links:
            label = (link.inner_text() or "").strip().lower()
            title = (link.get_attribute("title") or "").lower()
            if (link.get_attribute("rel") == "next" or label in {">", ">>", "successiva", "avanti", "pagina successiva"}
                    or title == "pagina successiva"):
                if link.get_attribute("aria-disabled") == "true":
                    continue
                href = link.get_attribute("href")
                if href and not href.startswith(("#", "javascript:")):
                    next_url = safe_url(href, page.url)
                    break
        if not next_url:
            # Una paginazione solo numerica richiede un adattamento al portale:
            # non dichiarare mai completo un elenco potenzialmente parziale.
            for link in next_links:
                if (link.inner_text() or "").strip().isdigit():
                    href = link.get_attribute("href") or ""
                    if any(token in href.lower() for token in ("pagina=", "page=", "offset=")):
                        raise RuntimeError("Paginazione numerica da verificare: nessun download avviato.")
            return rows
        page.goto(next_url, wait_until="domcontentloaded", timeout=30_000)
        page.locator("table tbody tr").first.wait_for(timeout=15_000)
    raise RuntimeError("Elenco superiore a 100 pagine: ricerca interrotta.")

class QuietanzaNotPrintable(RuntimeError):
    """Il portale rifiuta esplicitamente la stampa Q per questa delega."""


def _quietanza_not_printable(text):
    normalized = _normalized_text(text)
    return bool(re.search(r"delega (?:richiesta )?non e'? stampabile nel formato (?:di )?[\"'«]?quietanza", normalized))


DOWNLOAD_TIMEOUT_SECONDS = 20


def download_pdf(page, url, dest_path):
    url = safe_url(url)
    is_quietanza = ("stampa", "Q") in parse_qsl(urlsplit(url).query)
    downloads = []
    navigated = False
    def on_navigation(frame):
        nonlocal navigated
        if frame == page.main_frame:
            navigated = True
    def on_download(download):
        downloads.append(download)
    page.on("download", on_download)
    page.on("framenavigated", on_navigation)
    try:
        deadline = time.monotonic() + DOWNLOAD_TIMEOUT_SECONDS
        page.evaluate("url => { window.location.href = url; }", url)
        while not downloads:
            if time.monotonic() >= deadline:
                raise PWTimeout("Attesa download scaduta.")
            page.wait_for_timeout(100)
            # Leggere soltanto il nuovo documento, mai un precedente errore Q.
            if navigated and not downloads:
                try:
                    text = page.locator("body").inner_text(timeout=500)
                except PWError:
                    continue
                _check_session(page, text)
                if is_quietanza and _quietanza_not_printable(text):
                    raise QuietanzaNotPrintable("Delega non stampabile nel formato quietanza.")
        downloads[0].save_as(str(dest_path))
        with Path(dest_path).open("rb") as stream:
            header = stream.read(5)
            if header != b"%PDF-":
                text = (header + stream.read(65_536)).decode("utf-8", errors="replace")
                _check_session(page, text)
                if is_quietanza and _quietanza_not_printable(text):
                    raise QuietanzaNotPrintable("Delega non stampabile nel formato quietanza.")
                raise RuntimeError("Il portale non ha restituito un PDF valido.")
    finally:
        page.remove_listener("download", on_download)
        page.remove_listener("framenavigated", on_navigation)


def _payment_pdf_url(page, detail_url, cancel, section):
    navigate(page, detail_url, cancel=cancel)
    detail_url = safe_url(page.url)
    _check_session(page)
    selector = "a[href]" if section == "F23" else 'a[href*="stampa=Q"]'
    fallback = None
    for link in page.locator(selector).all():
        href = link.get_attribute("href") or ""
        if not href or href.startswith(("#", "javascript:")):
            continue
        parts = urlsplit(href)
        query = dict(parse_qsl(parts.query))
        if query.get("stampa") == "Q":
            return safe_url(href, detail_url)
        if fallback is None and section == "F23" and _is_print_link(parts, query, _link_label(link)):
            fallback = href
    return safe_url(fallback, detail_url) if fallback else get_pdf_url_from_detail(detail_url)


def _download_with_restore(page, url, destination, anno, dal, al, cancel, log, *, section="F24", detail=False):
    for attempt in range(1, SESSION_ATTEMPTS + 1):
        check_cancel(cancel)
        try:
            pdf_url = _payment_pdf_url(page, url, cancel, section) if detail else url
            download_pdf(page, pdf_url, destination)
            return
        except SessionNeedsRestore:
            if attempt == SESSION_ATTEMPTS:
                raise SessionRestoreFailed("Ripristino della sessione non riuscito durante il download del documento.") from None
            log(f"Sessione interrotta durante il documento. Ripristino {attempt}/{SESSION_ATTEMPTS - 1}…")
            ripristina_cassetto(page, cancel=cancel, log=log)
            options = {"section": section} if section != "F24" else {}
            page = apri_cassetto_e_scegli_date(page, anno, dal, al, cancel, log, **options) or page


def scarica_f24(page, anno, dal, al, output_dir, cancel=None, log=print, progress=None, pausa=2,
                *, include_other=False):
    output_dir = Path(output_dir)
    log("Verifica della cartella di destinazione…")
    prepare_destination(output_dir)
    result = DownloadResult(destination=output_dir)
    comparison_cache = {}
    check_cancel(cancel)
    available = False
    sections = ("F24", "VXX", "F23") if include_other else ("F24",)
    for section in sections:
        if result.cancelled or (cancel is not None and cancel.is_set()):
            result.cancelled = True
            break
        title = SECTION_TITLES[section]
        log(f"Anno {anno} · {title}.")
        options = {"section": section} if section != "F24" else {}
        try:
            page = apri_cassetto_e_scegli_date(page, anno, dal, al, cancel, log, **options) or page
        except YearNotAvailable:
            log(f"Anno {anno} · {title}: selettore assente.")
            continue
        available = True
        rows = collect_all_rows(page, anno, dal, al, cancel, **options)
        if not rows and not _empty_result(page.locator("body").inner_text(timeout=5_000)):
            raise RuntimeError(f"{title}: nessun collegamento ai documenti riconosciuto. Verifica il portale.")
        result.total += len(rows)
        log(f"{title}: {len(rows)} documenti da elaborare nel periodo.")
        if progress:
            progress(result)
        _scarica_documenti(page, rows, anno, dal, al, output_dir, result, comparison_cache,
                           cancel, log, progress, pausa, section)
    if not available and not result.cancelled:
        result.unavailable_years = (int(anno),)
    elif available and not result.total and not result.cancelled:
        result.empty_years = (int(anno),)
    if progress:
        progress(result)
    return result


def _scarica_documenti(page, rows, anno, dal, al, output_dir, result, comparison_cache,
                       cancel, log, progress, pausa, section):
    for index, row in enumerate(rows, 1):
        download_options = ({} if section == "F24"
                            else {"section": section, "detail": row["tipo"] == "detail"})
        if cancel is not None and cancel.is_set():
            result.cancelled = True
            break
        with tempfile.TemporaryDirectory(prefix=".f24-", dir=output_dir) as temporary:
            downloaded = Path(temporary) / "quietanza.pdf"
            try:
                model = False
                try:
                    _download_with_restore(page, row["url"], downloaded, anno, dal, al,
                                           cancel, log, **download_options)
                except (QuietanzaNotPrintable, PWTimeout) as error:
                    if section != "F24":
                        raise
                    reason = ("Delega non stampabile come quietanza" if isinstance(error, QuietanzaNotPrintable)
                              else "Quietanza non ricevuta entro il tempo previsto")
                    log(f"{index}/{len(rows)} · {reason}: provo il modello F24 (stampa=P).")
                    _download_with_restore(page, get_pdf_url_from_detail(row["url"], stampa="P"),
                        downloaded, anno, dal, al, cancel, log)
                    model = True
                options = {"document_kind": "modello"} if model else {}
                if section != "F24":
                    options["compact_amount"] = True
                if section == "F23":
                    options["document_kind"] = "f23"
                name = processa_nuovo_file(str(downloaded), output_dir=output_dir,
                    comparison_cache=comparison_cache, **options)
                if name == "skipped":
                    result.skipped += 1
                    log(f"{index}/{len(rows)} · Duplicato già presente.")
                else:
                    result.downloaded += 1
                    if "da_verificare_" in name:
                        result.unclassified += 1
                    if model:
                        result.models += 1
                        log(f"{index}/{len(rows)} · Modello F24 salvato (formato P, non quietanza).")
                    else:
                        message = "PDF F23 salvato." if section == "F23" else "Quietanza salvata."
                        log(f"{index}/{len(rows)} · {message}")
            except Cancelled:
                result.cancelled = True
                break
            except SessionRestoreFailed:
                raise
            except PWTimeout:
                result.errors += 1
                message = {
                    "F23": "PDF F23 non ricevuto entro il tempo previsto.",
                    "VXX": "Quietanza Q non ricevuta entro il tempo previsto.",
                    "F24": "Documento non disponibile né come quietanza né come modello P, o attesa scaduta.",
                }[section]
                log(f"{index}/{len(rows)} · {message}")
            except Exception:
                result.errors += 1
                log(f"{index}/{len(rows)} · Download non riuscito. Verifica il documento nel portale.")
        if progress:
            progress(result)
        if index < len(rows):
            if cancel is not None:
                if cancel.wait(max(2, pausa)):
                    result.cancelled = True
                    break
            else:
                page.wait_for_timeout(max(2, pausa) * 1000)
