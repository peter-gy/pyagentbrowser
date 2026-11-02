from __future__ import annotations

from pathlib import Path

import pytest

from agentbrowser import StateLoadResult
from tests.support.browser import _browser
from tests.support.browser_site import LocalSite
from tests.support.browser_site import local_site as local_site

pytestmark = pytest.mark.integration


def test_cookie_attributes_round_trip_through_the_native_engine(
    chrome_path: Path, local_site: LocalSite
) -> None:
    (local_site.root / "index.html").write_text("<title>App</title>")
    with _browser(chrome_path) as browser:
        browser.page.open(f"{local_site.base_url}/index.html")
        browser.cookies.set("session", "abc", http_only=True, same_site="Strict")

        (cookie,) = browser.cookies.get()

        assert (cookie.name, cookie.value, cookie.domain, cookie.path) == (
            "session",
            "abc",
            "127.0.0.1",
            "/",
        )
        assert cookie.http_only is True
        assert cookie.same_site == "Strict"
        assert cookie.session is True
        assert cookie.expires == -1


def test_state_load_restores_storage_for_the_active_origin(
    chrome_path: Path, local_site: LocalSite, tmp_path: Path
) -> None:
    (local_site.root / "index.html").write_text("<title>App</title>")
    page_url = f"{local_site.base_url}/index.html"
    with _browser(chrome_path) as browser:
        browser.page.open(page_url)
        browser.storage.set("theme", "dark")
        state_path = browser.state.save(tmp_path / "state.json")

    with _browser(chrome_path) as browser:
        browser.page.open(page_url)

        result = browser.state.load(state_path)

        assert result == StateLoadResult(path=state_path, skipped_origins=())
        assert browser.storage.get("theme") == "dark"
