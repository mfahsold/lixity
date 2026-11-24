.PHONY: help install install-dev test browser-tools browser browser-changed browser-full lint typecheck workflow-check check fast-check audit build github-check rc-gate release-check release-prepare release-verify screenshots videos examples brand-assets media clean-caches clean docs-check docs-generated-check docs-sync pages-deploy pages-verify run start serve stop restart status doctor

PYTHON ?= python3
VENV ?= .venv
VPY := $(VENV)/bin/python
SCRIPT_PYTHON := $(if $(wildcard $(VPY)),$(VPY),$(PYTHON))
RUFF_CACHE ?= .ruff_cache
MYPY_CACHE ?= .mypy_cache
PYTEST_CACHE ?= .pytest_cache
PYTEST_FLAGS := -W error -q -p no:asyncio -o cache_dir=$(PYTEST_CACHE)
ACTIONLINT ?= actionlint
BROWSER_JOBS ?= $(shell (nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4) | awk '{j=int($$1/2); if(j<2)j=2; if(j>8)j=8; print j}')
BROWSER_TOOLS_DIR ?= $(HOME)/.local/share/lixity/browser-tools
PLAYWRIGHT_VERSION ?= 1.59.1
AXE_CORE_VERSION ?= 4.13.0
PYTEST_ARGS ?= -n auto

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

test: ## Run the full test suite (warnings as errors, slowest cases reported)
	PYTHONPATH="$(CURDIR)/src" "$(VPY)" -m pytest $(PYTEST_FLAGS) --durations=15 $(PYTEST_ARGS)

browser-tools: ## Install isolated versioned Playwright, Chromium and axe-core
	npm install --prefix "$(BROWSER_TOOLS_DIR)" playwright@$(PLAYWRIGHT_VERSION) axe-core@$(AXE_CORE_VERSION)
	PLAYWRIGHT_BROWSERS_PATH="$(BROWSER_TOOLS_DIR)/browsers" "$(BROWSER_TOOLS_DIR)/node_modules/.bin/playwright" install chromium

browser: ## Run the everyday browser checks (needs Node and Playwright)
	$(SCRIPT_PYTHON) scripts/run_browser_suites.py --group fast --jobs $(BROWSER_JOBS)

browser-changed: ## Run only the browser suites for modified paths (safe fallback to full)
	$(SCRIPT_PYTHON) scripts/run_browser_suites.py --changed --jobs $(BROWSER_JOBS)

browser-full: ## Run every browser suite with the full locale/theme/pointer matrix before a release
	LIXITY_BROWSER_FULL=1 $(SCRIPT_PYTHON) scripts/run_browser_suites.py --jobs $(BROWSER_JOBS) $(BROWSER_ARGS)

lint: ## Ruff lint (src, tests, scripts)
	RUFF_CACHE_DIR=$(RUFF_CACHE) "$(VPY)" -m ruff check src tests scripts

typecheck: ## mypy --strict on the package
	MYPY_CACHE_DIR=$(MYPY_CACHE) "$(VPY)" -m mypy --strict src

