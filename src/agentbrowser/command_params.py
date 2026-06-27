from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agentbrowser.models import (
    OMIT,
    MouseButton,
    MouseEventType,
    ReadMode,
    RouteResponse,
    SameSite,
    StorageArea,
    WaitSelectorState,
    path_value,
    paths_value,
)


def optional(value: Any) -> Any:
    return OMIT if value is None else value


def screenshot_params(
    path: str | Path | None = None,
    *,
    selector: str | None = None,
    full_page: bool = False,
    annotate: bool = False,
    output_dir: str | Path | None = None,
    format: str = "png",
    quality: int | None = None,
) -> dict[str, Any]:
    return {
        "path": optional(path_value(path)),
        "selector": optional(selector),
        "fullPage": full_page,
        "annotate": annotate,
        "screenshotDir": optional(path_value(output_dir)),
        "format": format,
        "quality": optional(quality),
    }


def pdf_params(
    path: str | Path | None = None,
    *,
    print_background: bool = True,
    landscape: bool = False,
    prefer_css_page_size: bool = False,
) -> dict[str, Any]:
    return {
        "path": optional(path_value(path)),
        "printBackground": print_background,
        "landscape": landscape,
        "preferCSSPageSize": prefer_css_page_size,
    }


def click_params(
    selector: str,
    *,
    button: MouseButton = "left",
    click_count: int = 1,
    new_tab: bool = False,
) -> dict[str, Any]:
    return {
        "selector": selector,
        "button": button,
        "clickCount": click_count,
        "newTab": new_tab,
    }


def scroll_params(
    direction: str | None = None,
    amount: float | None = None,
    *,
    selector: str | None = None,
    x: float | None = None,
    y: float | None = None,
) -> dict[str, Any]:
    return {
        "direction": optional(direction),
        "amount": optional(amount),
        "selector": optional(selector),
        "x": optional(x),
        "y": optional(y),
    }


def dispatch_params(selector: str, event: str, init: Mapping[str, Any]) -> dict[str, Any]:
    return {"selector": selector, "event": event, "eventInit": dict(init) or OMIT}


def upload_params(selector: str, files: Sequence[str | Path]) -> dict[str, Any]:
    return {"selector": selector, "files": paths_value(files)}


def wait_params(
    milliseconds: int | None = None,
    *,
    selector: str | None = None,
    text: str | None = None,
    url: str | None = None,
    predicate: str | None = None,
    load_state: str | None = None,
    state: WaitSelectorState = "visible",
    timeout_ms: int | None = None,
) -> dict[str, Any]:
    return {
        "selector": optional(selector),
        "text": optional(text),
        "url": optional(url),
        "function": optional(predicate),
        "loadState": optional(load_state),
        "state": state,
        "timeout": optional(milliseconds if milliseconds is not None else timeout_ms),
    }


def read_params(
    url: str | None = None,
    *,
    mode: ReadMode | None = None,
    filter: str | None = None,
    timeout_ms: int | None = None,
    headers: Mapping[str, str] | None = None,
    allowed_domains: Sequence[str] | None = None,
) -> dict[str, Any]:
    mode = mode or ReadMode()
    if timeout_ms is not None and timeout_ms <= 0:
        raise ValueError("timeout_ms must be greater than 0")
    return {
        "url": optional(url),
        "raw": mode.raw,
        "requireMd": mode.require_markdown,
        "llms": optional(mode.llms),
        "outline": mode.outline,
        "filter": optional(filter),
        "timeout": optional(timeout_ms),
        "headers": dict(headers) if headers is not None else OMIT,
        "allowedDomains": list(allowed_domains) if allowed_domains is not None else OMIT,
    }


def viewport_params(
    width: int,
    height: int,
    *,
    device_scale_factor: float = 1.0,
    mobile: bool = False,
) -> dict[str, Any]:
    return {
        "width": width,
        "height": height,
        "deviceScaleFactor": device_scale_factor,
        "mobile": mobile,
    }


def media_params(
    *,
    media: str | None = None,
    color_scheme: str | None = None,
    reduced_motion: str | None = None,
    features: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "media": optional(media),
        "colorScheme": optional(color_scheme),
        "reducedMotion": optional(reduced_motion),
        "features": dict(features) if features is not None else OMIT,
    }


def geolocation_params(
    latitude: float,
    longitude: float,
    *,
    accuracy: float | None = None,
) -> dict[str, Any]:
    return {"latitude": latitude, "longitude": longitude, "accuracy": optional(accuracy)}


