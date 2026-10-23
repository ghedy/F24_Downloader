from datetime import date
import time
from src.models import DownloadResult
from src.ui import main_window as ui

def config():
    return {"utenze": [{"descrizione": "Azienda demo", "codice": "DEMO123"}], "impostazioni": {}}

def test_window_navigation_dates_and_secret_mask(qapp, tmp_path):
    window = ui.MainWindow(config())
    window.show()
    qapp.processEvents()
    assert window.pages.count() == 3
    assert window.target.count() == 2
    window.nav.setCurrentRow(1)
    assert window.pages.currentIndex() == 1
    window.year.setValue(2024)
    assert window.start_date.date().year() == window.end_date.date().year() == 2024
    window.target.setCurrentIndex(1)
    window.output.setText(str(tmp_path))
    assert window.make_request().destination.parts[-2:] == ("DEMO123", "2024")
    assert window.password.echoMode() == window.password.EchoMode.Password
    window.close()

def test_worker_finishes_and_restores_controls(qapp, monkeypatch, tmp_path):
    saved = []
    monkeypatch.setattr(ui, "salva_config", lambda value: saved.append(value))
    def synthetic_download(request, credentials, cancel, log, progress, stage, **kwargs):
        stage("Download")
        result = DownloadResult(total=1, downloaded=1, destination=request.destination)
        progress(result)
        return result
    monkeypatch.setattr(ui, "run_download", synthetic_download)
    window = ui.MainWindow(config())
    window.output.setText(str(tmp_path))
    window.start_download()
    deadline = time.monotonic() + 5
    while window.worker is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert window.worker is None
    assert window.start.isEnabled()
    assert not window.stop.isEnabled()
    assert window.badge.text() == "Completato"
    assert window.metrics["downloaded"].text() == "1"
    assert saved[0]["impostazioni"]["output_dir"] == str(tmp_path)
    window.close()



def test_error_keeps_window_open_until_browser_close_command(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(ui, "salva_config", lambda value: None)
    def synthetic_failure(request, credentials, cancel, log, progress, stage, on_error=None):
        stage("Cambio utenza")
        on_error("Interruzione durante: Cambio utenza. Errore sintetico.")
        cancel.wait(5)
        raise RuntimeError("Errore già mostrato")
    monkeypatch.setattr(ui, "run_download", synthetic_failure)
    window = ui.MainWindow(config())
    window.output.setText(str(tmp_path))
    window.show()
    window.start_download()
    deadline = time.monotonic() + 3
    while not window.browser_failed and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    try:
        assert window.isVisible()
        assert window.worker is not None
        assert window.stop.text() == "Chiudi browser"
        assert "Cambio utenza" in window.log.toPlainText()
        window.stop.click()
    finally:
        if window.worker:
            window.worker.cancel.set()
        deadline = time.monotonic() + 3
        while window.worker is not None and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.005)
    assert window.worker is None
    assert window.isVisible()
    assert window.start.isEnabled()
    assert "Errore già mostrato" not in window.log.toPlainText()
    window.close()

def test_folder_button_works_without_login(qapp, monkeypatch, tmp_path):
    from unittest.mock import Mock
    from tests.test_pdf_files import _printed_quietanza
    network = Mock()
    monkeypatch.setattr(ui, "run_download", network)
    window = ui.MainWindow(config())
    window.output.setText(str(tmp_path))
    window.target.setCurrentIndex(1)
    folder = window.make_request().destination
    folder.mkdir(parents=True)
    _printed_quietanza(folder / "a.pdf")
    _printed_quietanza(folder / "b.pdf", printed="19/10/2026 Ore: 11:22:33")
    window.start_folder_organizer()
    deadline = time.monotonic() + 8
    while window.worker is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert window.worker is None
    network.assert_not_called()
    assert window.metrics["downloaded"].text() == "1"
    assert window.metrics["skipped"].text() == "1"
    assert len(list(folder.glob("*.pdf"))) == 1
    assert window.organize.isEnabled()
    window.close()

def test_cleanup_flag_runs_after_download(qapp, monkeypatch, tmp_path):
    from src.folder_organizer import FolderResult
    from src.models import DownloadResult
    from unittest.mock import Mock
    monkeypatch.setattr(ui, "salva_config", lambda value: None)
    monkeypatch.setattr(ui, "run_download",
        lambda *a, **k: DownloadResult(total=2, skipped=2, destination=a[0].destination))
    organize = Mock(return_value=FolderResult(total=6, processed=6, renamed=2, duplicates=4))
    monkeypatch.setattr(ui, "organize_folder", organize)
    window = ui.MainWindow(config())
    window.output.setText(str(tmp_path))
    window.cleanup.setChecked(True)
    assert window.make_request().riordina_cartella
    window.start_download()
    deadline = time.monotonic() + 5
    while window.worker is not None and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert window.worker is None
    organize.assert_called_once()
    assert "4 duplicati eliminati" in window.log.toPlainText()
    window.close()


