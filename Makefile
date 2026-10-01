.PHONY: help install install-dev test lint typecheck check build screenshots clean docs-check docs-sync serve stop

PYTHON ?= python3
VENV ?= .venv
VPY := $(VENV)/bin/python
RUFF_CACHE ?= /tmp/ruff_cache
MYPY_CACHE ?= /tmp/mypy_cache
PYTEST_CACHE ?= /tmp/pytest_cache

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Create .venv and install the local CLI/API without dev tools
	$(PYTHON) -m venv "$(VENV)"
	"$(VPY)" -m pip install -e .
	"$(VPY)" -m pip check
	"$(VPY)" -m lixity.cli --version

install-dev: ## Create .venv and install with dev extras
	$(PYTHON) -m venv "$(VENV)"
	"$(VPY)" -m pip install -e ".[dev]"
	"$(VPY)" -m pip check
	"$(VPY)" -m lixity.cli --version

test: ## Run the full test suite (warnings as errors)
	PYTHONPATH=src $(VPY) -m pytest -W error -q -p no:asyncio -o cache_dir=$(PYTEST_CACHE)

lint: ## Ruff lint (src, tests, scripts)
	RUFF_CACHE_DIR=$(RUFF_CACHE) $(VENV)/bin/ruff check src tests scripts

typecheck: ## mypy --strict on the package
	MYPY_CACHE_DIR=$(MYPY_CACHE) $(VENV)/bin/mypy --strict src

check: lint typecheck test ## Everything CI cares about locally

build: ## Build sdist + wheel into dist/
	$(VPY) -m build

screenshots: ## Regenerate docs/screenshots (needs headless Chromium)
	$(PYTHON) scripts/make_screenshots.py

docs-check: ## Check documentation version consistency and link integrity
	$(PYTHON) scripts/sync_docs.py --check
	PYTHONPATH=src $(VPY) -m pytest tests/test_documentation.py -W error -q -p no:asyncio -o cache_dir=$(PYTEST_CACHE)

docs-sync: ## Synchronize documentation version references to match __version__
	$(PYTHON) scripts/sync_docs.py

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache \
	  .ruff_cache htmlcov .coverage

LIXITY_PORT ?= 8765
LIXITY_LAUNCHER := $(wildcard scripts/lixity-start.sh)

serve: ## Start the managed Lixity dashboard (default port 8765). Override with LIXITY_PORT.
	@if [ -n "$(LIXITY_LAUNCHER)" ]; then \
	    bash $(LIXITY_LAUNCHER) start --port $(LIXITY_PORT); \
	else \
	    echo "[--]  scripts/lixity-start.sh missing; starting in the foreground instead."; \
	    $(VENV)/bin/lixity serve --host 127.0.0.1 --port $(LIXITY_PORT); \
	fi

stop: ## Stop the managed Lixity dashboard instance.
	@if [ -n "$(LIXITY_LAUNCHER)" ]; then \
	    bash $(LIXITY_LAUNCHER) stop --port $(LIXITY_PORT); \
	else \
	    pids=$$(lsof -ti :$(LIXITY_PORT) 2>/dev/null || true); \
	    if [ -n "$$pids" ]; then \
	        kill $$pids && echo "[OK]  Stopped PID(s) $$pids on port $(LIXITY_PORT)."; \
	    else \
	        echo "[--]  Nothing is listening on port $(LIXITY_PORT)."; \
	    fi; \
	fi
