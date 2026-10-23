"""Controlli della destinazione, prima di richiedere l'identità digitale."""
from datetime import date
from pathlib import Path
from unittest.mock import Mock
import pytest
from src import destination, service
from src.destination import DestinationError, prepare_destination
from src.models import DownloadRequest

def test_writable_destination_is_created_without_leaving_check_files(tmp_path):
    path = tmp_path / "output" / "demo" / "2026"
    assert prepare_destination(path) == path
    assert path.is_dir()
    assert list(path.iterdir()) == []

def test_missing_drive_has_actionable_message(monkeypatch):
    def missing(*args, **kwargs):
        raise FileNotFoundError("private-path-must-not-be-in-log")
    monkeypatch.setattr(Path, "mkdir", missing)
    with pytest.raises(DestinationError) as result:
        prepare_destination(Path("U:/unavailable/demo"))
    assert "Sfoglia" in str(result.value)
    assert "private-path" not in str(result.value)

def test_read_only_destination_is_reported(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise PermissionError()
    monkeypatch.setattr(destination.tempfile, "TemporaryFile", denied)
    with pytest.raises(DestinationError, match="permessi"):
        prepare_destination(tmp_path)

def test_invalid_destination_stops_before_starting_browser(tmp_path, monkeypatch):
    blocked = tmp_path / "file-in-place-of-folder"
    blocked.write_text("synthetic", encoding="utf-8")
    start_browser = Mock()
    monkeypatch.setattr(service, "sync_playwright", start_browser)
    request = DownloadRequest("CIE", "", "", 2025, date(2025, 1, 1), date(2025, 12, 31), blocked)
    with pytest.raises(DestinationError):
        service.run_download(request, log=lambda _: None)
    start_browser.assert_not_called()

def test_gui_warns_about_output_before_creating_worker(qapp, monkeypatch):
    from src.ui import main_window as ui
    def missing(path):
        raise DestinationError("Unità non raggiungibile. Usa Sfoglia.")
    monkeypatch.setattr(ui, "prepare_destination", missing)
    warning = Mock()
    monkeypatch.setattr(ui.QMessageBox, "warning", warning)
    window = ui.MainWindow({"utenze": [], "impostazioni": {}})
    window.output.setText("U:/unavailable")
    window.start_download()
    assert window.worker is None
    warning.assert_called_once()
    assert "Sfoglia" in warning.call_args.args[2]
    window.close()
