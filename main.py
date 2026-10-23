"""Avvio dell'applicazione desktop F24 Downloader."""
import sys

def main():
    from PySide6.QtWidgets import QApplication, QMessageBox
    from config.config_manager import carica_config_avvio, salva_config
    from src.ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName("F24 Downloader")
    app.setOrganizationName("F24 Downloader")
    try:
        config, warning = carica_config_avvio()
        if config.get("credenziali"):
            salva_config(config)
    except PermissionError:
        QMessageBox.critical(None, "Cartella di configurazione non accessibile",
            "Windows non permette di leggere o aggiornare la cartella config. "
            "Sposta il programma in una cartella personale scrivibile, per esempio Documenti, e riavvialo.")
        return 1
    except (ValueError, UnicodeError):
        QMessageBox.critical(None, "Configurazione non valida",
            "Il file config/config.json non contiene una configurazione valida. "
            "Conservane una copia e ripristinalo dal file config/config.example.json.")
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
