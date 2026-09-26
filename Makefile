.PHONY: help install install-dev test lint typecheck check build screenshots clean

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

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache \
	  .ruff_cache htmlcov .coverage
