"""Installed capability and dependency health reporting."""

from __future__ import annotations

from contextlib import suppress
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from importlib.util import find_spec
from pathlib import Path

from agentbrowser.integrations.host import current_host


@dataclass(frozen=True, slots=True)
class BrowserCapabilities:
    """Features available in the current Python environment."""

    screenshots: bool
    image_bytes: bool
    pillow: bool
    direct_cdp: bool
    host_image_delivery: bool


@dataclass(frozen=True, slots=True)
class HealthCheckEntry:
    """Result of one bounded dependency probe."""

    name: str
    status: str
    detail: str
    module_path: Path | None = None
    recovery: str | None = None


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """Dependency probes required by optional browser features."""

    checks: tuple[HealthCheckEntry, ...]

    @property
    def ok(self) -> bool:
        """Return whether every probe is ready."""
        return all(check.status == "ready" for check in self.checks)


def capabilities(*, host: object | None = None) -> BrowserCapabilities:
    """Return configured features without launching a browser."""
    if host is None:
        with suppress(RuntimeError):
            host = current_host()
    return BrowserCapabilities(
        screenshots=True,
        image_bytes=True,
        pillow=find_spec("PIL") is not None,
        direct_cdp=_probe_websockets().status == "ready",
        host_image_delivery=bool(getattr(host, "image_delivery", False)),
    )


def healthcheck() -> HealthCheck:
    """Probe optional image and direct-CDP dependencies."""
    checks = [_probe_pillow(), _probe_websockets()]
    return HealthCheck(tuple(checks))


def _probe_pillow() -> HealthCheckEntry:
    try:
        import PIL
    except ImportError as error:
        return HealthCheckEntry(
            "pillow",
            "unavailable",
            str(error),
            recovery='Install pyagentbrowser with the "images" extra in a clean process.',
        )
    return HealthCheckEntry(
        "pillow",
        "ready",
        f"Pillow {getattr(PIL, '__version__', 'unknown')} is importable",
        _module_path(PIL),
    )


def _probe_websockets() -> HealthCheckEntry:
    try:
        installed = version("websockets")
    except PackageNotFoundError:
        installed = "not installed"
    try:
        import websockets
        from websockets.asyncio.client import connect as async_connect
        from websockets.sync.client import connect

        del connect, async_connect
        loaded = getattr(websockets, "__version__", installed)
        if installed != "not installed" and loaded != installed:
            raise ImportError(f"loaded websockets {loaded} differs from installed {installed}")
    except ImportError as error:
        module = locals().get("websockets")
        return HealthCheckEntry(
            "direct_cdp",
            "unavailable",
            f"Installed websockets: {installed}. Import failed: {error}",
            _module_path(module),
            "Restart the Python process after installing pyagentbrowser[cdp]. "
            "Reloading one websockets module can leave incompatible class identities.",
        )
    return HealthCheckEntry(
        "direct_cdp",
        "ready",
        f"Installed websockets: {installed}. "
        f"Loaded websockets: {getattr(websockets, '__version__', 'unknown')}",
        _module_path(websockets),
    )


def _module_path(module: object | None) -> Path | None:
    value = getattr(module, "__file__", None)
    return Path(value).resolve() if isinstance(value, str) else None
