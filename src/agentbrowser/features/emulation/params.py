from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from agentbrowser.contracts.protocol import OMIT, optional


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
