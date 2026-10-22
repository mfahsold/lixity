.PHONY: help install install-dev test browser browser-changed browser-full lint typecheck workflow-check check audit build release-check screenshots videos examples clean docs-check docs-generated-check docs-sync run start serve stop restart status

PYTHON ?= python3
VENV ?= .venv
VPY := $(VENV)/bin/python
RUFF_CACHE ?= /tmp/ruff_cache
MYPY_CACHE ?= /tmp/mypy_cache
PYTEST_CACHE ?= /tmp/pytest_cache
ACTIONLINT ?= actionlint

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

browser: ## Run the everyday browser checks (needs Node and Playwright)
	$(PYTHON) scripts/run_browser_suites.py --group fast --jobs 3

browser-changed: ## Run only the browser suites for modified paths (safe fallback to full)
	$(PYTHON) scripts/run_browser_suites.py --changed --jobs 3

browser-full: ## Run every browser suite before a release
	$(PYTHON) scripts/run_browser_suites.py --jobs 3

lint: ## Ruff lint (src, tests, scripts)
	RUFF_CACHE_DIR=$(RUFF_CACHE) $(VENV)/bin/ruff check src tests scripts

typecheck: ## mypy --strict on the package
	MYPY_CACHE_DIR=$(MYPY_CACHE) $(VENV)/bin/mypy --strict src

workflow-check: ## Lint GitHub workflows (needs actionlint; override ACTIONLINT for its path)
	"$(ACTIONLINT)" .github/workflows/*.yml

audit: ## Dependency audit baseline (needs the dev extra with pip-audit)
	$(VPY) -m pip_audit . --progress-spinner off

check: lint typecheck test ## Canonical local source checks: Ruff, strict mypy and the full test suite

build: ## Build fresh source-verified sdist + wheel and checksums into dist/
	$(VPY) scripts/check_release.py --build

release-check: check docs-generated-check audit ## Local release gate; test once, check generated docs, audit and verify artifacts
	@test -n "$(RELEASE_TAG)" || (echo "Set RELEASE_TAG=vX.Y.Z to match the source version"; exit 1)
	$(VPY) scripts/check_release.py --build --smoke --tag "$(RELEASE_TAG)"

screenshots: ## Regenerate docs/screenshots (needs headless Chromium)
	$(PYTHON) scripts/make_screenshots.py

videos: ## Record and publish the walkthrough videos (needs Chromium and ffmpeg)
	$(PYTHON) scripts/make_screenshots.py --video
	$(VPY) scripts/make_videos.py

examples: ## Regenerate the published example reports and their PDFs
	PYTHONPATH=src $(VPY) scripts/build_examples.py

docs-generated-check: ## Check generated version pins, documentation bundle and guide alternatives
	$(PYTHON) scripts/sync_docs.py --check
	$(PYTHON) scripts/build_llms_full.py --check
	$(PYTHON) scripts/build_guide_markdown.py --check

docs-check: docs-generated-check ## Standalone documentation checks, including staged-site links and generated content
	PYTHONPATH=src $(VPY) -m pytest tests/test_pages.py tests/test_guide_markdown.py tests/test_documentation.py -q -W error -p no:asyncio -o cache_dir=$(PYTEST_CACHE)

docs-sync: ## Synchronize documentation version references to match __version__
	$(PYTHON) scripts/sync_docs.py
	$(PYTHON) scripts/build_llms_full.py
	$(PYTHON) scripts/build_guide_markdown.py

clean: ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info .pytest_cache .mypy_cache \
	  .ruff_cache htmlcov .coverage

LIXITY_PORT ?= 8765

run: ## Run the empty dashboard in the foreground (Ctrl+C stops it).
	"$(VPY)" -m lixity serve --no-project --port $(LIXITY_PORT)

start: ## Start the packaged managed dashboard (default port 8765).
	"$(VPY)" -m lixity service start --port $(LIXITY_PORT)

serve: start ## Compatibility alias for managed start; use run for foreground.

stop: ## Stop the managed Lixity dashboard instance.
	"$(VPY)" -m lixity service stop --port $(LIXITY_PORT)

restart: ## Restart the managed instance with its saved startup settings.
	"$(VPY)" -m lixity service restart --port $(LIXITY_PORT)

status: ## Inspect the managed instance without modifying manuscript data.
	"$(VPY)" -m lixity service status --port $(LIXITY_PORT)
