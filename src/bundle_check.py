"""Offline release check, invoked explicitly with --check-installation REPORT.json."""
import json
import os
from pathlib import Path
import tempfile
import traceback


def run(report):
    report = Path(report).resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    result = {"ok": False, "checks": []}
    original = os.environ.get("LOCALAPPDATA")
    try:
        with tempfile.TemporaryDirectory(prefix="f24-installation-check-") as temporary:
            temporary = Path(temporary)
            os.environ["LOCALAPPDATA"] = str(temporary / "settings")
            from config.config_manager import CONFIG_FILE, carica_config, salva_config
            from src import __version__
            from src.models import AVAILABLE_LOGIN_METHODS
            from src.security import protect, unprotect
            from src.ui.main_window import MainWindow, ROOT
            from PySide6.QtWidgets import QApplication
            from playwright.sync_api import sync_playwright
            import pdfplumber
            result["version"] = __version__
            assert CONFIG_FILE == temporary / "settings/F24Downloader/config.json"
            config = carica_config()
            assert config == {"utenze": [], "impostazioni": {}, "credenziali": {}}
            assert AVAILABLE_LOGIN_METHODS == {"SPID", "CIE"}
            secret = b"synthetic-installation-check"
            encrypted = protect(secret)
            assert encrypted != secret and unprotect(encrypted) == secret
            salva_config(config)
            assert carica_config() == config
            result["checks"].extend(["empty-user-settings", "CIE-and-Sielte-only", "Windows-DPAPI"])
            app = QApplication([])
            window = MainWindow(config)
            window.show()
            app.processEvents()
            assert (ROOT / "src/ui/icons/chevron-up.svg").is_file()
            assert (ROOT / "src/ui/icons/f24-downloader.svg").is_file()
            window.grab().save(str(report.with_suffix(".png")))
            window.close()
            app.processEvents()
            result["checks"].append("desktop-interface-and-icons")
            # Build a complete synthetic PDF. No fiscal data and no network requests.
            stream = b"BT /F1 12 Tf 20 750 Td (F24 installation check) Tj ET"
            objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
            pdf, positions = b"%PDF-1.4\n", [0]
            for number, body in enumerate(objects, 1):
                positions.append(len(pdf))
                pdf += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
            offset = len(pdf)
            pdf += b"xref\n0 6\n0000000000 65535 f \n"
            pdf += b"".join(f"{position:010d} 00000 n \n".encode() for position in positions[1:])
            pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{offset}\n%%EOF".encode()
            with sync_playwright() as playwright:
                executable = Path(playwright.firefox.executable_path).resolve()
                import sys
                assert executable.is_relative_to(Path(sys._MEIPASS).resolve())
                browser = playwright.firefox.launch(headless=True)
                context = browser.new_context(accept_downloads=True)
                def route_request(route):
                    if route.request.url == "https://installation-check.invalid/":
                        route.fulfill(body='<a href="/document.pdf" download>PDF</a>', content_type="text/html")
                    elif route.request.url == "https://installation-check.invalid/document.pdf":
                        route.fulfill(body=pdf, content_type="application/pdf",
                            headers={"Content-Disposition": 'attachment; filename="synthetic.pdf"'})
                    else:
                        route.abort()
                context.route("**/*", route_request)
                page = context.new_page()
                page.goto("https://installation-check.invalid/")
                with page.expect_download() as event:
                    page.locator("a").click()
                destination = temporary / "synthetic.pdf"
                event.value.save_as(destination)
                assert destination.read_bytes() == pdf
                with pdfplumber.open(destination) as document:
                    assert "F24 installation check" in document.pages[0].extract_text()
                browser.close()
            result["checks"].extend(["bundled-Firefox", "offline-PDF-download-and-read"])
        result["ok"] = True
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        if original is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = original
        report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1
