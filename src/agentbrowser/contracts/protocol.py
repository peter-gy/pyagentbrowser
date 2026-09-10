from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from agentbrowser.contracts.types import JSONMapping, JSONValue


class _OmitType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "OMIT"


OMIT = _OmitType()


@dataclass(frozen=True, slots=True)
class BrowserResponse:
    """Native response envelope returned by `browser.native.execute()`.

    Attributes
    ----------
    id
        Native command id.
    action
        Native action name.
    success
        Whether the native command succeeded.
    data
        Raw response data.
    raw
        Complete native response mapping.
    warning
        Optional native warning message.
    """

    id: str
    action: str
    success: bool
    data: JSONValue
    raw: JSONMapping
    warning: str | None = None


def path_value(value: str | Path | None) -> str | None:
    return str(value) if value is not None else None


def paths_value(values: SequencePath) -> list[str]:
    return [str(value) for value in values]


SequencePath = Sequence[str | Path]


def optional(value: Any) -> Any:
    return OMIT if value is None else value


def response_data_mapping(response: BrowserResponse) -> Mapping[str, Any] | None:
    if isinstance(response.data, Mapping):
        return cast(Mapping[str, Any], response.data)
    return None
