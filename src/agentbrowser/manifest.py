"""Serializable evidence records for agent completion reports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, cast

from agentbrowser.host import ImageDelivery


@dataclass(frozen=True, slots=True)
class EvidenceAssertion:
    """One named behavioral assertion and its outcome."""

    name: str
    passed: bool
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One captured value with delivery, assessment, and assertions."""

    name: str
    value: object = field(repr=False)
    delivery: ImageDelivery | None = None
    assessment: str | None = None
    assertions: tuple[EvidenceAssertion, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible evidence record."""
        return {
            "name": self.name,
            "kind": type(self.value).__name__,
            "captured": _captured(self.value),
            "value": _json_value(self.value),
            "delivery": _json_value(self.delivery),
            "assessment": self.assessment,
            "assertions": [_json_value(assertion) for assertion in self.assertions],
        }


@dataclass(slots=True)
class EvidenceManifest:
    """Ordered evidence records for one agent task."""

    records: list[EvidenceRecord] = field(default_factory=list)

    def record(
        self,
        name: str,
        value: object,
        *,
        delivery: ImageDelivery | None = None,
        assessment: str | None = None,
        assertions: tuple[EvidenceAssertion, ...] = (),
    ) -> EvidenceRecord:
        """Append one evidence record and return it."""
        if not name:
            raise ValueError("evidence name must not be empty")
        record = EvidenceRecord(name, value, delivery, assessment, assertions)
        self.records.append(record)
        return record

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible manifest."""
        return {"records": [record.to_dict() for record in self.records]}


def _captured(value: object) -> bool:
    path = getattr(value, "path", None)
    return path.is_file() if isinstance(path, Path) else True


def _json_value(value: object) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _json_value(asdict(cast(Any, value)))
    if hasattr(value, "origin") and hasattr(value, "text"):
        evidence = cast(Any, value)
        return {"origin": str(evidence.origin), "text": str(evidence.text)}
    return repr(value)
