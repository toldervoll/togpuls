"""Bygg Togpuls menylinje-app til en standalone .app med py2app.

    pip install py2app
    python setup.py py2app        # standalone bundle i dist/Togpuls.app

LSUIElement=False gir appen et Dock-ikon (og plass i app-veksleren), som er
den pålitelige reserveveien til menyen når menylinje-ikonet skjules bak notch.
Dock-menyen og den globale hurtigtasten settes opp i togpuls_bar.py.

Versjonen leses fra repo-rot-fila ``VERSION`` så ``setup.py``, Makefile og
release-workflowen alltid er enige.
"""

from pathlib import Path

from setuptools import setup

VERSION = (Path(__file__).resolve().parent.parent / "VERSION").read_text().strip()

APP = ["togpuls_bar.py"]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "assets/Togpuls.icns",
    # Importeres lazy i koden, så py2app må få beskjed om å bundle den.
    "includes": ["WebKit"],
    "plist": {
        "CFBundleName": "Togpuls",
        "CFBundleDisplayName": "Togpuls",
        "CFBundleIdentifier": "no.kengu.togpuls.menubar",
        "CFBundleVersion": VERSION,
        "CFBundleShortVersionString": VERSION,
        "LSUIElement": False,
    },
    "packages": ["rumps"],
}

setup(
    app=APP,
    name="Togpuls",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
