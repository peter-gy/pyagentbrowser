.DEFAULT_GOAL := check

PYTHON_SOURCES = src tests scripts examples
BUILD_PYTHON ?= 3.11
RUST_TOOLCHAIN ?= 1.97.0
RUST_CARGO = rustup run $(RUST_TOOLCHAIN) cargo
RUST_ENV = cargo_path="$$(rustup which --toolchain $(RUST_TOOLCHAIN) cargo)" && rust_bin="$$(dirname "$$cargo_path")" && PATH="$$rust_bin:$$PATH"
UV_RUN = uv run --no-sync
PYTHON_RUN = uv run --no-project --python $(BUILD_PYTHON) python
DIST_DIR = target/wheels
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct 2>/dev/null || printf '315532800')
CARGO_HOME ?= $(HOME)/.cargo
REPRODUCIBLE_RUSTFLAGS = --remap-path-prefix=$(CURDIR)=/src/pyagentbrowser --remap-path-prefix=$(CARGO_HOME)=/cargo

.PHONY: submodule-init
submodule-init:
	@status="$$(git submodule status third_party/agent-browser)"; \
	case "$$status" in -*) git submodule update --init --recursive third_party/agent-browser ;; esac

.PHONY: sync
sync:
	uv sync --locked --no-install-project --inexact --extra cdp

.PHONY: native-dev
native-dev: submodule-init sync
	$(RUST_ENV) $(UV_RUN) maturin develop --locked

.PHONY: install
install: native-dev

.PHONY: clean
clean:
	rm -rf target crates/agent-browser-adapter/target build dist wheels *.egg-info
	rm -rf .pytest_cache .ruff_cache .venv .venv[0-9]* .venvbuild[0-9]*
	rm -f src/agentbrowser/_native*.so src/agentbrowser/_native*.pyd src/agentbrowser/_native*.dylib
	find $(PYTHON_SOURCES) -type d -name __pycache__ -prune -exec rm -rf {} +
	find $(PYTHON_SOURCES) -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

.PHONY: format
format: sync
	$(UV_RUN) ruff format $(PYTHON_SOURCES) pyproject.toml
	$(UV_RUN) ruff check --fix $(PYTHON_SOURCES)
	$(RUST_CARGO) fmt --all --manifest-path Cargo.toml

.PHONY: lint
lint: sync
	uv lock --check
	$(UV_RUN) ruff format --check $(PYTHON_SOURCES) pyproject.toml
	$(UV_RUN) ruff check
	$(UV_RUN) python -m compileall -q examples

.PHONY: typecheck
typecheck: sync
	$(UV_RUN) ty check

.PHONY: test
test: native-dev
	$(UV_RUN) pytest -q -m "not integration"

.PHONY: test-integration
test-integration: native-dev
	chrome_path="$$($(UV_RUN) python scripts/check_chrome.py)" && \
	PYAGENTBROWSER_CHROME="$$chrome_path" \
	PYAGENTBROWSER_FAIL_ON_SKIP=1 \
	$(UV_RUN) pytest -q -m integration

.PHONY: rust-check
rust-check:
	test ! -e crates/agent-browser-adapter/Cargo.lock
	$(RUST_CARGO) fmt --all --manifest-path Cargo.toml --check
	$(RUST_CARGO) clippy -p pyagentbrowser --all-features --lib --no-deps --locked -- -D warnings
	$(RUST_CARGO) clippy -p agent-browser --lib --all-features --locked -- -D warnings
	$(RUST_CARGO) clippy -p agent-browser --test smoke --all-features --locked -- -D warnings
	$(RUST_CARGO) check --workspace --locked

.PHONY: rust-test
rust-test:
	$(RUST_CARGO) test -p pyagentbrowser --lib --locked
	$(RUST_CARGO) test -p agent-browser --test smoke --locked

.PHONY: package
package: export RUSTFLAGS := $(strip $(RUSTFLAGS) $(REPRODUCIBLE_RUSTFLAGS))
package: export SOURCE_DATE_EPOCH := $(SOURCE_DATE_EPOCH)
package: export UV_PROJECT_ENVIRONMENT := .venvbuild$(subst .,,$(BUILD_PYTHON))
package:
	rm -rf $(DIST_DIR)
	mkdir -p $(DIST_DIR)
	$(RUST_ENV) uv run --no-project --python $(BUILD_PYTHON) --with "maturin>=1.11.5" maturin build --release --locked --compatibility pypi --out $(DIST_DIR)
	uv run --no-project --python $(BUILD_PYTHON) --with "maturin>=1.11.5" maturin sdist --out $(DIST_DIR)
	$(PYTHON_RUN) scripts/package_smoke.py $(DIST_DIR)
	$(PYTHON_RUN) scripts/verify-install-artifacts.py $(DIST_DIR)

.PHONY: prerelease-version-check
prerelease-version-check:
	$(PYTHON_RUN) scripts/prepare_prerelease.py --check
	$(PYTHON_RUN) scripts/update_upstream.py --check

.PHONY: check
check: lint typecheck test rust-check

.PHONY: check-release
check-release: prerelease-version-check check test-integration rust-test package
