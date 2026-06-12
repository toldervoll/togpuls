PY := venv/bin/python
PIP := venv/bin/pip

.DEFAULT_GOAL := help
.PHONY: help configure serve cli clean

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
