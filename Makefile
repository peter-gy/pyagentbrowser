.DEFAULT_GOAL := check

PYTHON_SOURCES = src tests scripts examples
BUILD_PYTHON ?= 3.11
RUST_TOOLCHAIN ?= stable
RUST_CARGO = rustup run $(RUST_TOOLCHAIN) cargo
DIST_DIR = target/wheels

.PHONY: install
install:
	git submodule update --init --recursive
	uv sync
	uv run maturin develop

.PHONY: clean
clean:
	rm -rf target crates/agent-browser-adapter/target build dist wheels *.egg-info
	rm -rf .pytest_cache .ruff_cache .venv .venv[0-9]* .venvbuild[0-9]*
	rm -f src/agentbrowser/_native*.so src/agentbrowser/_native*.pyd src/agentbrowser/_native*.dylib
	find $(PYTHON_SOURCES) -type d -name __pycache__ -prune -exec rm -rf {} +
	find $(PYTHON_SOURCES) -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

.PHONY: format
format:
	uv run ruff format $(PYTHON_SOURCES) pyproject.toml
	uv run ruff check --fix $(PYTHON_SOURCES)
	$(RUST_CARGO) fmt --manifest-path Cargo.toml

.PHONY: lint
lint:
	uv lock --check
	uv run ruff format --check $(PYTHON_SOURCES) pyproject.toml
	uv run ruff check
	uv run python -m compileall -q examples

.PHONY: typecheck
typecheck:
	uv run --extra cdp ty check

.PHONY: test
test:
	uv run pytest -q -m "not integration"

.PHONY: test-integration
test-integration:
	chrome_path="$$(uv run python scripts/check_chrome.py)" && \
	PYAGENTBROWSER_CHROME="$$chrome_path" \
	PYAGENTBROWSER_FAIL_ON_SKIP=1 \
	uv run --extra cdp pytest -q -m integration

.PHONY: rust-check
rust-check:
	$(RUST_CARGO) fmt --manifest-path Cargo.toml -- --check
	$(RUST_CARGO) clippy -p pyagentbrowser --all-features --lib --no-deps -- -D warnings
	$(RUST_CARGO) clippy --manifest-path crates/agent-browser-adapter/Cargo.toml --all-targets --all-features -- -D warnings
	$(RUST_CARGO) check

.PHONY: rust-test
rust-test:
	$(RUST_CARGO) test
	$(RUST_CARGO) test --manifest-path crates/agent-browser-adapter/Cargo.toml --test smoke

.PHONY: package
package:
	rm -rf $(DIST_DIR)
	mkdir -p $(DIST_DIR)
	CARGO="$$(rustup which --toolchain $(RUST_TOOLCHAIN) cargo)" \
	RUSTC="$$(rustup which --toolchain $(RUST_TOOLCHAIN) rustc)" \
	UV_PROJECT_ENVIRONMENT=.venvbuild$$(printf '%s' "$(BUILD_PYTHON)" | tr -d '.') \
	uv run --no-project --python $(BUILD_PYTHON) --with "maturin>=1.11.5" maturin build --release --locked --compatibility pypi --sdist --out $(DIST_DIR)
	uv run python scripts/package_smoke.py $(DIST_DIR)
	uv run python scripts/verify-install-artifacts.py $(DIST_DIR)

.PHONY: prerelease-version-check
prerelease-version-check:
	uv run python scripts/prepare_prerelease.py --check

.PHONY: check
check: lint typecheck test rust-check

.PHONY: check-release
check-release: prerelease-version-check check test-integration rust-test package
