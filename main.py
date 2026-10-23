"""Avvio dell'applicazione desktop F24 Downloader."""
import sys

def main():
    from src.runtime import configure_runtime
    configure_runtime()
    if len(sys.argv) == 3 and sys.argv[1] == "--check-installation":
        from src.bundle_check import run
        return run(sys.argv[2])
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QIcon
    from pathlib import Path
    from config.config_manager import carica_config_avvio, salva_config
    from src.ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "src/ui/icons/f24-downloader.svg")))
    app.setApplicationName("F24 Downloader")
    app.setOrganizationName("F24 Downloader")
    try:
        config, warning = carica_config_avvio()
        if config.get("credenziali"):
            salva_config(config)
    except PermissionError:
        QMessageBox.critical(None, "Cartella di configurazione non accessibile",
            "Windows non permette di leggere o aggiornare la configurazione locale. "
            "Verifica i permessi della cartella della configurazione e l'account Windows.")
        return 1
    except (ValueError, UnicodeError):
        QMessageBox.critical(None, "Configurazione non valida",
            "Il file della configurazione locale non contiene dati validi. "
            "Conservane una copia prima di ripristinare le impostazioni.")
        return 1
    except Exception:
        QMessageBox.critical(None, "Configurazione non disponibile",
            "Impossibile aprire o proteggere la configurazione locale. "
            "Nessuna sessione avviata. Verifica i permessi e l'account Windows.")
        return 1
    if warning:
        QMessageBox.warning(None, "Reinserisci le credenziali su questo PC", warning)
    window = MainWindow(config)
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
