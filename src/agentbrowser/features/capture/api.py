from __future__ import annotations

from asyncio import sleep as async_sleep
from dataclasses import dataclass, replace
from pathlib import Path
from time import sleep as sync_sleep

from agentbrowser.contracts.decode import required_path
from agentbrowser.contracts.errors import ConfirmationRequired
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor, result_scope
from agentbrowser.features.capture.codec import screenshot_from_data
from agentbrowser.features.capture.models import Screenshot
from agentbrowser.features.capture.params import pdf_params, screenshot_params
from agentbrowser.features.capture.validation import validate_screenshot_wait_ms

DEFAULT_SCREENSHOT_WAIT_MS = 100


@dataclass(frozen=True, slots=True)
class _ScreenshotCapture:
    """Screenshot capture shared by page and frame documents."""

    executor: Executor

    def screenshot(
        self,
        path: str | Path | None = None,
        *,
        selector: str | None = None,
        full_page: bool = False,
        annotate: bool = False,
        output_dir: str | Path | None = None,
        format: str = "png",
        quality: int | None = None,
        wait_ms: int = DEFAULT_SCREENSHOT_WAIT_MS,
    ) -> Screenshot:
        """Capture a screenshot.

        Parameters
        ----------
        path
            Optional output path.
        selector
            Optional selector to capture instead of the full viewport or page.
        full_page
            Capture the full scrollable page.
        annotate
            Include native snapshot annotations when supported.
        output_dir
            Optional output directory used by the native engine.
        format
            Image format such as `png`, `jpeg`, or `webp`.
        quality
            Optional lossy image quality.
        wait_ms
            Milliseconds to wait before capture to allow recent paint to settle.

        Returns
        -------
        Screenshot
            Parsed screenshot metadata and file path.
        """
        if path is not None:
            path = Path(path).expanduser()
        if output_dir is not None:
            output_dir = Path(output_dir).expanduser()
        params = screenshot_params(
            path=path,
            selector=selector,
            full_page=full_page,
            annotate=annotate,
            output_dir=output_dir,
            format=format,
            quality=quality,
        )
        _wait_before_screenshot(wait_ms)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
        try:
            screenshot = self.executor.execute(
                Command(
                    "screenshot",
                    {**params},
                    decode=lambda data: screenshot_from_data(data, format=format),
                )
            )
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(self._result)
            raise
        return self._result(screenshot)

    def _result(self, screenshot: Screenshot) -> Screenshot:
        scope = result_scope(self.executor, screenshot.raw)
        return replace(screenshot, scope=scope)


class Capture(_ScreenshotCapture):
    """Page screenshot and PDF capture helpers."""

    def pdf(
        self,
        path: str | Path | None = None,
        *,
        print_background: bool = True,
        landscape: bool = False,
        prefer_css_page_size: bool = False,
    ) -> Path:
        """Print the current page to PDF."""
        return self.executor.execute(
            Command(
                "pdf",
                {
                    **pdf_params(
                        path=path,
                        print_background=print_background,
                        landscape=landscape,
                        prefer_css_page_size=prefer_css_page_size,
                    )
                },
                decode=lambda data: required_path(data, action="pdf"),
            )
        )


@dataclass(frozen=True, slots=True)
class FrameCapture:
    """Screenshot capture for one rendered frame rectangle."""

    executor: Executor

    def screenshot(
        self,
        path: str | Path | None = None,
        *,
        output_dir: str | Path | None = None,
        format: str = "png",
        quality: int | None = None,
        wait_ms: int = DEFAULT_SCREENSHOT_WAIT_MS,
    ) -> Screenshot:
        return _ScreenshotCapture(self.executor).screenshot(
            path,
            output_dir=output_dir,
            format=format,
            quality=quality,
            wait_ms=wait_ms,
        )


def _wait_before_screenshot(wait_ms: int) -> None:
    validate_screenshot_wait_ms(wait_ms)
    if wait_ms:
        sync_sleep(wait_ms / 1000)


@dataclass(frozen=True, slots=True)
class _AsyncScreenshotCapture:
    """Async screenshot capture shared by page and frame documents."""

    executor: AsyncExecutor

    async def screenshot(
        self,
        path: str | Path | None = None,
        *,
        selector: str | None = None,
        full_page: bool = False,
        annotate: bool = False,
        output_dir: str | Path | None = None,
        format: str = "png",
        quality: int | None = None,
        wait_ms: int = DEFAULT_SCREENSHOT_WAIT_MS,
    ) -> Screenshot:
        """Capture a screenshot.

        Parameters
        ----------
        path
            Optional output path.
        selector
            Optional selector to capture instead of the full viewport or page.
        full_page
            Capture the full scrollable page.
        annotate
            Include native snapshot annotations when supported.
        output_dir
            Optional output directory used by the native engine.
        format
            Image format such as `png`, `jpeg`, or `webp`.
        quality
            Optional lossy image quality.
        wait_ms
            Milliseconds to wait before capture to allow recent paint to settle.

        Returns
        -------
        Screenshot
            Parsed screenshot metadata and file path.
        """
        if path is not None:
            path = Path(path).expanduser()
        if output_dir is not None:
            output_dir = Path(output_dir).expanduser()
        params = screenshot_params(
            path=path,
            selector=selector,
            full_page=full_page,
            annotate=annotate,
            output_dir=output_dir,
            format=format,
            quality=quality,
        )
        validate_screenshot_wait_ms(wait_ms)
        await async_sleep(wait_ms / 1000)
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        if output_dir is not None:
            output_dir.mkdir(parents=True, exist_ok=True)
        try:
            screenshot = await self.executor.execute(
                Command(
                    "screenshot",
                    {**params},
                    decode=lambda data: screenshot_from_data(data, format=format),
                )
            )
        except ConfirmationRequired as error:
            if error.pending is not None:
                error.pending = error.pending.map(self._result)
            raise
        return self._result(screenshot)

    def _result(self, screenshot: Screenshot) -> Screenshot:
        scope = result_scope(self.executor, screenshot.raw)
        return replace(screenshot, scope=scope)


class AsyncCapture(_AsyncScreenshotCapture):
    """Async page screenshot and PDF capture helpers."""

    async def pdf(
        self,
        path: str | Path | None = None,
        *,
        print_background: bool = True,
        landscape: bool = False,
        prefer_css_page_size: bool = False,
    ) -> Path:
        """Print the current page to PDF."""
        return await self.executor.execute(
            Command(
                "pdf",
                {
                    **pdf_params(
                        path=path,
                        print_background=print_background,
                        landscape=landscape,
                        prefer_css_page_size=prefer_css_page_size,
                    )
                },
                decode=lambda data: required_path(data, action="pdf"),
            )
        )


@dataclass(frozen=True, slots=True)
class AsyncFrameCapture:
    """Async screenshot capture for one rendered frame rectangle."""

    executor: AsyncExecutor

    async def screenshot(
        self,
        path: str | Path | None = None,
        *,
        output_dir: str | Path | None = None,
        format: str = "png",
        quality: int | None = None,
        wait_ms: int = DEFAULT_SCREENSHOT_WAIT_MS,
    ) -> Screenshot:
        return await _AsyncScreenshotCapture(self.executor).screenshot(
            path,
            output_dir=output_dir,
            format=format,
            quality=quality,
            wait_ms=wait_ms,
        )
