from __future__ import annotations

import pyagentbrowser as ab
from pyagentbrowser import Browser, RestoreOptions

session_id = ab.session_id(prefix="docs").session

with Browser.from_session(
    session_id,
    restore=RestoreOptions(key=session_id, check_text="Example Domain"),
) as browser:
    browser.page.open("https://example.com")
    print(browser.restore.info()["restoreStatus"])
