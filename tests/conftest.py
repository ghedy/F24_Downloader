import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
from pathlib import Path
import uuid

def pytest_configure(config):
    if config.option.basetemp is None:
        # Directory nuova dentro al progetto; evita ACL di vecchi temporanei globali.
        root = Path(__file__).resolve().parents[1]
        (root / ".pytest_tmp").mkdir(exist_ok=True)
        config.option.basetemp = str(root / ".pytest_tmp" / ("run-" + uuid.uuid4().hex))

@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app
