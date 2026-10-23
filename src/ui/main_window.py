import os
import re
from copy import deepcopy
from dataclasses import replace
from datetime import date
from pathlib import Path
from threading import Event

from PySide6.QtCore import QDate, Qt, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices, QFontDatabase, QBrush, QColor
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QScrollArea, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGridLayout, QComboBox, QLineEdit, QCheckBox, QSpinBox, QDateEdit, QFileDialog,
    QMessageBox, QProgressBar, QPlainTextEdit, QListWidget, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QStyledItemDelegate,
)
from config.config_manager import salva_config
from src import __version__
from src.models import DownloadRequest, Cancelled, AVAILABLE_LOGIN_METHODS
from src.destination import prepare_destination
from src.service import run_download
from src.folder_organizer import organize_folder, organize_folders

ROOT = Path(__file__).resolve().parents[2]
STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 9.75pt; color: #20262d; }
QMainWindow, #workspace, #downloadContent { background: #f7f8fa; }
QFrame#sidebar, QFrame#card { background: white; border: 1px solid #d4d9de; border-radius: 9px; }
QLabel#brand { color: #256a9f; font-size: 16.5pt; font-weight: 700; }
QLabel#heading { font-size: 18.75pt; font-weight: 650; }
QLabel#section { font-size: 11.25pt; font-weight: 650; }
QLabel#muted { color: #616b75; }
QLabel#metric { font-size: 20.25pt; font-weight: 650; color: #256a9f; }
QLabel#badge { background: #dfedf8; color: #194c73; padding: 6px 10px; border-radius: 6px; }
QListWidget { border: none; background: white; outline: none; }
QListWidget::item { padding: 12px 10px; margin: 3px 0; border-radius: 6px; }
QListWidget::item:selected { background: #dfedf8; color: #194c73; font-weight: 600; }
QLineEdit, QComboBox, QSpinBox, QDateEdit { background: white; border: 1px solid #b9c1c9; border-radius: 6px; padding: 7px; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateEdit:focus { border: 1px solid #256a9f; }
QSpinBox { padding-right: 30px; }
QSpinBox::up-button, QSpinBox::down-button { subcontrol-origin: border; width: 25px; background: #edf4fa; border-left: 1px solid #b9c1c9; }
QSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 6px; border-bottom: 1px solid #d4d9de; }
QSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 6px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: #dfedf8; }
QSpinBox::up-button:disabled, QSpinBox::down-button:disabled { background: #e1e5e8; }
QSpinBox::up-arrow { image: url("$YEAR_UP_ICON"); width: 12px; height: 10px; }
QSpinBox::down-arrow { image: url("$YEAR_DOWN_ICON"); width: 12px; height: 10px; }
QDateEdit { padding-right: 30px; }
QDateEdit::drop-down { subcontrol-origin: border; subcontrol-position: top right; width: 25px; background: #edf4fa; border-left: 1px solid #b9c1c9; border-top-right-radius: 6px; border-bottom-right-radius: 6px; }
QDateEdit::drop-down:hover { background: #dfedf8; }
QDateEdit::down-arrow { image: url("$YEAR_DOWN_ICON"); width: 12px; height: 10px; }
QPushButton { background: white; border: 1px solid #b9c1c9; border-radius: 6px; padding: 8px 14px; min-height: 20px; }
QPushButton:hover { background: #f0f2f3; }
QPushButton#primary { background: #256a9f; color: white; border-color: #256a9f; font-weight: 600; }
QPushButton#primary:hover { background: #1f5d8d; }
QPushButton:disabled { background: #f0f2f3; color: #8b949e; border-color: #d4d9de; }
QPlainTextEdit, QTableWidget { background: white; border: 1px solid #d4d9de; border-radius: 6px; selection-background-color: #dfedf8; }
QHeaderView::section { background: #e1e5e8; padding: 8px; border: none; }
QProgressBar { background: #e1e5e8; border: none; border-radius: 4px; min-height: 8px; max-height: 8px; }
QProgressBar::chunk { background: #256a9f; border-radius: 4px; }
QCheckBox { spacing: 8px; }
QStatusBar { background: white; border-top: 1px solid #d4d9de; color: #616b75; }
"""
STYLE = STYLE.replace("$YEAR_UP_ICON", (ROOT / "src/ui/icons/chevron-up.svg").as_posix())
STYLE = STYLE.replace("$YEAR_DOWN_ICON", (ROOT / "src/ui/icons/chevron-down.svg").as_posix())

def label(text, role=None):
    widget = QLabel(text)
    if role:
        widget.setObjectName(role)
    widget.setWordWrap(True)
    widget.setTextFormat(Qt.PlainText)
    return widget

def card(title):
    panel = QFrame()
    panel.setObjectName("card")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(20, 16, 20, 20)
    layout.setSpacing(12)
    layout.addWidget(label(title, "section"))
    return panel, layout

class DownloadWorker(QThread):
    message = Signal(str)
    phase = Signal(str)
    progress = Signal(object)
    result = Signal(object)
    error = Signal(str)
    browser_error = Signal(str)

    def __init__(self, request, credentials):
        super().__init__()
        self.request = request
        self.credentials = credentials
        self.cancel = Event()
        self.failure_reported = False

    def report_browser_error(self, message):
        self.failure_reported = True
        self.browser_error.emit(message)

    def run(self):
        try:
            result = run_download(self.request, self.credentials, self.cancel,
                self.message.emit, lambda value: self.progress.emit(replace(value)), self.phase.emit,
                on_error=self.report_browser_error)
            if self.request.riordina_cartella and not result.cancelled:
                self.phase.emit("Riordino cartella")
                folders = self.request.destinations
                cleaned = (organize_folder(folders[0], self.cancel, self.message.emit) if len(folders) == 1
                    else organize_folders(folders, self.cancel, self.message.emit))
                result.renamed_existing = cleaned.renamed
                result.removed_existing_duplicates = cleaned.duplicates
                result.cleanup_errors = cleaned.errors
                result.cancelled = cleaned.cancelled
            self.result.emit(result)
        except Cancelled:
            self.phase.emit("Interrotto")
            self.message.emit("Operazione interrotta. Le quietanze già salvate restano nella cartella.")
        except (ValueError, RuntimeError) as error:
            if not self.failure_reported:
                self.error.emit(str(error))
        except Exception:
            if not self.failure_reported:
                self.error.emit("Sessione non completata. Verifica il browser, la connessione e "
                    "l'installazione di Firefox per Playwright. Il portale potrebbe essere cambiato.")
        finally:
            self.credentials = {}

class FolderWorker(QThread):
    message = Signal(str)
    phase = Signal(str)
    progress = Signal(object)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, folder):
        super().__init__()
        self.folders = (folder,) if isinstance(folder, (str, Path)) else tuple(folder)
        self.cancel = Event()

    def run(self):
        try:
            self.phase.emit("Riordino cartella")
            self.result.emit(organize_folders(self.folders, self.cancel, self.message.emit, self.progress.emit))
        except Exception:
            self.error.emit("Riordino non completato. Verifica cartella e permessi di accesso.")

class MainWindow(QMainWindow):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.worker = None
        self.close_pending = False
        self.browser_failed = False
        self.last_destination = None
        self.setWindowTitle(f"F24 Downloader · {__version__}")
        if not QFontDatabase.families() and os.name == "nt":
            QFontDatabase.addApplicationFont("C:/Windows/Fonts/segoeui.ttf")
        self.resize(1180, 850)
        self.setMinimumSize(1040, 780)
        self.setStyleSheet(STYLE)
        container = QWidget()
        container.setObjectName("workspace")
        outer = QHBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(18)
        self.setCentralWidget(container)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(218)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(16, 24, 16, 18)
        side.addWidget(label("F24 Downloader", "brand"))
        side.addWidget(label("Le tue quietanze, in ordine.", "muted"))
        side.addSpacing(25)
        self.nav = QListWidget()
        self.nav.addItems(["Scarica quietanze", "Utenze", "Impostazioni e privacy"])
        side.addWidget(self.nav, 1)
        side.addWidget(label("LOCALE · GRATUITO", "muted"))
        side.addWidget(label(f"Versione {__version__}\nProgetto indipendente da AdE", "muted"))
        outer.addWidget(sidebar)
        content = QVBoxLayout()
        outer.addLayout(content, 1)
        heading = QHBoxLayout()
        heading.addWidget(label("Quietanze F24", "heading"), 1)
        self.badge = label("Pronto", "badge")
        heading.addWidget(self.badge)
        content.addLayout(heading)
        content.addWidget(label("Accedi, scegli l'utenza e raccogli i documenti nel tuo computer.", "muted"))
        self.pages = QStackedWidget()
        content.addWidget(self.pages, 1)
        self.build_download()
        self.build_users()
        self.build_settings()
        self.nav.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.nav.setCurrentRow(0)
        self.statusBar().showMessage("Autenticazione nel browser · Nessuna telemetria applicativa")
        self.load_users()
        self.load_credentials()

    def build_download(self):
        page = QWidget()
        page.setObjectName("downloadContent")
        columns = QHBoxLayout(page)
        columns.setContentsMargins(0, 12, 0, 0)
        columns.setSpacing(16)
        left = QVBoxLayout()
        columns.addLayout(left, 3)
        access, layout = card("1   Accesso e utenza")
        self.access_card = access
        self.method = QComboBox()
        self.method.setItemDelegate(QStyledItemDelegate(self.method))
        for title, value in [("SPID · Sielte", "SPID"), ("Carta d'identità elettronica · CIE", "CIE"),
                             ("Carta nazionale dei servizi · CNS", "CNS"),
                             ("Fisconline / Entratel", "FISCONLINE"),
                             ("Accesso dal portale · altri gestori SPID", "PORTALE")]:
            self.method.addItem(title.replace(" · ", " - "), value)
            if value not in AVAILABLE_LOGIN_METHODS:
                item = self.method.model().item(self.method.count() - 1)
                item.setEnabled(False)
                item.setForeground(QBrush(QColor("#949ca5")))
                item.setToolTip("Non ancora disponibile: in attesa di collaudo.")
        self.target = QComboBox()
        self.auto = QCheckBox("Compila automaticamente nome utente e password")
        self.username = QLineEdit()
        self.username.setPlaceholderText("Nome utente")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Password")
        self.password.setEchoMode(QLineEdit.Password)
        self.remember = QCheckBox("Ricorda le credenziali in questo account Windows")
        form = QFormLayout()
        form.addRow("Metodo", self.method)
        form.addRow("Utenza", self.target)
        layout.addLayout(form)
        layout.addWidget(self.auto)
        credentials = QHBoxLayout()
        credentials.addWidget(self.username)
        credentials.addWidget(self.password)
        layout.addLayout(credentials)
        layout.addWidget(self.remember)
        layout.addWidget(label("Conferma tu il secondo fattore; per Sielte e CIE l'app prosegue automaticamente.", "muted"))
        self.method.currentIndexChanged.connect(self.load_credentials)
        self.auto.toggled.connect(self.toggle_credentials)
        left.addWidget(access)

        period, layout = card("2   Periodo e destinazione")
        self.period_card = period
        self.year = QSpinBox()
        self.year.setRange(2000, date.today().year)
        self.year.setValue(date.today().year)
        self._first_year = date.today().year
        self.year_to = QSpinBox()
        self.year_to.setRange(2000, date.today().year)
        self.year_to.setValue(date.today().year)
        self.year.setKeyboardTracking(False)
        self.year_to.setKeyboardTracking(False)
        self.year.setToolTip("Anno iniziale, dal 2000 all'anno corrente.")
        self.year_to.setToolTip("Anno finale, dal 2000 all'anno corrente. Se precede l'anno iniziale, anche quello iniziale viene aggiornato.")
        self.start_date = QDateEdit(QDate(date.today().year, 1, 1))
        self.end_date = QDateEdit(QDate.currentDate())
        for field in (self.start_date, self.end_date):
            field.setCalendarPopup(True)
            field.setDisplayFormat("dd/MM/yyyy")
        self.period_fields = QGridLayout()
        self.period_fields.setHorizontalSpacing(8)
        self.period_fields.setVerticalSpacing(10)
        for row, title, first, last in (
            (0, "Anni dal / al", self.year, self.year_to),
            (1, "Dal / al", self.start_date, self.end_date),
        ):
            self.period_fields.addWidget(label(title), row, 0)
            for field, column in ((first, 1), (last, 3)):
                field.setFixedSize(150, 38)
                self.period_fields.addWidget(field, row, column)
            separator = label("-")
            separator.setAlignment(Qt.AlignCenter)
            separator.setFixedWidth(8)
            self.period_fields.addWidget(separator, row, 2)
        self.period_fields.setColumnStretch(4, 1)
        layout.addLayout(self.period_fields)
        self.year.valueChanged.connect(self.change_year)
        self.year_to.valueChanged.connect(self.change_last_year)
        self.output = QLineEdit(str(self.config.get("impostazioni", {}).get("output_dir") or ""))
        self.output.setPlaceholderText("Scegli la cartella dei download")
        destination = QHBoxLayout()
        destination.addWidget(self.output, 1)
        choose = QPushButton("Sfoglia…")
        choose.clicked.connect(self.choose_folder)
        destination.addWidget(choose)
        layout.addLayout(destination)
        self.destination_hint = label("", "muted")
        layout.addWidget(self.destination_hint)
        self.output.textChanged.connect(self.update_hint)
        self.target.currentIndexChanged.connect(self.update_hint)
        self.cleanup = QCheckBox("Rinomina e rimuovi duplicati da tutta la cartella")
        self.cleanup.setToolTip("Dopo il download controlla tutti i PDF delle cartelle annuali selezionate, anche quelli già presenti. Elimina direttamente le copie uguali e conserva una quietanza per contenuto.")
        layout.addWidget(self.cleanup)
        left.addWidget(period)

        actions = QHBoxLayout()
        self.start = QPushButton("Avvia download")
        self.start.setObjectName("primary")
        self.start.clicked.connect(self.start_download)
        self.stop = QPushButton("Interrompi")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self.cancel_download)
        actions.addWidget(self.start, 1)
        actions.addWidget(self.stop)
        left.addLayout(actions)
        self.organize = QPushButton("Riordina e rinomina solo la cartella")
        self.organize.setToolTip("Operazione locale senza accesso AdE: rinomina i PDF riconosciuti ed elimina i duplicati nelle cartelle utenza/anno selezionate.")
        self.organize.clicked.connect(self.start_folder_organizer)
        left.addWidget(self.organize)
        left.addStretch()

        right = QVBoxLayout()
        columns.addLayout(right, 2)
        summary, layout = card("Questa sessione")
        metrics = QHBoxLayout()
        self.metrics = {}
        self.metric_titles = {}
        for key, title in [("downloaded", "Salvate"), ("skipped", "Duplicati"), ("errors", "Errori")]:
            column = QVBoxLayout()
            value = label("0", "metric")
            self.metrics[key] = value
            column.addWidget(value)
            caption = label(title, "muted")
            self.metric_titles[key] = caption
            column.addWidget(caption)
            metrics.addLayout(column)
        layout.addLayout(metrics)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.progress_text = label("Nessuna sessione avviata", "muted")
        layout.addWidget(self.progress_text)
        self.open_folder = QPushButton("Apri cartella")
        self.open_folder.clicked.connect(self.show_folder)
        layout.addWidget(self.open_folder)
        right.addWidget(summary)
        history, layout = card("Attività")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(1000)
        self.log.setPlaceholderText("Qui vedrai accesso, verifica utenza\ne avanzamento dei download.")
        layout.addWidget(self.log, 1)
        right.addWidget(history, 1)
        right.addWidget(label("I PDF sono organizzati per utenza e anno. I documenti già presenti vengono riconosciuti anche se cambia l'ora di stampa.", "muted"))
        self.download_scroll = QScrollArea()
        self.download_scroll.setWidgetResizable(True)
        self.download_scroll.setFrameShape(QFrame.NoFrame)
        self.download_scroll.setWidget(page)
        self.pages.addWidget(self.download_scroll)

    def build_users(self):
        page, layout = card("Utenze collegate")
        layout.addWidget(label("Inserisci il codice fiscale o la partita IVA visibile nella descrizione dell'utenza su AdE. "
            "Il programma individua automaticamente il codice interno. La rubrica non attribuisce deleghe.", "muted"))
        self.users_table = QTableWidget(0, 2)
        self.users_table.setHorizontalHeaderLabels(["Descrizione", "Codice fiscale / Partita IVA"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        layout.addWidget(self.users_table, 1)
        row = QHBoxLayout()
        for title, action in [("Aggiungi utenza", self.add_user), ("Rimuovi selezionata", self.remove_user),
                              ("Salva utenze", self.save_users)]:
            button = QPushButton(title)
            button.clicked.connect(action)
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(label("Profilo personale: il programma salta il cambio utenza. Le utenze collegate richiedono una corrispondenza univoca sul portale.", "muted"))
        self.pages.addWidget(page)

    def build_settings(self):
        page, layout = card("Impostazioni e privacy")
        layout.addWidget(label("I documenti restano nella cartella scelta. L'applicazione contatta AdE "
            "e il gestore di identità necessario all'accesso. Non invia dati allo sviluppatore.", "muted"))
        self.pause = QSpinBox()
        self.pause.setRange(2, 60)
        self.pause.setSuffix(" secondi")
        self.pause.setValue(max(2, int(self.config.get("impostazioni", {}).get("pausa_download", 2))))
        form = QFormLayout()
        form.addRow("Pausa tra download", self.pause)
        layout.addLayout(form)
        save = QPushButton("Salva impostazioni")
        save.clicked.connect(self.save_settings)
        layout.addWidget(save)
        layout.addWidget(label("Credenziali protette", "section"))
        layout.addWidget(label("Se scegli di ricordarle, vengono cifrate con Windows DPAPI e sono "
            "leggibili dal tuo account Windows. Chi può operare nel tuo account può accedervi. "
            "Non vengono salvati cookie, sessioni, OTP, schermate o copie delle pagine.", "muted"))
        forget = QPushButton("Dimentica tutte le credenziali salvate")
        forget.clicked.connect(self.forget_credentials)
        layout.addWidget(forget)
        layout.addWidget(label("Versione di prova", "section"))
        layout.addWidget(label("Software indipendente, non affiliato né approvato dall'Agenzia delle Entrate. "
            "Usalo per dati tuoi o per utenze per cui disponi delle necessarie autorizzazioni. "
            "I cambiamenti del portale possono richiedere aggiornamenti.", "muted"))
        layout.addStretch()
        self.pages.addWidget(page)

    def credential_key(self):
        return "SPID_SIELTE" if self.method.currentData() == "SPID" else self.method.currentData()

    def load_credentials(self):
        allowed = self.method.currentData() in AVAILABLE_LOGIN_METHODS
        credentials = self.config.get("credenziali", {}).get(self.credential_key(), {})
        self.username.setText(credentials.get("username", ""))
        self.password.setText(credentials.get("password", ""))
        self.auto.setEnabled(allowed)
        self.auto.setChecked(allowed and bool(credentials.get("username") and credentials.get("password")))
        self.remember.setChecked(bool(credentials.get("password")))
        self.toggle_credentials(self.auto.isChecked())

    def toggle_credentials(self, enabled):
        for widget in (self.username, self.password, self.remember):
            widget.setEnabled(enabled)

    def load_users(self):
        self.users_table.setRowCount(0)
        self.target.clear()
        self.target.addItem("Profilo personale - nessun cambio utenza", "")
        for user in self.config.get("utenze", []):
            row = self.users_table.rowCount()
            self.users_table.insertRow(row)
            for col, key in enumerate(("descrizione", "codice")):
                self.users_table.setItem(row, col, QTableWidgetItem(user.get(key, "")))
            code = user["codice"]
            description = user.get("descrizione", "")
            self.target.addItem(f"{description} - {code}" if description else code, code)
        self.update_hint()

    def add_user(self):
        self.users_table.insertRow(self.users_table.rowCount())

    def remove_user(self):
        for row in sorted({item.row() for item in self.users_table.selectedItems()}, reverse=True):
            self.users_table.removeRow(row)

    def persist(self, updated):
        try:
            salva_config(updated)
        except Exception:
            QMessageBox.critical(self, "Salvataggio non riuscito",
                "Impossibile salvare la configurazione protetta. Verifica permessi e account Windows.")
            return False
        self.config = updated
        return True

    def save_users(self):
        users, seen = [], set()
        for row in range(self.users_table.rowCount()):
            values = [(self.users_table.item(row, col).text().strip()
                       if self.users_table.item(row, col) else "") for col in range(2)]
            description, code = values
            code = code.upper()
            if not description or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code) or code.upper() in seen:
                QMessageBox.warning(self, "Utenza non valida", "Ogni riga richiede una descrizione e un codice fiscale o partita IVA univoco, senza spazi.")
                return
            seen.add(code.upper())
            users.append({"descrizione": description, "codice": code})
        updated = deepcopy(self.config)
        updated["utenze"] = users
        if self.persist(updated):
            self.load_users()
            self.statusBar().showMessage("Rubrica utenze salvata localmente.")

    def save_settings(self):
        updated = deepcopy(self.config)
        updated.setdefault("impostazioni", {}).update(
            output_dir=self.output.text().strip(), pausa_download=self.pause.value())
        if self.persist(updated):
            self.statusBar().showMessage("Impostazioni salvate.")

    def forget_credentials(self):
        from config.config_manager import CONFIG_FILE
        updated = deepcopy(self.config)
        updated["credenziali"] = {}
        if self.persist(updated):
            try:
                CONFIG_FILE.with_name("credentials.bin").unlink(missing_ok=True)
            except OSError:
                QMessageBox.warning(self, "Archivio non eliminato", "Impossibile eliminare l'archivio cifrato. Verifica i permessi.")
            self.load_credentials()

    def change_year(self, year):
        previous_first = self._first_year
        last = self.year_to.value()
        self.year_to.blockSignals(True)
        self.year_to.setValue(year if last == previous_first else max(year, last))
        self.year_to.blockSignals(False)
        self._first_year = year
        self.start_date.setDate(QDate(year, 1, 1))
        self.change_last_year(self.year_to.value())

    def change_last_year(self, year):
        if year < self.year.value():
            self.year.blockSignals(True)
            self.year.setValue(year)
            self.year.blockSignals(False)
            self._first_year = year
            self.start_date.setDate(QDate(year, 1, 1))
        self.end_date.setDate(QDate.currentDate() if year == date.today().year else QDate(year, 12, 31))
        self.update_hint()

    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Cartella quietanze", self.output.text())
        if path:
            self.output.setText(path)

    def update_hint(self):
        if not self.output.text().strip():
            self.destination_hint.setText("Destinazione: scegli una cartella per i PDF.")
            return
        base = Path(self.output.text().strip()).expanduser()
        root = base / (self.target.currentData() or "profilo_personale")
        if self.year.value() == self.year_to.value():
            root = root / str(self.year.value())
            note = ""
        else:
            note = f" · cartelle separate {self.year.value()}-{self.year_to.value()}"
        self.destination_hint.setText("Destinazione: " + str(root) + note)

    def make_request(self):
        if not self.output.text().strip():
            raise ValueError("Scegli una cartella di destinazione.")
        base = Path(self.output.text().strip()).expanduser()
        if not base.is_absolute():
            base = ROOT / base
        return DownloadRequest(self.method.currentData(), "sielte", self.target.currentData() or "",
            self.year.value(), self.start_date.date().toPython(), self.end_date.date().toPython(),
            base, self.auto.isChecked(), self.pause.value(), self.cleanup.isChecked(), self.year_to.value())

    def start_download(self):
        if self.worker is not None:
            return
        try:
            request = self.make_request()
            request.validate()
            prepare_destination(request.destination)
            if request.automatico and (not self.username.text().strip() or not self.password.text()):
                raise ValueError("Inserisci nome utente e password oppure disattiva la compilazione automatica.")
        except ValueError as error:
            QMessageBox.warning(self, "Controlla i parametri", str(error))
            return
        credentials = {"username": self.username.text().strip(), "password": self.password.text()} if request.automatico else {}
        updated = deepcopy(self.config)
        updated.setdefault("impostazioni", {}).update(
            output_dir=self.output.text().strip(), pausa_download=self.pause.value())
        if request.automatico and self.remember.isChecked():
            updated.setdefault("credenziali", {})[self.credential_key()] = credentials.copy()
        if not self.persist(updated):
            return
        self.log.clear()
        self.browser_failed = False
        self.last_destination = request.destination
        self.metric_titles["downloaded"].setText("Salvate")
        self.metric_titles["skipped"].setText("Duplicati")
        self.progress.setRange(0, 0)
        self.progress_text.setText("Avvio del browser…")
        for metric in self.metrics.values():
            metric.setText("0")
        self.set_busy(True)
        self.worker = DownloadWorker(request, credentials)
        self.worker.message.connect(self.log.appendPlainText)
        self.worker.phase.connect(self.badge.setText)
        self.worker.progress.connect(self.update_progress)
        self.worker.result.connect(self.finish_result)
        self.worker.error.connect(self.show_error)
        self.worker.browser_error.connect(self.show_browser_error)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def start_folder_organizer(self):
        if self.worker is not None:
            return
        try:
            request = self.make_request()
            destination = request.destination
            folders = tuple(path for path in request.destinations if path.is_dir())
            if not folders:
                raise ValueError("La cartella utenza/anno non esiste ancora. Controlla utenza, anno e destinazione.")
        except ValueError as error:
            QMessageBox.warning(self, "Controlla la cartella", str(error))
            return
        self.log.clear()
        self.browser_failed = False
        self.last_destination = destination
        self.metric_titles["downloaded"].setText("Rinominati")
        self.metric_titles["skipped"].setText("Duplicati eliminati")
        for metric in self.metrics.values():
            metric.setText("0")
        self.set_busy(True)
        self.progress.setRange(0, 0)
        self.worker = FolderWorker(folders)
        self.worker.message.connect(self.log.appendPlainText)
        self.worker.phase.connect(self.badge.setText)
        self.worker.progress.connect(self.update_folder_progress)
        self.worker.result.connect(self.finish_folder_result)
        self.worker.error.connect(self.show_error)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def update_folder_progress(self, result):
        self.metrics["downloaded"].setText(str(result.renamed))
        self.metrics["skipped"].setText(str(result.duplicates))
        self.metrics["errors"].setText(str(result.errors))
        self.progress.setRange(0, max(1, result.total))
        self.progress.setValue(result.processed)
        self.progress_text.setText(f"{result.processed} di {result.total} PDF controllati")

    def finish_folder_result(self, result):
        self.update_folder_progress(result)
        self.badge.setText("Interrotto" if result.cancelled else ("Da verificare" if result.errors else "Completato"))
        if result.unclassified:
            self.log.appendPlainText(f"{result.unclassified} PDF non riconosciuti conservano il nome originale.")

    def set_busy(self, busy):
        self.stop.setText("Interrompi")
        self.start.setEnabled(not busy)
        self.organize.setEnabled(not busy)
        self.stop.setEnabled(busy)
        self.access_card.setEnabled(not busy)
        self.period_card.setEnabled(not busy)
        self.nav.setEnabled(not busy)

    def update_progress(self, result):
        for key, metric in self.metrics.items():
            metric.setText(str(getattr(result, key)))
        done = result.downloaded + result.skipped + result.errors
        self.progress.setRange(0, max(1, result.total))
        self.progress.setValue(done)
        self.progress_text.setText(f"{done} di {result.total} documenti elaborati")

    def finish_result(self, result):
        self.update_progress(result)
        state = "Interrotto" if result.cancelled else ("Da verificare" if result.errors or result.unclassified or result.cleanup_errors else "Completato")
        self.badge.setText(state)
        self.log.appendPlainText(f"{state} · {result.downloaded} salvate, {result.skipped} duplicati, {result.errors} errori.")
        if result.models:
            self.log.appendPlainText(f"Tra i documenti salvati: {result.models} modelli F24 in formato P, identificati da F24_modello nel nome.")
        if result.unavailable_years:
            self.log.appendPlainText("Anni senza selettore F24, saltati: " + ", ".join(map(str, result.unavailable_years)))
        if result.empty_years:
            self.log.appendPlainText("Nessuna occorrenza nel periodo per gli anni: " + ", ".join(map(str, result.empty_years)))
        if result.renamed_existing or result.removed_existing_duplicates or result.cleanup_errors:
            self.log.appendPlainText(f"Cartella riordinata: {result.renamed_existing} rinominati, "
                f"{result.removed_existing_duplicates} duplicati eliminati, {result.cleanup_errors} errori.")
        if result.unclassified:
            self.log.appendPlainText(f"{result.unclassified} PDF conservati con nome 'da_verificare': controlla data e importo.")
        if result.cancelled:
            self.log.appendPlainText("I documenti già salvati restano nella cartella.")

    def show_error(self, message):
        self.badge.setText("Da verificare")
        self.log.appendPlainText(message)
        self.progress_text.setText("Operazione non completata")
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

    def show_browser_error(self, message):
        self.browser_failed = True
        self.show_error(message)
        self.stop.setText("Chiudi browser")
        self.stop.setEnabled(True)
        self.log.appendPlainText("Il browser resta aperto: puoi leggere la pagina in cui si è fermato. "
            "Poi premi Chiudi browser per terminare la sessione.")

    def worker_finished(self):
        worker = self.worker
        self.worker = None
        if worker:
            worker.deleteLater()
        self.set_busy(False)
        self.progress.setRange(0, max(1, self.progress.maximum()))
        if self.close_pending:
            self.close()

    def cancel_download(self):
        if self.worker:
            self.worker.cancel.set()
            self.stop.setEnabled(False)
            if self.browser_failed:
                self.log.appendPlainText("Chiusura del browser richiesta.")
            else:
                self.badge.setText("Interruzione…")
                self.log.appendPlainText("Interruzione richiesta. Attendo il completamento della richiesta corrente (fino a 60 secondi).")

    def show_folder(self):
        try:
            destination = self.last_destination or self.make_request().destination
        except ValueError as error:
            QMessageBox.warning(self, "Controlla la cartella", str(error))
            return
        if destination.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(destination)))
        else:
            QMessageBox.information(self, "Cartella non ancora creata", "La cartella viene creata all'avvio dello scaricamento.")

    def closeEvent(self, event):
        if self.worker is not None:
            self.close_pending = True
            self.cancel_download()
            event.ignore()
        else:
            event.accept()
