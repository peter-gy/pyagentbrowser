.DEFAULT_GOAL := help

PYTHON_SOURCES = src tests scripts examples
PYTHON_VERSIONS ?= 3.10 3.11 3.12 3.13 3.14
RUST_TOOLCHAIN ?= stable
RUST_CARGO = rustup run $(RUST_TOOLCHAIN) cargo
RUSTFMT = $(shell rustup which --toolchain $(RUST_TOOLCHAIN) rustfmt 2>/dev/null || printf rustfmt)
DIST_DIR = target/wheels

.PHONY: help
help: ## Show this help
	@awk 'BEGIN { printf "\nUsage:\n  make <target>\n" } \
		/^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5); next } \
		/^[a-zA-Z0-9_-]+:.*##/ { \
			target = $$1; sub(/:.*/, "", target); \
			help = $$0; sub(/^.*## /, "", help); \
			printf "  \033[36m%-20s\033[0m %s\n", target, help; \
		}' $(MAKEFILE_LIST)

##@ Setup

.PHONY: check-prereqs
check-prereqs:
	@command -v uv >/dev/null || { echo "uv is required" >&2; exit 1; }
	@command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
	@test -f .gitmodules || { echo ".gitmodules is required" >&2; exit 1; }
	@git config --file .gitmodules --get submodule.third_party/agent-browser.url >/dev/null || { echo "agent-browser submodule is not configured" >&2; exit 1; }
	@command -v rustup >/dev/null || { echo "rustup is required" >&2; exit 1; }
	@rustup which --toolchain $(RUST_TOOLCHAIN) cargo >/dev/null
	@rustup which --toolchain $(RUST_TOOLCHAIN) rustc >/dev/null
	@rustup which --toolchain $(RUST_TOOLCHAIN) rustfmt >/dev/null

.PHONY: install
install: check-prereqs ## Initialize submodules and install the editable package
	git submodule update --init --recursive
	uv sync
	uv run maturin develop

##@ Quality

.PHONY: format
format: ## Format Python and first-party Rust sources
	uv run ruff format $(PYTHON_SOURCES) pyproject.toml
	uv run ruff check --fix $(PYTHON_SOURCES)
	$(RUST_CARGO) fmt --manifest-path Cargo.toml
	$(RUSTFMT) --edition 2024 crates/pyagentbrowser/build.rs
	$(RUSTFMT) --edition 2021 crates/agent-browser-adapter/build.rs

.PHONY: lint
lint: ## Check lockfile, formatting, linting, docs, and examples
	uv lock --check
	uv run ruff format --check $(PYTHON_SOURCES) pyproject.toml
	uv run ruff check
	$(MAKE) docs
	$(MAKE) examples

.PHONY: typecheck
typecheck: ## Run Python type checks
	uv run --extra cdp ty check

##@ Tests

.PHONY: test
test: ## Run fast current-interpreter tests without browser coverage
	uv run pytest -q -m "not integration"

.PHONY: test-integration
test-integration: ## Run real-browser tests and fail on skipped coverage
	chrome_path="$$(uv run python scripts/check_chrome.py)" && \
	PYAGENTBROWSER_CHROME="$$chrome_path" \
	PYAGENTBROWSER_FAIL_ON_SKIP=1 \
	uv run --extra cdp pytest -q -m integration

.PHONY: test-python-matrix
test-python-matrix: ## Run pytest and native-extension smoke across PYTHON_VERSIONS
	@set -e; \
	for version in $(PYTHON_VERSIONS); do \
		env_name=$$(printf '%s' "$$version" | tr -d '.'); \
		echo "==> Python $$version"; \
		UV_PROJECT_ENVIRONMENT=.venv$$env_name uv run --python $$version python -c 'from pyagentbrowser import Browser; import pyagentbrowser._native as native; assert Browser; assert native.__agent_browser_version__'; \
		UV_PROJECT_ENVIRONMENT=.venv$$env_name uv run --python $$version pytest -q; \
	done

##@ Rust

.PHONY: rust-check
rust-check: ## Run Rust format checks, clippy -D warnings, and cargo check
	$(RUST_CARGO) fmt --manifest-path Cargo.toml -- --check
	$(RUSTFMT) --edition 2024 --check crates/pyagentbrowser/build.rs
	$(RUSTFMT) --edition 2021 --check crates/agent-browser-adapter/build.rs
	$(RUST_CARGO) clippy -p pyagentbrowser --all-features --lib --no-deps -- -D warnings
	$(RUST_CARGO) clippy --manifest-path crates/agent-browser-adapter/Cargo.toml --all-targets --all-features -- -D warnings
	$(RUST_CARGO) check

.PHONY: rust-test
rust-test: ## Run Rust tests and adapter smoke tests
	$(RUST_CARGO) test
	$(RUST_CARGO) test --manifest-path crates/agent-browser-adapter/Cargo.toml --test smoke

.PHONY: rust
rust: rust-check rust-test ## Run all Rust checks and tests

##@ Packaging

.PHONY: package
package: ## Build wheel/sdist artifacts and run artifact/install smoke checks
	rm -rf $(DIST_DIR)
	mkdir -p $(DIST_DIR)
	@for version in $(PYTHON_VERSIONS); do \
		env_name=$$(printf '%s' "$$version" | tr -d '.'); \
		echo "==> Building wheel for Python $$version"; \
		CARGO="$$(rustup which --toolchain $(RUST_TOOLCHAIN) cargo)" \
		RUSTC="$$(rustup which --toolchain $(RUST_TOOLCHAIN) rustc)" \
		UV_PROJECT_ENVIRONMENT=.venvbuild$$env_name \
		uv run --no-project --python $$version --with "maturin>=1.11.5" maturin build --release --out $(DIST_DIR); \
	done
	CARGO="$$(rustup which --toolchain $(RUST_TOOLCHAIN) cargo)" \
	RUSTC="$$(rustup which --toolchain $(RUST_TOOLCHAIN) rustc)" \
	uv run --no-project --with "maturin>=1.11.5" maturin sdist --out $(DIST_DIR)
	uv run python scripts/package_smoke.py $(DIST_DIR)
	PYAGENTBROWSER_PYTHON_VERSIONS="$(PYTHON_VERSIONS)" uv run python scripts/verify-install-artifacts.py $(DIST_DIR)

.PHONY: prepare-prerelease
prepare-prerelease: ## Sync release metadata from the upstream base tag
	uv run python scripts/prepare_prerelease.py

.PHONY: prerelease-version-check
prerelease-version-check: ## Verify release metadata matches the pinned upstream commit
	uv run python scripts/prepare_prerelease.py --check

##@ Docs/examples

.PHONY: docs
docs: ## Check docs and examples for stale public API claims
	uv run python scripts/check_docs.py

.PHONY: examples
examples: ## Compile maintained examples against the public API
	uv run python -m compileall -q examples

##@ Gates

.PHONY: check
check: lint typecheck test rust-check ## Run the normal handoff gate

.PHONY: check-release
check-release: prerelease-version-check check test-integration test-python-matrix rust-test package ## Run the full release gate
