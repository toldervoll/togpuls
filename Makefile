PY := venv/bin/python
PIP := venv/bin/pip

# macOS menylinje-app bygges med py2app, som trenger et framework-Python
# (Homebrew/python.org). Xcode/CommandLineTools sin python3 kan ikke signere
# bunten, så denne appen får sin egen venv adskilt fra hovedvenv-en.
MACOS_PY ?= python3.12
MACOS_VENV := macos/.venv
# Versjon for setup.py, DMG-navn og release-tag. Scoped til macOS-leveransen
# fordi web-siden enn så lenge bare ruller på main uten egen versjonering.
MACOS_VERSION := $(shell cat macos/VERSION)
MACOS_TAG := macos-v$(MACOS_VERSION)
MACOS_APP := macos/dist/Togpuls.app
MACOS_DMG := macos/dist/Togpuls-$(MACOS_VERSION).dmg
DMG_BACKGROUND := macos/installer/dmg-background.png

.DEFAULT_GOAL := help
.PHONY: help configure serve cli clean macos-run macos-app macos-sign macos-dmg macos-release macos-clean

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

macos-sign: macos-app  ## Ad-hoc-signer Togpuls.app (kreves for arm64)
	@codesign --force --deep --sign - "$(MACOS_APP)"
	@codesign --verify --verbose=2 "$(MACOS_APP)"

$(DMG_BACKGROUND): macos/installer/render_dmg_background.py $(MACOS_VENV)/.installed
	@$(MACOS_VENV)/bin/pip install --quiet Pillow
	@$(MACOS_VENV)/bin/python macos/installer/render_dmg_background.py "$@"

macos-dmg: macos-sign $(DMG_BACKGROUND)  ## Bygg signert DMG (drag-to-Applications)
	@command -v create-dmg >/dev/null || { \
	    echo "Trenger create-dmg (brew install create-dmg)."; \
	    exit 1; }
	@rm -f "$(MACOS_DMG)"
	create-dmg \
	    --volname "Togpuls $(MACOS_VERSION)" \
	    --background "$(DMG_BACKGROUND)" \
	    --window-pos 200 120 \
	    --window-size 640 460 \
	    --icon-size 96 \
	    --icon "Togpuls.app" 190 195 \
	    --app-drop-link 450 195 \
	    --hide-extension "Togpuls.app" \
	    --no-internet-enable \
	    "$(MACOS_DMG)" \
	    "$(MACOS_APP)"
	@echo "→ $(MACOS_DMG)"
	@shasum -a 256 "$(MACOS_DMG)"

macos-release:       ## Tag macos-v$(MACOS_VERSION) og push for å trigge release-workflow
	@test -z "$$(git status --porcelain)" || { \
	    echo "Working tree er ikke ren. Commit eller stash først."; exit 1; }
	@test "$$(git rev-parse --abbrev-ref HEAD)" = "main" || { \
	    echo "Taggar bare fra main (du står på $$(git rev-parse --abbrev-ref HEAD))."; \
	    exit 1; }
	@git fetch --quiet origin main
	@test "$$(git rev-parse HEAD)" = "$$(git rev-parse origin/main)" || { \
	    echo "HEAD er ikke i sync med origin/main. Push eller pull først."; exit 1; }
	@if git rev-parse "$(MACOS_TAG)" >/dev/null 2>&1; then \
	    echo "Tag $(MACOS_TAG) finnes allerede. Bump macos/VERSION først."; exit 1; fi
	@echo "Tagger $(MACOS_TAG) …"
	git tag -a "$(MACOS_TAG)" -m "macOS release $(MACOS_VERSION)"
	git push origin "$(MACOS_TAG)"
	@echo "→ $(MACOS_TAG) pushet. Workflow kjører på github.com/kengu/togpuls/actions"

macos-clean:         ## Remove the macOS venv and build artifacts
	rm -rf $(MACOS_VENV) macos/build macos/dist $(DMG_BACKGROUND)