def permissions_params(permissions: Sequence[str], *, origin: str | None = None) -> dict[str, Any]:
    return {"permissions": list(permissions), "origin": optional(origin)}


def cookies_get_params(
    urls: Sequence[str] | None = None,
    *,
    unsafe_export_all: bool = False,
) -> dict[str, Any]:
    return {
        "urls": list(urls) if urls is not None else OMIT,
        "unsafeExportAll": unsafe_export_all,
    }


def cookies_clear_params(*, unsafe_clear_all: bool = False) -> dict[str, Any]:
    return {"unsafeClearAll": unsafe_clear_all}


def cookies_set_params(
    name: str | None = None,
    value: str | None = None,
    *,
    cookies: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    url: str | None = None,
    domain: str | None = None,
    path: str | None = None,
    expires: int | None = None,
    http_only: bool | None = None,
    secure: bool | None = None,
    same_site: SameSite | None = None,
) -> dict[str, Any]:
    if cookies is not None:
        payload = (
            [dict(cookies)] if isinstance(cookies, Mapping) else [dict(item) for item in cookies]
        )
        return {"cookies": payload}

    if name is None or value is None:
        raise ValueError("cookies.set requires either cookies=... or name and value")

    return {
        "name": name,
        "value": value,
        "url": optional(url),
        "domain": optional(domain),
        "path": optional(path),
        "expires": optional(expires),
        "httpOnly": optional(http_only),
        "secure": optional(secure),
        "sameSite": optional(same_site),
    }


def storage_get_params(key: str | None = None, *, area: StorageArea = "local") -> dict[str, Any]:
    return {"type": area, "key": optional(key)}


def storage_set_params(key: str, value: str, *, area: StorageArea = "local") -> dict[str, Any]:
    return {"type": area, "key": key, "value": value}


def storage_clear_params(*, area: StorageArea = "local") -> dict[str, Any]:
    return {"type": area}


def route_params(
    url: str,
    *,
    abort: bool = False,
    response: RouteResponse | Mapping[str, Any] | None = None,
    status: int | None = None,
    body: str | None = None,
    content_type: str | None = None,
    headers: Mapping[str, str] | None = None,
    resource_type: str | None = None,
    resource_types: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "url": url,
        "abort": abort,
        "response": optional(route_response(response, status, body, content_type, headers)),
        "resourceType": optional(resource_type),
        "resourceTypes": list(resource_types) if resource_types is not None else OMIT,
    }


def route_response(
    response: RouteResponse | Mapping[str, Any] | None,
    status: int | None,
    body: str | None,
    content_type: str | None,
    headers: Mapping[str, str] | None,
) -> Mapping[str, Any] | None:
    if isinstance(response, RouteResponse):
        return response.as_command_value()
    if response is not None:
        return dict(response)
    if status is None and body is None and content_type is None and headers is None:
        return None
    return RouteResponse(
        status=status,
        body=body,
        content_type=content_type,
        headers=headers,
    ).as_command_value()


def requests_params(
    *,
    clear: bool = False,
    url_pattern: str | None = None,
    resource_type: str | None = None,
    method: str | None = None,
    status: str | int | None = None,
) -> dict[str, Any]:
    return {
        "clear": clear,
        "filter": optional(url_pattern),
        "type": optional(resource_type),
        "method": optional(method),
        "status": str(status) if status is not None else OMIT,
    }


def state_path_params(path: str | Path | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "path": optional(path_value(path)),
        **{key: optional(value) for key, value in extra.items()},
    }


def keyboard_params(
    event_type: str,
    *,
    key: str | None = None,
    code: str | None = None,
    text: str | None = None,
) -> dict[str, Any]:
    return {
        "eventType": event_type,
        "key": optional(key),
        "code": optional(code),
        "text": optional(text),
    }


def wheel_params(
    delta_y: float = 100,
    *,
    delta_x: float = 0,
    x: float = 0,
    y: float = 0,
) -> dict[str, Any]:
    return {"x": x, "y": y, "deltaX": delta_x, "deltaY": delta_y}


def mouse_params(
    event_type: MouseEventType,
    *,
    x: float = 0,
    y: float = 0,
    button: str = "none",
    click_count: int = 0,
) -> dict[str, Any]:
    return {
        "eventType": event_type,
        "x": x,
        "y": y,
        "button": button,
        "clickCount": click_count,
    }
