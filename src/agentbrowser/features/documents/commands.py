from __future__ import annotations

import json
import math
from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.contracts.errors import NativeParseError
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor, result_scope
from agentbrowser.features.documents.models import ElementGeometry, ScrollResult
from agentbrowser.features.documents.shared import scroll_position


def geometry(executor: Executor | AsyncExecutor, selector: str | None) -> Command[ElementGeometry]:
    if selector == "":
        raise ValueError("geometry selector must not be empty")
    selector_json = json.dumps(selector)
    script = f"""(() => {{
        const element = {selector_json} === null
            ? document.documentElement
            : document.querySelector({selector_json});
        if (!element) throw new Error('geometry target not found');
        const rect = element.getBoundingClientRect();
        return {{
            x: rect.x, y: rect.y, width: rect.width, height: rect.height,
            clientWidth: element.clientWidth, clientHeight: element.clientHeight,
            scrollWidth: element.scrollWidth, scrollHeight: element.scrollHeight,
        }};
    }})()"""

    def decode(data: Mapping[str, object]) -> ElementGeometry:
        result = data.get("result")
        if not isinstance(result, Mapping):
            raise NativeParseError("geometry evaluation must return an object")
        result = cast(Mapping[str, Any], result)
        fields = (
            "x",
            "y",
            "width",
            "height",
            "clientWidth",
            "clientHeight",
            "scrollWidth",
            "scrollHeight",
        )
        if any(
            isinstance(result.get(field), bool) or not isinstance(result.get(field), int | float)
            for field in fields
        ):
            raise NativeParseError("geometry fields must be numbers")
        return ElementGeometry(
            result_scope(executor, data),
            selector or "document",
            *(float(result[field]) for field in fields),
        )

    return Command("evaluate", {"script": script}, decode=decode)


def scroll(
    executor: Executor | AsyncExecutor, *, x: float, y: float, selector: str | None
) -> Command[ScrollResult]:
    if selector == "":
        raise ValueError("scroll selector must not be empty")
    if any(
        isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value)
        for value in (x, y)
    ):
        raise ValueError("scroll offsets must be finite numbers")
    selector_json = json.dumps(selector)
    script = f"""(() => {{
        const element = {selector_json} === null
            ? document.scrollingElement
            : document.querySelector({selector_json});
        if (!element) throw new Error('scroll container not found');
        const before = {{x: element.scrollLeft, y: element.scrollTop}};
        element.scrollLeft += {x!r};
        element.scrollTop += {y!r};
        return {{before, after: {{x: element.scrollLeft, y: element.scrollTop}}}};
    }})()"""

    def decode(data: Mapping[str, object]) -> ScrollResult:
        result = data.get("result")
        if not isinstance(result, Mapping):
            raise NativeParseError("scroll evaluation must return an object")
        result = cast(Mapping[str, Any], result)
        return ScrollResult(
            result_scope(executor, data),
            selector or "document",
            scroll_position(result.get("before")),
            scroll_position(result.get("after")),
        )

    return Command("evaluate", {"script": script}, decode=decode)