def test_ui_multi_year_changes_dates_and_destination(qapp, tmp_path):
    window = ui.MainWindow(config())
    window.output.setText(str(tmp_path))
    window.target.setCurrentIndex(1)
    window.year.setValue(2023)
    window.year_to.setValue(2025)
    request = window.make_request()
    request.validate()
    assert request.years == (2023, 2024, 2025)
    assert window.start_date.date().year() == 2023
    assert window.end_date.date().year() == 2025
    assert request.destination == tmp_path / "DEMO123"
    assert "2023-2025" in window.destination_hint.text()
    window.close()



def test_summary_identifies_models_saved_as_p(qapp):
    window = ui.MainWindow(config())
    window.finish_result(DownloadResult(total=2, downloaded=2, models=1))
    assert "1 modelli F24 in formato P" in window.log.toPlainText()
    assert "F24_modello" in window.log.toPlainText()
    window.close()


def test_final_year_mouse_arrows_work_at_and_below_initial_year(qapp, tmp_path):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QStyle, QStyleOptionSpinBox
    window = ui.MainWindow(config())
    window.output.setText(str(tmp_path))
    window.year.setValue(2025)
    window.show()
    qapp.processEvents()
    def click(control):
        option = QStyleOptionSpinBox()
        window.year_to.initStyleOption(option)
        rect = window.year_to.style().subControlRect(QStyle.CC_SpinBox, option, control, window.year_to)
        assert not rect.isEmpty()
        QTest.mouseClick(window.year_to, Qt.LeftButton, pos=rect.center())
        qapp.processEvents()
    assert window.year_to.value() == 2025
    click(QStyle.SC_SpinBoxDown)
    assert window.year_to.value() == window.year.value() == 2024
    assert window.start_date.date().year() == window.end_date.date().year() == 2024
    click(QStyle.SC_SpinBoxUp)
    assert window.year_to.value() == 2025 and window.year.value() == 2024
    assert window.end_date.date().year() == 2025
    window.make_request().validate()
    window.close()


def test_only_sielte_and_cie_are_selectable(qapp):
    window = ui.MainWindow(config())
    enabled = {window.method.itemData(index) for index in range(window.method.count())
               if window.method.model().item(index).isEnabled()}
    assert enabled == {"SPID", "CIE"}
    for index in range(window.method.count()):
        item = window.method.model().item(index)
        if not item.isEnabled():
            assert "collaudo" in item.toolTip()
    window.close()


def test_user_book_preserves_leading_zero_in_tax_number(qapp, monkeypatch, tmp_path):
    from PySide6.QtWidgets import QTableWidgetItem
    saved = []
    monkeypatch.setattr(ui, "salva_config", lambda value: saved.append(value))
    window = ui.MainWindow({"utenze": [], "impostazioni": {}})
    window.output.setText(str(tmp_path))
    window.add_user()
    window.users_table.setItem(0, 0, QTableWidgetItem("Società demo"))
    window.users_table.setItem(0, 1, QTableWidgetItem("01234567890"))
    window.save_users()
    assert saved[0]["utenze"][0]["codice"] == "01234567890"
    assert "Codice fiscale" in window.users_table.horizontalHeaderItem(1).text()
    window.target.setCurrentIndex(1)
    assert window.make_request().utenza == "01234567890"
    assert "01234567890" in window.target.currentText()
    window.target.setCurrentIndex(0)
    assert window.make_request().utenza == ""
    window.close()


def test_clean_install_has_no_preselected_download_folder(qapp):
    import pytest
    window = ui.MainWindow({"utenze": [], "impostazioni": {}})
    assert window.output.text() == ""
    assert window.target.count() == 1 and window.target.currentData() == ""
    with pytest.raises(ValueError, match="cartella di destinazione"):
        window.make_request()
    window.close()


def test_calendar_and_selectors_use_valid_point_fonts_without_qfont_warnings(qapp):
    from PySide6.QtCore import Qt, QPoint, qInstallMessageHandler
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QToolButton
    warnings = []
    previous = qInstallMessageHandler(lambda kind, context, message: warnings.append(message))
    window = None
    try:
        window = ui.MainWindow({"utenze": [], "impostazioni": {}})
        window.show()
        qapp.processEvents()
        for field in (window.method, window.target):
            field.showPopup()
            qapp.processEvents()
            field.hidePopup()
        for field in (window.start_date, window.end_date):
            assert field.font().pointSizeF() > 0
            QTest.mouseClick(field, Qt.LeftButton, pos=QPoint(field.width() - 12, field.height() // 2))
            qapp.processEvents()
            calendar = field.calendarWidget()
            assert calendar.isVisible()
            year = calendar.findChild(QToolButton, "qt_calendar_yearbutton")
            if year:
                year.click()
                qapp.processEvents()
            calendar.window().hide()
        for widget in (window, window.year, window.year_to, window.method, window.target):
            assert widget.font().pointSizeF() > 0
    finally:
        if window:
            window.close()
        qInstallMessageHandler(previous)
    assert not any("QFont::setPointSize" in message for message in warnings)
