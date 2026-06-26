"""Python bindings for the native Rust `agent-browser` engine.

The public package follows upstream concepts from https://agent-browser.dev/:
commands (https://agent-browser.dev/commands), selectors
(https://agent-browser.dev/selectors), snapshots
(https://agent-browser.dev/snapshots), sessions
(https://agent-browser.dev/sessions), configuration
(https://agent-browser.dev/configuration), and CDP mode
(https://agent-browser.dev/cdp-mode).
"""

from importlib.metadata import PackageNotFoundError, version

from pyagentbrowser import skills
from pyagentbrowser._native import __agent_browser_version__ as __upstream_version__
from pyagentbrowser._version import PACKAGE_NAME, PACKAGE_VERSION, UPSTREAM_COMMIT
from pyagentbrowser.agent import Agent, AgentRef, AgentSnapshot, StaleAgentRefError
from pyagentbrowser.agent_async import (
    AsyncAgent,
    AsyncAgentRef,
    AsyncAgentSnapshot,
    AsyncStaleAgentRefError,
)
from pyagentbrowser.browser import Browser
from pyagentbrowser.browser_async import AsyncBrowser
from pyagentbrowser.cdp import (
    AsyncExecutionContext,
    AsyncFrame,
    CDPContextAmbiguityError,
    CDPContextNotFoundError,
    CDPError,
    CDPEvaluationError,
    CDPFrameAmbiguityError,
    CDPFrameNotFoundError,
    CDPProtocolError,
    CDPStaleObjectError,
    CDPTargetAmbiguityError,
    CDPTargetNotFoundError,
    CDPTimeoutError,
    ExecutionContext,
    Frame,
)
from pyagentbrowser.default_session import (
    agent,
    capture,
    cdp,
    clipboard,
    close,
    configure,
    cookies,
    default_browser,
    diagnostics,
    dialogs,
    diff,
    downloads,
    find,
    frames,
    keyboard,
    mouse,
    network,
    page,
    reset,
    scripts,
    state,
    storage,
    tabs,
)
from pyagentbrowser.models import (
    ActionConfirmationRequired,
    ActionEvidence,
    AgentBrowserError,
    BoundingBox,
    BrowserError,
    BrowserResponse,
    ConsoleMessage,
    Cookie,
    DashboardOptions,
    LlmsMode,
    NetworkRequest,
    ProxyConfig,
    ReadResult,
    RequestDetail,
    RouteResponse,
    Screenshot,
    ScreenshotAnnotation,
    ScreenshotBox,
    Snapshot,
    SnapshotDiff,
    SnapshotRef,
    TabInfo,
)
from pyagentbrowser.skills import Skill, SkillFile, SkillPart

try:
    __version__ = version(PACKAGE_NAME)
except PackageNotFoundError:
    __version__ = PACKAGE_VERSION

__agent_browser_version__ = __upstream_version__
__agent_browser_commit__ = UPSTREAM_COMMIT
__upstream_commit__ = UPSTREAM_COMMIT

__all__ = [
    "ActionConfirmationRequired",
    "ActionEvidence",
    "Agent",
    "AgentBrowserError",
    "AgentRef",
    "AgentSnapshot",
    "AsyncAgent",
    "AsyncAgentRef",
    "AsyncAgentSnapshot",
    "AsyncBrowser",
    "AsyncExecutionContext",
    "AsyncFrame",
    "AsyncStaleAgentRefError",
    "BoundingBox",
    "Browser",
    "BrowserError",
    "BrowserResponse",
    "CDPContextAmbiguityError",
    "CDPContextNotFoundError",
    "CDPError",
    "CDPEvaluationError",
    "CDPFrameAmbiguityError",
    "CDPFrameNotFoundError",
    "CDPProtocolError",
    "CDPStaleObjectError",
    "CDPTargetAmbiguityError",
    "CDPTargetNotFoundError",
    "CDPTimeoutError",
    "ConsoleMessage",
    "Cookie",
    "DashboardOptions",
    "ExecutionContext",
    "Frame",
    "LlmsMode",
    "NetworkRequest",
    "ProxyConfig",
    "ReadResult",
    "RequestDetail",
    "RouteResponse",
    "Screenshot",
    "ScreenshotAnnotation",
    "ScreenshotBox",
    "Skill",
    "SkillFile",
    "SkillPart",
    "Snapshot",
    "SnapshotDiff",
    "SnapshotRef",
    "StaleAgentRefError",
    "TabInfo",
    "__agent_browser_commit__",
    "__agent_browser_version__",
    "__upstream_commit__",
    "__upstream_version__",
    "__version__",
    "agent",
    "capture",
    "cdp",
    "clipboard",
    "close",
    "configure",
    "cookies",
    "default_browser",
    "diagnostics",
    "dialogs",
    "diff",
    "downloads",
    "find",
    "frames",
    "keyboard",
    "mouse",
    "network",
    "page",
    "reset",
    "scripts",
    "skills",
    "state",
    "storage",
    "tabs",
]
