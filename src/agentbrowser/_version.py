"""Release metadata for the Python SDK and embedded upstream engine."""

import json
from pathlib import Path

PACKAGE_NAME = "pyagentbrowser"
PACKAGE_VERSION = "0.32.0a1"

_UPSTREAM = json.loads(Path(__file__).with_name("_upstream.json").read_text())
UPSTREAM_TAG = str(_UPSTREAM["tag"])
UPSTREAM_VERSION = str(_UPSTREAM["version"])
UPSTREAM_COMMIT = str(_UPSTREAM["commit"])
