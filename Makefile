.PHONY: help install install-dev test lint typecheck check build screenshots clean

PYTHON ?= python3
VENV ?= .venv
VPY := $(VENV)/bin/python
VPIP := $(VENV)/bin/pip
RUFF_CACHE ?= /tmp/ruff_cache

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Editable install into the current environment
	$(PYTHON) -m pip install -e .

install-dev: ## Create .venv and install with dev extras
	$(PYTHON) -m venv $(VENV)
	$(VPIP) install -U pip
	$(VPIP) install -e ".[dev]"

test: ## Run the full test suite (warnings as errors)
	PYTHONPATH=src $(VPY) -m pytest -W error -q -p no:asyncio

lint: ## Ruff lint (src, tests, scripts)
	RUFF_CACHE_DIR=$(RUFF_CACHE) $(VENV)/bin/ruff check src tests scripts

typecheck: ## mypy --strict on the package
	$(VENV)/bin/mypy --strict src

check: lint typecheck test ## Everything CI cares about locally

build: ## Build sdist + wheel into dist/
	$(VPY) -m build

screenshots: ## Regenerate docs/screenshots (needs headless Chromium)
	$(PYTHON) scripts/make_screenshots.py

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache \
	  .ruff_cache htmlcov .coverage
