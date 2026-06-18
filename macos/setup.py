"""Bygg Togpuls menylinje-app til en standalone .app med py2app.

    pip install py2app
    python setup.py py2app        # standalone bundle i dist/Togpuls.app

LSUIElement=True gjør den til en ren menylinje-app uten dock-ikon.
"""

from setuptools import setup

APP = ["togpuls_bar.py"]
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "Togpuls",
        "CFBundleDisplayName": "Togpuls",
        "CFBundleIdentifier": "no.kengu.togpuls.menubar",
        "CFBundleVersion": "1.0",
        "CFBundleShortVersionString": "1.0",
        "LSUIElement": True,
    },
    "packages": ["rumps"],
}

setup(
    app=APP,
    name="Togpuls",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
