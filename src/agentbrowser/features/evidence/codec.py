from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.features.evidence.changes import SnapshotDiff
from agentbrowser.features.evidence.models import SnapshotData, SnapshotSpec

# The engine prints a tree line as
#   - role "json name" [level=1, ref=e7, url=/x] hint="rust debug string": value
# The name is a JSON string and the attributes before `ref` are engine values.
# The URL and everything after the attribute block are page text.
_REF_LINE = re.compile(
    r"""
    \s* -[ ] \S+                                  # role
    (?: [ ] " (?: [^"\\] | \\. )* " )?             # name
    [ ] \[ (?: [a-z]+ (?: = [A-Za-z0-9]+ )? ,[ ] )*  # attributes before the ref
    ref= (?P<ref> [A-Za-z0-9_-]+ )
    (?P<url> ,[ ] url= )?
    """,
    re.VERBOSE,
)
_BLOCK_END_HINT = re.compile(r'\] hint="(?P<hint>(?:[^"\\]|\\.)*)"')
_DEBUG_ESCAPE = re.compile(r"\\(?:u\{(?P<code>[0-9a-fA-F]{1,6})\}|(?P<char>.))")
_DEBUG_CHARS = {"n": "\n", "r": "\r", "t": "\t", "0": "\0"}


def _debug_unescape(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        code = match.group("code")
        if code is not None:
            point = int(code, 16)
            return chr(point) if point <= 0x10FFFF else match.group(0)
        char = match.group("char")
        return _DEBUG_CHARS.get(char, char)

    return _DEBUG_ESCAPE.sub(replace, text)


def _line_hint(line: str) -> tuple[str, str] | None:
    """Return the ref and hint one tree line prints for its own node."""
    node = _REF_LINE.match(line)
    if node is None:
        return None
    if node.group("url") is None:
        hint = _BLOCK_END_HINT.match(line, node.end())
    else:
        # A URL is unescaped page text and can contain `] hint="..."` itself,
        # so the line carries a hint only when exactly one candidate follows.
        candidates = list(_BLOCK_END_HINT.finditer(line, node.end()))
        hint = candidates[0] if len(candidates) == 1 else None
    if hint is None:
        return None
    return node.group("ref"), _debug_unescape(hint.group("hint"))


def _hints(text: str, refs: Mapping[str, Any]) -> dict[str, str]:
    hints: dict[str, str] = {}
    for line in text.split("\n"):
        found = _line_hint(line)
        if found is not None and found[0] in refs:
            hints[found[0]] = found[1]
    return hints


def snapshot_from_data(
    data: Mapping[str, Any],
    *,
    spec: SnapshotSpec | None = None,
) -> SnapshotData:
    text = data.get("snapshot")
    origin = data.get("origin")
    raw_refs = data.get("refs")
    if not isinstance(text, str):
        raise NativeParseError("Snapshot field 'snapshot' must be a string")
    if not isinstance(origin, str):
        raise NativeParseError("Snapshot field 'origin' must be a string")
    if not isinstance(raw_refs, Mapping):
        raise NativeParseError("Snapshot field 'refs' must be an object")
    refs: dict[str, dict[str, Any]] = {}
    for key, value in raw_refs.items():
        if not isinstance(value, Mapping):
            raise NativeParseError("Snapshot ref metadata must be objects")
        if not isinstance(value.get("role"), str) or not isinstance(value.get("name"), str):
            raise NativeParseError("Snapshot refs require string 'role' and 'name' fields")
        refs[str(key)] = {str(ref_key): ref_value for ref_key, ref_value in value.items()}
    return SnapshotData(
        text=text,
        origin=origin,
        refs=refs,
        raw=data,
        spec=spec or SnapshotSpec(),
        hints=_hints(text, refs),
    )


def snapshot_diff_from_data(data: Mapping[str, Any]) -> SnapshotDiff:
    text = data.get("diff")
    additions = data.get("additions")
    removals = data.get("removals")
    unchanged = data.get("unchanged")
    changed = data.get("changed")
    if not isinstance(text, str):
        raise NativeParseError("diff_snapshot field 'diff' must be a string")
    if any(
        not isinstance(value, int) or isinstance(value, bool)
        for value in (additions, removals, unchanged)
    ):
        raise NativeParseError("diff_snapshot counts must be integers")
    if not isinstance(changed, bool):
        raise NativeParseError("diff_snapshot field 'changed' must be a boolean")
    return SnapshotDiff(
        text=text,
        additions=cast(int, additions),
        removals=cast(int, removals),
        unchanged=cast(int, unchanged),
        changed=changed,
        raw=data,
    )
