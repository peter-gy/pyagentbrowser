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

from agentbrowser import skills
from agentbrowser._browser_common import ConfirmationTarget
from agentbrowser._native import __agent_browser_version__ as __upstream_version__
from agentbrowser._version import PACKAGE_NAME, PACKAGE_VERSION, UPSTREAM_COMMIT
from agentbrowser.agent import Agent, AgentRef, AgentSnapshot, StaleAgentRefError
from agentbrowser.agent_async import (
    AsyncAgent,
    AsyncAgentRef,
    AsyncAgentSnapshot,
    AsyncStaleAgentRefError,
)
from agentbrowser.browser import Browser, PendingAction
from agentbrowser.browser_async import AsyncBrowser, AsyncPendingAction
from agentbrowser.cdp import (
    AsyncExecutionContext,
    AsyncFrame,
    CDPClosedError,
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
from agentbrowser.default_session import (
    active_frame,
    agent,
    capture,
    cdp,
    clipboard,
    close,
    configure,
    cookies,
    dashboard,
    default_browser,
    diagnostics,
    dialogs,
    diff,
    downloads,
    find,
    keyboard,
    mouse,
    native,
    network,
    page,
    reset,
    restore,
    runtime,
    scripts,
    state,
    storage,
    tabs,
)
from agentbrowser.install import BrowserInstallError, InstallResult, ensure_installed
from agentbrowser.launch import (
    BrowserSessionOptions,
    BrowserSessionOptionsDict,
    CDPAttach,
    CDPAttachDict,
    LaunchOptions,
    LaunchOptionsDict,
)
from agentbrowser.models import (
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
    NativeParseError,
    NetworkRequest,
    ProxyConfig,
    ReadMode,
    ReadResult,
    RequestDetail,
    RestoreOptions,
    RestoreSave,
    RouteResponse,
    Screenshot,
    ScreenshotAnnotation,
    ScreenshotBox,
    SessionId,
    SessionIdScope,
    Snapshot,
    SnapshotDiff,
    SnapshotRef,
    TabInfo,
)
from agentbrowser.session_id import generate_session_id as session_id
from agentbrowser.skills import Skill, SkillFile, SkillPart

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
    "AsyncPendingAction",
    "AsyncStaleAgentRefError",
    "BoundingBox",
    "Browser",
    "BrowserError",
    "BrowserInstallError",
    "BrowserResponse",
    "BrowserSessionOptions",
    "BrowserSessionOptionsDict",
    "CDPAttach",
    "CDPAttachDict",
    "CDPClosedError",
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
    "ConfirmationTarget",
    "ConsoleMessage",
    "Cookie",
    "DashboardOptions",
    "ExecutionContext",
    "Frame",
    "InstallResult",
    "LaunchOptions",
    "LaunchOptionsDict",
    "LlmsMode",
    "NativeParseError",
    "NetworkRequest",
    "PendingAction",
    "ProxyConfig",
    "ReadMode",
    "ReadResult",
    "RequestDetail",
    "RestoreOptions",
    "RestoreSave",
    "RouteResponse",
    "Screenshot",
    "ScreenshotAnnotation",
    "ScreenshotBox",
    "SessionId",
    "SessionIdScope",
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
    "active_frame",
    "agent",
    "capture",
    "cdp",
    "clipboard",
    "close",
    "configure",
    "cookies",
    "dashboard",
    "default_browser",
    "diagnostics",
    "dialogs",
    "diff",
    "downloads",
    "ensure_installed",
    "find",
    "keyboard",
    "mouse",
    "native",
    "network",
    "page",
    "reset",
    "restore",
    "runtime",
    "scripts",
    "session_id",
    "skills",
    "state",
    "storage",
    "tabs",
]
