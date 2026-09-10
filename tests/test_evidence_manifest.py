from __future__ import annotations

from pathlib import Path

import pytest
from fakes import ScriptedNative
from support.sdk import _browser

from agentbrowser import (
    EvidenceAssertion,
    EvidenceManifest,
    Screenshot,
)

pytestmark = pytest.mark.sdk_dx


def test_evidence_manifest_separates_capture_delivery_and_assessment(tmp_path: Path) -> None:
    path = tmp_path / "capture.png"
    path.write_bytes(b"png")
    screenshot = Screenshot(path, "png", (), {})
    manifest = EvidenceManifest()

    record = manifest.record(
        "mobile-results",
        screenshot,
        assessment="No horizontal clipping at 390 CSS pixels.",
        assertions=(EvidenceAssertion("content changed", True),),
    )

    data = record.to_dict()
    assert data["captured"] is True
    assert data["delivery"] is None
    assert data["assessment"] == "No horizontal clipping at 390 CSS pixels."
    assert manifest.to_dict()["records"] == [data]


def test_evidence_manifest_serializes_browser_evidence_without_controller_state(
    tmp_path: Path,
) -> None:
    snapshots = iter(
        [
            {
                "snapshot": "button Save [ref=e1]",
                "origin": "https://example.com",
                "refs": {"e1": {"role": "button", "name": "Save"}},
            },
            {
                "snapshot": "button Saved [ref=e1]",
                "origin": "https://example.com",
                "refs": {"e1": {"role": "button", "name": "Saved"}},
            },
        ]
    )
    native = ScriptedNative(
        {
            "snapshot": lambda _command: next(snapshots),
            "click": {},
            "evaluate": {"result": {"before": {"x": 0, "y": 0}, "after": {"x": 0, "y": 10}}},
        }
    )
    browser = _browser(native)
    snapshot = browser.page.observe()
    action = snapshot.one(name="Save").click()
    scroll = browser.page.scroll.by(y=10)
    path = tmp_path / "capture.png"
    path.write_bytes(b"png")
    screenshot = Screenshot(path, "png", (), {}, scope=browser.page.scope)
    manifest = EvidenceManifest()

    for name, value in (
        ("snapshot", snapshot),
        ("action", action),
        ("screenshot", screenshot),
        ("scroll", scroll),
    ):
        manifest.record(name, value)

    records = manifest.to_dict()["records"]
    assert [record["kind"] for record in records] == [
        "Snapshot",
        "ActionResult",
        "Screenshot",
        "ScrollResult",
    ]
    assert records[1]["value"]["after"]["text"] == "button Saved [ref=e1]"
