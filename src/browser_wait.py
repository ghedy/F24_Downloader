"""Attese interrompibili e gestione dei redirect Firefox già presenti nel flusso originale."""
import time
from playwright.sync_api import Error as PWError
from src.models import check_cancel

def wait_seconds(page, seconds, cancel=None):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        check_cancel(cancel)
        page.wait_for_timeout(min(250, max(1, (deadline - time.monotonic()) * 1000)))
    check_cancel(cancel)

def navigate(page, url, timeout=30_000, cancel=None):
    check_cancel(cancel)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
    except PWError as error:
        if "NS_BINDING_ABORTED" not in str(error):
            raise
        # Firefox può interrompere il primo caricamento durante un redirect.
        wait_seconds(page, 1, cancel)
        page.wait_for_load_state("domcontentloaded", timeout=timeout)
    check_cancel(cancel)
