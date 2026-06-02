#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: scripts/update-upstream.sh <agent-browser-commit-or-tag>" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
upstream="$repo_root/third_party/agent-browser"
target_ref="$1"

git -C "$upstream" fetch --tags origin
git -C "$upstream" checkout "$target_ref"

cd "$repo_root"
uv run python scripts/prepare_prerelease.py
uv run pytest tests/test_upstream_contract.py tests/test_skills.py tests/test_native.py
make rust
make package

echo
echo "upstream pinned to $(git -C "$upstream" rev-parse HEAD)"
echo "changed files:"
git status --short -- .gitmodules third_party/agent-browser crates/agent-browser-adapter crates/pyagentbrowser scripts
