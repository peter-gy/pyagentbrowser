from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

import pytest

from agentbrowser import (
    AccessibilityAudit,
    BrowserError,
)
from agentbrowser.cdp import CDPStaleObjectError
from tests.support.browser import (
    _browser,
)
from tests.support.browser_site import LocalSite
from tests.support.browser_site import local_site as local_site

pytestmark = pytest.mark.integration


def test_accessibility_audit_runs_the_embedded_engine_with_scope(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    page_name = "accessibility-audit.html"
    image_source = "data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="
    (local_site.root / page_name).write_text(
        "<!doctype html>"
        '<html lang="en"><head><title>Audit</title></head><body>'
        f'<img id="outside-image" src="{image_source}">'
        '<main id="audit-root">'
        f'<img id="missing-alt" src="{image_source}">'
        "</main>"
        "</body></html>"
    )

    with _browser(chrome_path) as browser:
        previous_frame = browser.cdp.frames.get()
        audit = browser.diagnostics.accessibility(
            f"{local_site.base_url}/{page_name}",
            tags=("wcag2a",),
            selector="#audit-root",
        )

        with pytest.raises(CDPStaleObjectError, match="stale"):
            previous_frame.evaluate("document.title")

        current_frame = browser.cdp.frames.get()
        browser.diagnostics.accessibility(
            tags=("wcag2a",),
            selector="#audit-root",
        )
        assert current_frame.evaluate("document.title") == "Audit"

        with pytest.raises(BrowserError, match="No element matches"):
            browser.diagnostics.accessibility(
                f"{local_site.base_url}/{page_name}",
                selector="#missing",
            )
        with pytest.raises(CDPStaleObjectError, match="stale"):
            current_frame.evaluate("document.title")

    assert isinstance(audit, AccessibilityAudit)
    assert audit.axe_version == "4.12.1"
    issue = next(item for item in audit.violations if item.id == "image-alt")
    assert issue.node_count == 1
    assert issue.nodes[0].target == ("#missing-alt",)


def test_accessibility_audit_reports_an_invalid_selector(chrome_path: Path) -> None:
    with _browser(chrome_path) as browser:
        browser.page.set_content("<main>Audit</main>")

        with pytest.raises(BrowserError, match=r"Invalid selector: main::bogus\("):
            browser.diagnostics.accessibility(selector="main::bogus(")


def test_webmcp_discovery_invocation_and_cancellation_cross_the_native_boundary(
    chrome_path: Path,
    local_site: LocalSite,
) -> None:
    page_name = "webmcp.html"
    (local_site.root / page_name).write_text(
        """<!doctype html>
<output id="result">idle</output>
<script>
  if (typeof document.modelContext?.registerTool !== "function") {
    document.body.dataset.webmcpReady = "unavailable";
  } else {
    const setMessage = document.modelContext.registerTool({
      name: "set_message",
      description: "Sets the visible message",
      inputSchema: {
        type: "object",
        properties: {message: {type: "string"}},
        required: ["message"],
        additionalProperties: false
      },
      annotations: {readOnlyHint: false},
      execute: async ({message}) => {
        document.getElementById("result").textContent = message;
        return {message};
      }
    });
    const waitForCancel = document.modelContext.registerTool({
      name: "wait_for_cancel",
      description: "Waits until canceled",
      inputSchema: {type: "object", properties: {}},
      annotations: {readOnlyHint: true},
      execute: async () => new Promise(() => {})
    });
    Promise.all([setMessage, waitForCancel]).then(() => {
      document.body.dataset.webmcpReady = "true";
    });
  }
</script>
"""
    )

    with _browser(chrome_path) as browser:
        navigation = browser.native.data("navigate", url=f"{local_site.base_url}/{page_name}")
        browser.page.wait_for_function("document.body.dataset.webmcpReady !== undefined")
        if browser.page.evaluate("document.body.dataset.webmcpReady") == "unavailable":
            assert sys.platform == "darwin"
            try:
                assert browser.webmcp.list() == ()
            except BrowserError as error:
                assert error.code == "webmcp_unsupported"
            return

        tools = browser.webmcp.list()
        availability = cast(dict[str, Any], navigation["webmcp"])
        assert isinstance(availability, dict)
        assert availability["experimental"] is True
        assert availability["available"] is True
        assert 1 <= availability["toolCount"] <= len(tools)
        set_message = next(tool for tool in tools if tool.name == "set_message")
        completed = browser.webmcp.invoke(
            set_message.name,
            {"message": "WebMCP works"},
            timeout_ms=5000,
        )
        pending = browser.webmcp.invoke("wait_for_cancel", detach=True)
        canceled = browser.webmcp.cancel(pending.invocation_id)

        assert set_message.origin == local_site.base_url
        assert set_message.input_schema["type"] == "object"
        assert completed.status == "completed"
        assert completed.output == {"message": "WebMCP works"}
        assert (
            browser.page.evaluate("document.getElementById('result').textContent") == "WebMCP works"
        )
        assert canceled.status == "canceled"
        with pytest.raises(BrowserError) as missing:
            browser.webmcp.invoke("missing_tool")
        assert missing.value.code == "webmcp_tool_not_found"
