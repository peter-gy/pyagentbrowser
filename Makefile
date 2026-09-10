.DEFAULT_GOAL := check

PYTHON_SOURCES = src tests scripts examples
BUILD_PYTHON ?= 3.11
RUST_TOOLCHAIN ?= 1.97.0
UPSTREAM_REF ?= origin/main
ALLOW_NON_FAST_FORWARD ?= 0
UPSTREAM_UPDATE_FLAGS = $(if $(filter 1,$(ALLOW_NON_FAST_FORWARD)),--allow-non-fast-forward)
RUST_ENV = cargo_path="$$(rustup which --toolchain $(RUST_TOOLCHAIN) cargo)" && rust_bin="$$(dirname "$$cargo_path")" && PATH="$$rust_bin:$$PATH"
RUST_CARGO = $(RUST_ENV) cargo
UV_RUN = uv run --no-sync
PYTHON_RUN = uv run --no-project --python $(BUILD_PYTHON) python
DIST_DIR = target/wheels
EDITABLE_DIST_DIR = target/editable-wheels
MATURIN_DIST_DIR = target/maturin-dist
PEP517_DIST_DIR = target/pep517-dist
SOURCE_DATE_EPOCH ?= $(shell git log -1 --format=%ct 2>/dev/null || printf '315532800')
CARGO_HOME ?= $(HOME)/.cargo
REPRODUCIBLE_RUSTFLAGS = --remap-path-prefix=$(CURDIR)=/src/pyagentbrowser --remap-path-prefix=$(CARGO_HOME)=/cargo

.PHONY: help
help:
	@printf '%s\n' \
		'make install           Bootstrap dependencies and build the native extension' \
		'make update-upstream   Pin upstream origin/main and synchronize metadata' \
		'make check-upstream    Audit an available upstream ref in isolation' \
		'make test-sdk          Run Python SDK contract tests' \
		'make test-native       Run PyO3 and generated-adapter boundary tests' \
		'make test-package      Run wheel, sdist, version, and provenance contracts' \
		'make test-integration  Run curated real-Chrome seams' \
		'make docs-install      Install the VitePress documentation dependencies' \
		'make docs-dev          Serve docs at a stable Portless URL' \
		'make docs-check        Type-check, build, and verify the documentation site' \
		'make check             Run the normal handoff gate' \
		'make package           Build and clean-install the wheel and sdist' \
		'make release-version-check  Verify release and upstream version identities' \
		'make check-release     Run the full release gate'

.PHONY: submodule-init
submodule-init:
	@status="$$(git submodule status third_party/agent-browser)"; \
	case "$$status" in -*) git submodule update --init --recursive third_party/agent-browser ;; esac

.PHONY: sync
sync:
	uv sync --locked --no-install-project --inexact --extra cdp

.PHONY: native-dev
native-dev: submodule-init sync
	$(RUST_ENV) MATURIN_PEP517_ARGS='--locked --out $(EDITABLE_DIST_DIR)' uv pip install \
		--python .venv --no-build-isolation --editable .

.PHONY: install
install: native-dev

.PHONY: update-upstream
update-upstream:
	uv run --no-project --with "tomlkit>=0.13.3" python scripts/update_upstream.py --ref "$(UPSTREAM_REF)" $(UPSTREAM_UPDATE_FLAGS)

.PHONY: check-upstream
check-upstream:
	$(UV_RUN) python -m scripts.check_upstream --ref "$(UPSTREAM_REF)" $(UPSTREAM_CHECK_FLAGS)

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
	$(UV_RUN) ty check --python-platform all

.PHONY: test
test: native-dev
	$(UV_RUN) pytest -q -m "not integration"

.PHONY: test-sdk
test-sdk: native-dev
	$(UV_RUN) pytest -q -m sdk_dx

.PHONY: test-native
test-native: native-dev
	$(UV_RUN) pytest -q -m native_smoke

.PHONY: test-package
test-package: submodule-init sync
	$(UV_RUN) pytest -q tests/packaging

.PHONY: test-integration
test-integration: native-dev
	chrome_path="$$($(UV_RUN) python scripts/check_chrome.py)" && \
	PYAGENTBROWSER_CHROME="$$chrome_path" \
	PYAGENTBROWSER_FAIL_ON_SKIP=1 \
	$(UV_RUN) pytest -q -m integration

.PHONY: docs-install
docs-install:
	pnpm --dir docs install --frozen-lockfile

.PHONY: docs-dev
docs-dev:
	pnpm --dir docs dev

.PHONY: docs-check
docs-check:
	$(UV_RUN) python scripts/check_development_docs.py
	pnpm --dir docs check

.PHONY: rust-check
rust-check: submodule-init
	test ! -e crates/agent-browser-adapter/Cargo.lock
	$(RUST_CARGO) fmt --all --manifest-path Cargo.toml --check
	$(RUST_CARGO) clippy -p pyagentbrowser -p agent-browser --lib --all-features --locked -- -D warnings
	$(RUST_CARGO) clippy -p agent-browser --test smoke --all-features --locked -- -D warnings
	$(RUST_CARGO) clippy -p agent-browser-build --all-targets --locked -- -D warnings

.PHONY: rust-test
rust-test: submodule-init
	$(RUST_CARGO) test -p pyagentbrowser --lib --locked
	$(RUST_CARGO) test -p agent-browser --test smoke --locked
	$(RUST_CARGO) test -p agent-browser-build --locked

.PHONY: package
package: export RUSTFLAGS := $(strip $(RUSTFLAGS) $(REPRODUCIBLE_RUSTFLAGS))
package: export SOURCE_DATE_EPOCH := $(SOURCE_DATE_EPOCH)
package: export UV_PROJECT_ENVIRONMENT := .venvbuild$(subst .,,$(BUILD_PYTHON))
package: submodule-init
	rm -rf $(DIST_DIR) $(MATURIN_DIST_DIR) $(PEP517_DIST_DIR)
	mkdir -p $(DIST_DIR) $(MATURIN_DIST_DIR) $(PEP517_DIST_DIR)
	$(RUST_ENV) uv build --wheel --force-pep517 --python $(BUILD_PYTHON) \
		--config-setting 'maturin.build-args=--profile release --locked --compatibility pypi --out $(MATURIN_DIST_DIR)' \
		--out-dir $(PEP517_DIST_DIR)
	uv build --sdist --force-pep517 --python $(BUILD_PYTHON) --out-dir $(PEP517_DIST_DIR)
	mv $(PEP517_DIST_DIR)/* $(DIST_DIR)/
	$(PYTHON_RUN) -m scripts.package_smoke $(DIST_DIR)
	$(PYTHON_RUN) scripts/verify-install-artifacts.py $(DIST_DIR)

.PHONY: release-version-check
release-version-check: submodule-init
	$(PYTHON_RUN) -m scripts.check_release
	$(PYTHON_RUN) scripts/update_upstream.py --check

.PHONY: check
check: lint typecheck test rust-check rust-test

.PHONY: check-release
check-release: release-version-check check test-integration package
