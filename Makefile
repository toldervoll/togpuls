PY := venv/bin/python
PIP := venv/bin/pip

# macOS menylinje-app bygges med py2app, som trenger et framework-Python
# (Homebrew/python.org). Xcode/CommandLineTools sin python3 kan ikke signere
# bunten, så denne appen får sin egen venv adskilt fra hovedvenv-en.
MACOS_PY ?= python3.12
MACOS_VENV := macos/.venv

.DEFAULT_GOAL := help
.PHONY: help configure serve cli clean macos-run macos-app macos-clean

help:                ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	    awk 'BEGIN {FS = ":.*?## "} {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

configure: venv/.installed  ## Create venv and install dependencies

venv/.installed: requirements.txt
	@if [ -d venv ] && ! $(PIP) --version >/dev/null 2>&1; then \
	    echo "venv looks stale (pip broken — likely moved from another path); rebuilding"; \
	    rm -rf venv; \
	fi
	@test -d venv || python3 -m venv venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt
	@touch venv/.installed

serve: configure     ## Run the API + widget (http://localhost:8000)
	@echo "togpuls → http://localhost:$${TOGPULS_PORT:-8000}/"
	@$(PY) -m togpuls.serve

cli: configure       ## Run the one-shot CLI analyser (JSON to stdout)
	@$(PY) -m togpuls.main

clean:               ## Remove the virtualenv
	rm -rf venv

$(MACOS_VENV)/.installed: macos/requirements.txt
	@command -v $(MACOS_PY) >/dev/null || { \
	    echo "Trenger $(MACOS_PY) (Homebrew: brew install python@3.12)."; \
	    echo "Xcode-python kan ikke signere .app. Overstyr med: make macos-app MACOS_PY=python3.13"; \
	    exit 1; }
	@test -d $(MACOS_VENV) || $(MACOS_PY) -m venv $(MACOS_VENV)
	$(MACOS_VENV)/bin/pip install --quiet --upgrade pip
	$(MACOS_VENV)/bin/pip install --quiet -r macos/requirements.txt
	@touch $(MACOS_VENV)/.installed

macos-run: $(MACOS_VENV)/.installed  ## Run the macOS menu bar app from source
	@$(MACOS_VENV)/bin/python macos/togpuls_bar.py

macos-app: $(MACOS_VENV)/.installed  ## Build standalone macos/dist/Togpuls.app (py2app)
	$(MACOS_VENV)/bin/pip install --quiet py2app
	cd macos && .venv/bin/python setup.py py2app
	@echo "→ macos/dist/Togpuls.app"

macos-clean:         ## Remove the macOS venv and build artifacts
	rm -rf $(MACOS_VENV) macos/build macos/dist