workflow-check: ## Lint GitHub workflows (needs actionlint; override ACTIONLINT for its path)
	"$(ACTIONLINT)" .github/workflows/*.yml

audit: ## Dependency audit baseline (needs the dev extra with pip-audit)
	$(VPY) -m pip_audit . --progress-spinner off

check: lint typecheck test ## Canonical local source checks: Ruff, strict mypy and the full test suite

fast-check: lint typecheck docs-generated-check ## Quick pre-commit check without full pytest (~5s)

build: ## Build fresh source-verified sdist + wheel and checksums into dist/
	$(VPY) scripts/check_release.py --build

release-check: ## Validate the tag first, then test once, check generated docs, audit and verify artifacts
	@test -n "$(RELEASE_TAG)" || (echo "Set RELEASE_TAG=vX.Y.Z to match the source version"; exit 1)
	$(VPY) scripts/check_release.py --source-only --require-release-notes --tag "$(RELEASE_TAG)"
	$(MAKE) check docs-generated-check audit
	$(VPY) scripts/check_release.py --build --smoke --tag "$(RELEASE_TAG)"

release-prepare: ## Prepare a new release: bump version, draft notes, sync docs (make release-prepare VERSION=X.Y.Z)
	@test -n "$(VERSION)" || (echo "Set VERSION=X.Y.Z (e.g. make release-prepare VERSION=0.8.1)"; exit 1)
	PYTHONPATH=src $(SCRIPT_PYTHON) scripts/prepare_release.py "$(VERSION)" $(if $(RELEASE_DATE),--release-date "$(RELEASE_DATE)")

github-check: ## Inspect gh CLI, attestation support, worktrees and optional RELEASE_TAG channel state
	$(SCRIPT_PYTHON) scripts/release_channels.py doctor --root . --repo mfahsold/lixity $(if $(RELEASE_TAG),--tag "$(RELEASE_TAG)",)

rc-gate: ## Trigger pre-tag release-candidate qualification on main (source, sharded browser, Windows/macOS)
	env -u GH_TOKEN -u GITHUB_TOKEN -u GIT_ASKPASS -u SSH_ASKPASS gh workflow run rc.yml --ref main

RELEASE_VERIFY_ROOT ?= .

release-verify: ## Verify a published release (RELEASE_TAG=vX.Y.Z, optionally RELEASE_VERIFY_ARGS)
	@test -n "$(RELEASE_TAG)" || (echo "Set RELEASE_TAG=vX.Y.Z to verify a published release"; exit 1)
	@commit=$$(git -C "$(RELEASE_VERIFY_ROOT)" rev-parse --verify "$(RELEASE_TAG)^{commit}") && \
		$(SCRIPT_PYTHON) scripts/release_channels.py verify-release --root "$(RELEASE_VERIFY_ROOT)" --tag "$(RELEASE_TAG)" --expected-commit "$$commit" --repo mfahsold/lixity --dist "$(or $(RELEASE_VERIFY_DIR),dist-verified)" --check-zenodo $(RELEASE_VERIFY_ARGS)

screenshots: ## Regenerate docs/screenshots (needs headless Chromium)
	PYTHONPATH=src $(VPY) scripts/make_screenshots.py

videos: ## Regenerate public walkthrough media locally (needs Chromium and ffmpeg)
	PYTHONPATH=src $(VPY) scripts/make_screenshots.py --video
	PYTHONPATH=src $(VPY) scripts/make_videos.py

examples: ## Regenerate the published example reports and their PDFs
	PYTHONPATH=src $(VPY) scripts/build_examples.py

brand-assets: ## Regenerate multi-size/multi-format brand icons and favicon from docs/assets/mark.svg
	$(SCRIPT_PYTHON) scripts/build_brand_assets.py

media: ## Regenerate all brand assets, screenshots, videos and published examples
	$(MAKE) brand-assets
	$(MAKE) screenshots
	$(MAKE) videos
	$(MAKE) examples

docs-generated-check: ## Check generated version pins, documentation bundle and guide alternatives
	PYTHONPATH=src $(SCRIPT_PYTHON) scripts/sync_docs.py --all --check

docs-check: docs-generated-check ## Standalone documentation checks, including staged-site links and generated content
	PYTHONPATH=src "$(VPY)" -m pytest $(PYTEST_FLAGS) tests/test_pages.py tests/test_guide_markdown.py tests/test_documentation.py $(PYTEST_ARGS)

docs-sync: ## Synchronize documentation version references to match __version__
	PYTHONPATH=src $(SCRIPT_PYTHON) scripts/sync_docs.py --all

pages-deploy: docs-generated-check ## Trigger the GitHub Pages deployment workflow on main
	env -u GH_TOKEN -u GITHUB_TOKEN -u GIT_ASKPASS -u SSH_ASKPASS gh workflow run pages.yml --ref main

pages-verify: ## Verify that live Pages matches the checked-out commit and staged content
	@commit=$$(git rev-parse --verify HEAD) && \
		$(SCRIPT_PYTHON) scripts/release_channels.py verify-pages --root . --expected-commit "$$commit"

clean-caches: ## Remove tool and test caches without deleting dist/
	rm -rf $(PYTEST_CACHE) $(MYPY_CACHE) $(RUFF_CACHE) htmlcov .coverage

clean: clean-caches ## Remove caches and build artifacts
	rm -rf build dist *.egg-info src/*.egg-info

PORT_OPTION = $(if $(strip $(LIXITY_PORT)),--port "$(LIXITY_PORT)")

run: ## Run the empty dashboard in the foreground (Ctrl+C stops it).
	"$(VPY)" -m lixity serve --no-project $(PORT_OPTION)

start: ## Start the packaged managed dashboard.
	"$(VPY)" -m lixity service start $(PORT_OPTION)

serve: start ## Compatibility alias for managed start; use run for foreground.

stop: ## Stop the managed Lixity dashboard instance.
	"$(VPY)" -m lixity service stop $(PORT_OPTION)

restart: ## Restart the managed instance with its saved startup settings.
	"$(VPY)" -m lixity service restart $(PORT_OPTION)

status: ## Inspect the managed instance without modifying manuscript data.
	"$(VPY)" -m lixity service status $(PORT_OPTION)

doctor: ## Check the checkout CLI and the managed instance on LIXITY_PORT.
	"$(VPY)" -m lixity doctor $(PORT_OPTION)
