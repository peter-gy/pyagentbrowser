from __future__ import annotations

from pathlib import Path
from typing import Any

from agentbrowser.contracts.protocol import optional, path_value


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
