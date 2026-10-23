from unittest.mock import Mock
import pytest
import main
from config import config_manager as manager
from src.ui import main_window as ui
from PySide6 import QtWidgets


def test_startup_warns_then_opens_window_with_recovered_settings(qapp, monkeypatch):
    config = {"utenze": [], "impostazioni": {}, "credenziali": {}}
    monkeypatch.setattr(manager, "carica_config_avvio", lambda: (config, "Credenziali da reinserire"))
    monkeypatch.setattr(QtWidgets, "QApplication", lambda _: qapp)
    monkeypatch.setattr(qapp, "exec", lambda: 0)
    warning, critical, window, save = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", warning)
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", critical)
    monkeypatch.setattr(ui, "MainWindow", window)
    monkeypatch.setattr(manager, "salva_config", save)
    assert main.main() == 0
    warning.assert_called_once()
    critical.assert_not_called()
    window.assert_called_once_with(config)
    window.return_value.show.assert_called_once()
    save.assert_not_called()


@pytest.mark.parametrize("error,title", [
    (PermissionError("private path"), "Cartella di configurazione non accessibile"),
    (ValueError("private contents"), "Configurazione non valida"),
    (RuntimeError("private secret"), "Configurazione non disponibile"),
])
def test_startup_errors_are_distinct_and_hide_raw_exception(qapp, monkeypatch, error, title):
    def fail():
        raise error
    monkeypatch.setattr(manager, "carica_config_avvio", fail)
    monkeypatch.setattr(QtWidgets, "QApplication", lambda _: qapp)
    critical, warning, window = Mock(), Mock(), Mock()
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical", critical)
    monkeypatch.setattr(QtWidgets.QMessageBox, "warning", warning)
    monkeypatch.setattr(ui, "MainWindow", window)
    assert main.main() == 1
    assert critical.call_args.args[1] == title
    assert str(error) not in critical.call_args.args[2]
    warning.assert_not_called()
    window.assert_not_called()
