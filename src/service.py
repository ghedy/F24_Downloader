"""Coordinamento del flusso, indipendente dall'interfaccia."""
from playwright.sync_api import sync_playwright, Error as PWError, TimeoutError as PWTimeout
from src.ade_login import effettua_login
from src.cambia_utenza import esegui_cambio_utenza
from src.f24_downloader import scarica_f24, apri_servizio_cassetto
from src.models import Cancelled, check_cancel, DownloadResult
from src.destination import prepare_destination

def describe_failure(error, phase):
    if isinstance(error, (ValueError, RuntimeError)):
        reason = str(error)
    elif isinstance(error, PWTimeout):
        reason = "Il sito non ha completato il passaggio entro il tempo previsto."
    elif isinstance(error, PWError):
        if "NS_BINDING_ABORTED" in str(error):
            reason = "Firefox ha interrotto la navigazione durante un reindirizzamento."
        elif "closed" in str(error).lower():
            reason = "La pagina o il browser sono stati chiusi."
        else:
            reason = "Errore di navigazione o pagina del portale diversa da quella attesa."
    else:
        reason = f"Errore applicativo ({type(error).__name__})."
    # Non riportare messaggi grezzi Playwright: possono contenere URL o dati dei form.
    return f"Interruzione durante: {phase}. {reason}"

def _combine_results(previous, current, destination=None):
    from dataclasses import replace
    combined = replace(previous)
    for name in ("total", "downloaded", "skipped", "errors", "models", "unclassified",
                 "renamed_existing", "removed_existing_duplicates", "cleanup_errors"):
        setattr(combined, name, getattr(previous, name) + getattr(current, name))
    combined.cancelled = previous.cancelled or current.cancelled
    combined.unavailable_years = previous.unavailable_years + current.unavailable_years
    combined.empty_years = previous.empty_years + current.empty_years
    combined.processed_years = previous.processed_years + current.processed_years
    combined.destination = destination or previous.destination or current.destination
    return combined

def run_download(request, credentials=None, cancel=None, log=print, progress=None, stage=None,
                 on_error=None):
    request.validate()
    log("Verifica della cartella di destinazione prima dell'accesso…")
    prepare_destination(request.destination)
    notify = stage or (lambda value: None)
    phase = "avvio del browser"
    def enter(value):
        nonlocal phase
        phase = value
        notify(value)
        log(f"Fase: {value}.")
    with sync_playwright() as playwright:
        browser = playwright.firefox.launch(headless=False)
        page = None
        try:
            context = browser.new_context(accept_downloads=True)
            context.set_default_timeout(20_000)
            page = context.new_page()
            enter("Accesso")
            effettua_login(page, request.metodo, request.provider, credentials,
                           request.automatico, cancel, log)
            check_cancel(cancel)
            if request.utenza.strip():
                enter("Cambio utenza")
                esegui_cambio_utenza(page, request.utenza, cancel, log)
            else:
                log("Profilo personale: salto il cambio utenza e proseguo verso il Cassetto fiscale.")
            check_cancel(cancel)
            enter("Apertura Cassetto e ricerca F24")
            page = apri_servizio_cassetto(page, cancel=cancel, log=log)
            aggregate = DownloadResult(destination=request.destination)
            for annual in request.year_requests():
                check_cancel(cancel)
                enter(f"Apertura Cassetto e ricerca F24 · anno {annual.anno}")
                baseline = aggregate
                def report(value, baseline=baseline):
                    if progress:
                        progress(_combine_results(baseline, value, request.destination))
                current = scarica_f24(page, str(annual.anno), annual.dal.strftime("%d/%m/%Y"),
                    annual.al.strftime("%d/%m/%Y"), annual.destination,
                    cancel, log, report, annual.pausa)
                current.processed_years = (annual.anno,)
                aggregate = _combine_results(aggregate, current, request.destination)
                if progress:
                    progress(aggregate)
                if aggregate.cancelled:
                    break
            return aggregate
        except Cancelled:
            raise
        except Exception as error:
            if on_error is not None:
                on_error(describe_failure(error, phase))
                # La GUI permette di leggere il portale e poi premere Chiudi browser.
                if cancel is not None and page is not None:
                    while not cancel.is_set() and browser.is_connected() and not page.is_closed():
                        try:
                            page.wait_for_timeout(250)
                        except PWError:
                            break
            raise
        finally:
            browser.close()
