from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from agentbrowser.cdp.errors import (
    CDPContextAmbiguityError,
    CDPContextNotFoundError,
    CDPFrameAmbiguityError,
    CDPFrameNotFoundError,
    CDPProtocolError,
    CDPTargetAmbiguityError,
    CDPTargetNotFoundError,
)
from agentbrowser.cdp.models import AsyncExecutionContext, AsyncFrame, ExecutionContext, Frame


def _resolve_active_target(
    targets_response: Mapping[str, Any],
    current_url: str,
    *,
    label: str | None = None,
    url: str | None = None,
    target_id: str | None = None,
) -> Mapping[str, Any]:
    raw_targets = targets_response.get("targetInfos")
    if not isinstance(raw_targets, list):
        raise CDPTargetNotFoundError("Target.getTargets did not return targetInfos")
    page_targets = [
        cast(Mapping[str, Any], target)
        for target in raw_targets
        if isinstance(target, Mapping) and target.get("type") == "page"
    ]
    if target_id is not None:
        matches = [target for target in page_targets if target.get("targetId") == target_id]
        return _single_target(matches, f"target_id={target_id!r}")
    if url is not None:
        matches = [target for target in page_targets if target.get("url") == url]
        return _single_target(matches, f"url={url!r}")
    if label is not None:
        matches = [target for target in page_targets if target.get("label") == label]
        return _single_target(matches, f"label={label!r}")
    exact = [target for target in page_targets if target.get("url") == current_url]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise CDPTargetAmbiguityError(
            f"multiple CDP page targets matched current URL {current_url!r}. "
            "Pass label=..., url=..., or target_id=... to browser.cdp.target(...) "
            "to select one target."
        )
    if len(page_targets) == 1:
        return page_targets[0]
    urls = ", ".join(str(target.get("url", "")) for target in page_targets)
    raise CDPTargetNotFoundError(
        f"could not resolve active CDP page target for current URL {current_url!r}. "
        f"available page target URLs: {urls or '<none>'}"
    )


def _single_target(targets: list[Mapping[str, Any]], criteria: str) -> Mapping[str, Any]:
    if not targets:
        raise CDPTargetNotFoundError(f"no CDP page target matched {criteria}")
    if len(targets) > 1:
        raise CDPTargetAmbiguityError(f"multiple CDP page targets matched {criteria}")
    return targets[0]


def _sync_context_from_event(
    params: Mapping[str, Any],
    owner: Any,
    session_id: str,
    generation: int,
) -> ExecutionContext | None:
    raw_context = params.get("context")
    if not isinstance(raw_context, Mapping):
        return None
    parsed = _parse_context(raw_context)
    return ExecutionContext(*parsed, _owner=owner, _session_id=session_id, _generation=generation)


def _async_context_from_event(
    params: Mapping[str, Any],
    owner: Any,
    session_id: str,
    generation: int,
) -> AsyncExecutionContext | None:
    raw_context = params.get("context")
    if not isinstance(raw_context, Mapping):
        return None
    parsed = _parse_context(raw_context)
    return AsyncExecutionContext(
        *parsed,
        _owner=owner,
        _session_id=session_id,
        _generation=generation,
    )


def _parse_context(
    raw_context: Mapping[str, Any],
) -> tuple[int, str | None, str | None, str, str, str, bool]:
    context_id = raw_context.get("id")
    if not isinstance(context_id, int):
        raise CDPProtocolError("Runtime.executionContextCreated", "context id was not an int")
    aux_data = raw_context.get("auxData")
    aux = cast(Mapping[str, Any], aux_data) if isinstance(aux_data, Mapping) else {}
    unique_id = raw_context.get("uniqueId")
    frame_id = aux.get("frameId")
    context_type = str(aux.get("type") or ("default" if aux.get("isDefault") else "isolated"))
    is_default = bool(aux.get("isDefault")) or context_type == "default"
    return (
        context_id,
        str(unique_id) if unique_id is not None else None,
        str(frame_id) if frame_id is not None else None,
        str(raw_context.get("origin", "")),
        str(raw_context.get("name", "")),
        context_type,
        is_default,
    )


def _single_frame(
    frames: list[Frame] | list[AsyncFrame],
    *,
    name: str | None,
    url: str | None,
) -> Frame | AsyncFrame:
    if not frames:
        criteria = _frame_criteria(name=name, url=url)
        raise CDPFrameNotFoundError(f"no CDP frame matched {criteria}")
    if len(frames) > 1:
        criteria = _frame_criteria(name=name, url=url)
        raise CDPFrameAmbiguityError(f"multiple CDP frames matched {criteria}")
    return frames[0]


def _frame_criteria(*, name: str | None, url: str | None) -> str:
    criteria = []
    if name is not None:
        criteria.append(f"name={name!r}")
    if url is not None:
        criteria.append(f"url={url!r}")
    return ", ".join(criteria) or "the main frame"


def _single_context(
    contexts: list[ExecutionContext] | list[AsyncExecutionContext],
    *,
    frame_id: str,
    extension_id: str | None,
) -> ExecutionContext | AsyncExecutionContext:
    if not contexts:
        if extension_id is None:
            raise CDPContextNotFoundError(
                f"no default execution context found for frame {frame_id}"
            )
        raise CDPContextNotFoundError(
            f"no execution context for extension {extension_id!r} found in frame {frame_id}"
        )
    if len(contexts) > 1:
        if extension_id is None:
            raise CDPContextAmbiguityError(
                f"multiple execution contexts found for frame {frame_id}"
            )
        raise CDPContextAmbiguityError(
            f"multiple execution contexts for extension {extension_id!r} found in frame {frame_id}"
        )
    return contexts[0]


def _context_matches_extension(
    context: ExecutionContext | AsyncExecutionContext,
    extension_id: str,
) -> bool:
    normalized = extension_id.lower()
    extension_origin = f"chrome-extension://{normalized}"
    haystacks = (context.origin.lower(), context.name.lower())
    return any(
        value == extension_origin or value.startswith(extension_origin + "/") or normalized in value
        for value in haystacks
    )


def _extract_frame_id(node: object) -> str | None:
    if not isinstance(node, Mapping):
        return None
    node = cast(Mapping[str, Any], node)
    frame_id = node.get("frameId")
    if frame_id is not None:
        return str(frame_id)
    content_document = node.get("contentDocument")
    if isinstance(content_document, Mapping):
        nested_frame_id = content_document.get("frameId")
        if nested_frame_id is not None:
            return str(nested_frame_id)
    return None
