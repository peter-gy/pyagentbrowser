#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

usage() {
  cat <<'EOF'
Usage: ./scripts/release.sh check-version <release-tag>

Checks that a GitHub release tag matches the pyagentbrowser package version.
Tags may include a leading "v".
EOF
}

python_package_version() {
  python - <<'PY'
import tomllib
from pathlib import Path

with Path("pyproject.toml").open("rb") as stream:
    print(tomllib.load(stream)["project"]["version"])
PY
}

runtime_package_version() {
  python - <<'PY'
import re
from pathlib import Path

text = Path("src/agentbrowser/_version.py").read_text(encoding="utf-8")
match = re.search(r'^PACKAGE_VERSION = "([^"]+)"$', text, re.MULTILINE)
if not match:
    raise SystemExit("src/agentbrowser/_version.py does not declare PACKAGE_VERSION")
print(match.group(1))
PY
}

check_version() {
  local release_tag="${1:-}"
  if [[ -z "$release_tag" ]]; then
    usage
    exit 1
  fi

  local python_version
  python_version="$(python_package_version)"
  local runtime_version
  runtime_version="$(runtime_package_version)"
  local actual="${release_tag#refs/tags/}"
  actual="${actual#v}"

  if [[ ! "$actual" =~ ^[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?$ ]]; then
    printf 'Release tag %s must look like v1.2.3, v1.2.3a1, or v1.2.3rc1\n' "$release_tag" >&2
    exit 1
  fi

  if [[ "$python_version" != "$runtime_version" ]]; then
    printf 'pyproject version %s does not match runtime version %s\n' "$python_version" "$runtime_version" >&2
    exit 1
  fi

  if [[ "$actual" != "$python_version" ]]; then
    printf 'Package version %s does not match release tag %s\n' "$python_version" "$release_tag" >&2
    exit 1
  fi

  printf 'Verified pyagentbrowser %s for release tag %s\n' "$python_version" "$release_tag"
}

case "${1:-}" in
  check-version)
    shift
    check_version "$@"
    ;;
  -h | --help)
    usage
    ;;
  *)
    usage
    exit 1
    ;;
esac
