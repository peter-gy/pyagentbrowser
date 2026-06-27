from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from pyagentbrowser.models import SessionId, SessionIdScope


def generate_session_id(
    *,
    scope: SessionIdScope = "worktree",
    prefix: str | None = None,
    path: str | Path | None = None,
) -> SessionId:
    """Return a stable session id for the requested filesystem scope."""
    resolved_scope, resolved_path = _resolve_scope(scope, path)
    path_text = str(resolved_path)
    suffix = hashlib.sha256(path_text.encode()).hexdigest()[:12]
    normalized_prefix = _sanitize_session_component(prefix) if prefix is not None else ""
    session = f"{normalized_prefix}-{suffix}" if normalized_prefix else suffix
    return SessionId(session=session, scope=resolved_scope, path=path_text, hash=suffix)


def _resolve_scope(scope: SessionIdScope, path: str | Path | None) -> tuple[SessionIdScope, Path]:
    base = _canonical_path(Path.cwd() if path is None else Path(path))
    if scope == "worktree":
        return "worktree", _git_toplevel(base) or base
    if scope == "cwd":
        return "cwd", base
    if scope == "git-root":
        root = _git_toplevel(base)
        if root is None:
            raise ValueError("Not inside a Git working tree")
        return "git-root", root
    raise ValueError("scope must be 'worktree', 'cwd', or 'git-root'")


def _git_toplevel(path: Path) -> Path | None:
    try:
        output = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if output.returncode != 0:
        return None
    value = output.stdout.strip()
    return _canonical_path(Path(value)) if value else None


def _canonical_path(path: Path) -> Path:
    return path.resolve(strict=False)


def _sanitize_session_component(value: str | None) -> str:
    if value is None:
        return ""
    out: list[str] = []
    last_was_sep = False
    for char in value:
        if char.isalnum():
            out.append(char.lower())
            last_was_sep = False
        elif char in {"-", "_"}:
            if out and not last_was_sep:
                out.append(char)
                last_was_sep = True
        elif out and not last_was_sep:
            out.append("-")
            last_was_sep = True
    return "".join(out).rstrip("-_")
