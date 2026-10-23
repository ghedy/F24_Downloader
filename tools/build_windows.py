"""Build Windows x64 installer from public sources only. No source ZIP produced."""
import argparse
from datetime import datetime
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import __version__
from tools.prepare_release import release_files, private_values


def run(command, **kwargs):
    subprocess.run([str(value) for value in command], check=True, **kwargs)


def prepare_notices(destination):
    destination.mkdir(parents=True)
    components = []
    for distribution in metadata.distributions():
        name = distribution.metadata["Name"]
        components.append({"name": name, "version": distribution.version})
        for entry in distribution.files or ():
            if not any(term in str(entry).lower() for term in ("license", "copying", "copyright", "notice")):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file() and source.suffix.lower() not in {".py", ".pyc", ".exe", ".dll"}:
                relative = Path(str(entry))
                if relative.is_absolute() or ".." in relative.parts:
                    continue
                target = destination / name / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    shutil.copyfile(Path(sys.base_prefix) / "LICENSE.txt", destination / "Python-LICENSE.txt")
    shutil.copytree(ROOT / "packaging/licenses", destination / "Qt-LGPL", dirs_exist_ok=True)
    (destination / "components.json").write_text(json.dumps(components, indent=2), encoding="utf-8")
    (destination / "README.txt").write_text(
        "F24 Downloader - componenti di terzi\n\n"
        "Python: https://www.python.org/downloads/source/\n"
        "Qt / PySide6 6.11.1: librerie condivise non modificate, LGPLv3.\n"
        "Sorgenti Qt: https://download.qt.io/archive/qt/6.11/6.11.1/single/\n"
        "Sorgenti PySide6: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.11.1-src/\n"
        "Le DLL Qt possono essere sostituite con build compatibili nella cartella _internal.\n"
        "E' consentito il reverse engineering per il debug di modifiche alle librerie LGPL.\n"
        "Playwright 1.61.0 e Firefox: distribuzioni non modificate del browser Playwright.\n"
        "Patch e istruzioni per ricostruire Firefox: \n"
        "https://github.com/microsoft/playwright/tree/v1.61.0/browser_patches/firefox\n"
        "Firefox: consultare about:license nel browser incluso per licenze e copyright.\n"
        "Codice sorgente Firefox: https://archive.mozilla.org/pub/firefox/releases/\n"
        "F24 Downloader (MIT): https://github.com/ghedy/F24_Downloader\n",
        encoding="utf-8")


def build(iscc):
    if os.name != "nt" or sys.version_info[:2] != (3, 14) or struct.calcsize("P") != 8:
        raise RuntimeError("Use Python 3.14 x64 on Windows")
    if not iscc.is_file():
        raise FileNotFoundError("Inno Setup ISCC.exe is required")
    for line in (ROOT / "packaging/requirements-windows-build.txt").read_text(encoding="utf-8-sig").splitlines():
        if "==" in line:
            name, version = line.strip().split("==", 1)
            if metadata.version(name) != version:
                raise RuntimeError("Install the exact build requirements first: " + name)
    environment = os.environ.copy()
    for key in list(environment):
        if key.upper().startswith(("PYTHON", "QT_", "PYSIDE")):
            environment.pop(key)
    windows = Path(environment.get("SystemRoot", "C:/Windows"))
    environment["PATH"] = os.pathsep.join(str(path) for path in [
        windows / "System32", windows, Path(sys.executable).parent,
        Path(sys.base_prefix), Path(sys.base_prefix) / "DLLs"])
    environment.update(PLAYWRIGHT_BROWSERS_PATH="0", PYTHONNOUSERSITE="1")
    paths, private = release_files(), private_values(ROOT)
    work = ROOT / "build/windows" / (__version__ + "-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    source = work / "source"
    source.mkdir(parents=True)
    # Export only public allowlisted files; config.json and credentials never enter staging.
    for path in paths:
        payload = path.read_bytes()
        if any(value.encode("utf-8") in payload for value in private):
            raise RuntimeError("Private data found in public source: " + str(path.relative_to(ROOT)))
        target = source / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    run([sys.executable, "-m", "playwright", "install", "firefox"], env=environment)
    notices = work / "third-party"
    prepare_notices(notices)
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QPixmap
    from PIL import Image
    app = QApplication.instance() or QApplication([])
    pixmap = QPixmap(str(source / "src/ui/icons/f24-downloader.svg"))
    if pixmap.isNull():
        raise RuntimeError("Missing application icon")
    png, icon = work / "icon.png", work / "F24Downloader.ico"
    pixmap.save(str(png))
    Image.open(png).save(icon, sizes=[(16,16), (32,32), (48,48), (64,64), (128,128)])
    bundle_dist = work / "dist"
    run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir",
        "--name", "F24Downloader", "--icon", icon, "--distpath", bundle_dist,
        "--workpath", work / "pyinstaller", "--specpath", work,
        "--paths", source, "--hidden-import", "PySide6.QtSvg",
        "--add-data", str(source / "src/ui/icons") + ";src/ui/icons",
        "--add-data", str(notices) + ";third-party", source / "main.py"],
        cwd=source, env=environment)
    bundle = bundle_dist / "F24Downloader"
    shutil.copyfile(source / "LICENSE", bundle / "LICENSE.txt")
    shutil.copyfile(source / "docs/INSTALLAZIONE_WINDOWS.md", bundle / "LEGGIMI.txt")
    # Reject accidental inclusion of local configurations/documents, even in dependencies.
    for path in bundle.rglob("*"):
        if path.is_file() and (path.name.startswith(("config.json", "credentials.bin")) or path.suffix.lower() == ".pdf"):
            raise RuntimeError("Unexpected private/document file in bundle")
    report = work / "installation-check.json"
    smoke_env = environment.copy()
    smoke_env.update(PLAYWRIGHT_BROWSERS_PATH=str(work / "empty-browser-cache"), QT_QPA_PLATFORM="offscreen")
    # External cache deliberately absent: the executable must use its bundled Firefox.
    run([bundle / "F24Downloader.exe", "--check-installation", report], env=smoke_env, timeout=120)
    if not json.loads(report.read_text(encoding="utf-8"))["ok"]:
        raise RuntimeError("Frozen executable check failed: " + str(report))
    artifacts = ROOT / "dist" / __version__
    artifacts.mkdir(parents=True, exist_ok=True)
    run([iscc, "/DAppVersion=" + __version__, "/DBundleDir=" + str(bundle),
        "/DArtifactDir=" + str(artifacts), "/DAppIcon=" + str(icon), "/DSourceDir=" + str(source),
        source / "packaging/F24Downloader.iss"])
    installer = artifacts / f"F24-Downloader-{__version__}-windows-x64-setup.exe"
    digest = hashlib.file_digest(installer.open("rb"), "sha256").hexdigest()
    installer.with_suffix(".exe.sha256").write_text(digest + "  " + installer.name + "\n", encoding="utf-8")
    shutil.copyfile(report, artifacts / "installation-check.json")
    shutil.copyfile(report.with_suffix(".png"), artifacts / "installation-check.png")
    print("Installer verified:", installer)
    print("SHA256:", digest)
    return installer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", type=Path, required=True)
    build(parser.parse_args().iscc.resolve())
