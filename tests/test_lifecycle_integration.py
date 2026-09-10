from __future__ import annotations

import asyncio
import subprocess
import time
from pathlib import Path

import pytest

from agentbrowser import (
    AsyncBrowser,
    Browser,
    BrowserError,
    CallbackHost,
    CDPTarget,
    ExecutionContext,
    ImageDelivery,
    LaunchOptions,
    OpenTarget,
    RestoreOptions,
    SessionOptions,
    SessionStatus,
    bind_host,
    reset_host,
)
from tests.support.browser import (
    _browser,
    _data_url,
    _form_html,
    _free_port,
    _session,
    _stop_process,
    _wait_for_cdp,
)
from tests.support.browser_site import LocalSite
from tests.support.browser_site import local_site as local_site

pytestmark = pytest.mark.integration


def _wait_for_restore_save(browser: Browser, timeout: float = 6.0) -> SessionStatus:
    deadline = time.monotonic() + timeout
    latest: SessionStatus | None = None
    while time.monotonic() < deadline:
        latest = browser.session.status()
        if latest.save_status == "saved":
            return latest
        time.sleep(0.1)
    pytest.fail(f"restore state was not autosaved: {latest}")


def test_host_deadline_bounds_native_evaluation_and_allows_recovery(
    chrome_path: Path, local_site: LocalSite
) -> None:
    (local_site.root / "index.html").write_text("<title>Ready</title>")
    with _browser(chrome_path) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        token = bind_host(
            CallbackHost(
                OpenTarget(local_site.base_url),
                lambda _: ImageDelivery("queued"),
                ExecutionContext(timeout_ms=2_000),
            )
        )
        started = time.monotonic()
        try:
            with pytest.raises(BrowserError, match="host deadline") as caught:
                browser.page.evaluate("new Promise(() => {})")
            assert caught.value.code == "execution_timeout"
            assert time.monotonic() - started < 4
        finally:
            reset_host(token)
        assert browser.page.title() == "Ready"


def test_periodic_restore_autosave_survives_abrupt_browser_exit(
    chrome_path: Path,
    local_site: LocalSite,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = f"autosave-{time.monotonic_ns()}"
    session = SessionOptions(
        session_id=key,
        namespace=f"pytest-{key}",
        timeout=5.0,
        restore=RestoreOptions(key, save="always", autosave_interval_ms=100),
    )
    monkeypatch.setenv("AGENT_BROWSER_AUTOSAVE_INTERVAL_MS", "0")
    browser = _browser(chrome_path, session=session)
    saved_path: Path | None = None

    try:
        browser.page.open(local_site.base_url)
        browser.storage.set("periodic", "saved")
        time.sleep(2.2)
        status = _wait_for_restore_save(browser)
        saved_path = status.restore_saved_path
        assert saved_path is not None
        assert saved_path.is_file()

        browser.cdp.send("Browser.close")
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if not browser.session.status().browser_launched:
                break
            time.sleep(0.1)
        assert browser.session.status().browser_launched is False
    finally:
        browser.close()

    restored = _browser(chrome_path, session=session)
    try:
        restored.page.open(local_site.base_url)
        assert restored.session.status().restore_status == "loaded"
        assert restored.storage.get("periodic") == "saved"
    finally:
        restored.close()
        if saved_path is not None:
            saved_path.unlink(missing_ok=True)


def test_browser_attaches_to_an_existing_cdp_target(
    chrome_path: Path,
    tmp_path: Path,
) -> None:
    port = _free_port()
    session = SessionOptions(
        session_id=f"attach-{time.monotonic_ns()}",
        timeout=5.0,
        pin_tab=True,
    )
    process = subprocess.Popen(
        [
            str(chrome_path),
            f"--remote-debugging-port={port}",
            f"--user-data-dir={tmp_path / 'cdp-profile'}",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        if not _wait_for_cdp(port):
            pytest.skip("Chrome CDP endpoint did not become ready")
        target = CDPTarget(port=port)
        with Browser.attach(target, session=session) as browser:
            browser.page.open(_data_url("<title>Attached</title>"))
            assert browser.page.title() == "Attached"
            active = next(tab for tab in browser.tabs.list() if tab.active)
            assert active.target_id

        with Browser.attach(target, session=session) as browser:
            assert browser.page.title() == "Attached"
            restored = next(tab for tab in browser.tabs.list() if tab.active)
            assert restored.target_id == active.target_id
    finally:
        _stop_process(process)


def test_async_native_wait_does_not_block_the_event_loop(chrome_path: Path) -> None:
    async def run() -> None:
        browser = await AsyncBrowser.launch(
            LaunchOptions(executable_path=chrome_path),
            session=_session("async"),
        )
        async with browser:
            await browser.page.open(_data_url(_form_html()))
            wait_task = asyncio.create_task(
                browser.native.data(
                    "wait",
                    function="window.__neverReady === true",
                    timeout=500,
                )
            )

            async def ticker() -> int:
                for _ in range(5):
                    await asyncio.sleep(0.01)
                return 5

            tick_task = asyncio.create_task(ticker())
            done, _ = await asyncio.wait(
                {wait_task, tick_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            assert tick_task in done
            assert wait_task not in done
            with pytest.raises(BrowserError):
                await wait_task
            assert tick_task.result() == 5

    asyncio.run(run())
