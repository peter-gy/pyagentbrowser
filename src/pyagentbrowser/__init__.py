"""Python bindings for the native Rust `agent-browser` engine.

The public package follows upstream concepts from https://agent-browser.dev/:
commands (https://agent-browser.dev/commands), selectors
(https://agent-browser.dev/selectors), snapshots
(https://agent-browser.dev/snapshots), sessions
(https://agent-browser.dev/sessions), configuration
(https://agent-browser.dev/configuration), and CDP mode
(https://agent-browser.dev/cdp-mode).
"""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

from pyagentbrowser import skills
from pyagentbrowser._browser_common import ConfirmationTarget
from pyagentbrowser._native import __agent_browser_version__ as __upstream_version__
from pyagentbrowser._version import PACKAGE_NAME, PACKAGE_VERSION, UPSTREAM_COMMIT
from pyagentbrowser.agent import Agent, AgentRef, AgentSnapshot, StaleAgentRefError
from pyagentbrowser.agent_async import (
    AsyncAgent,
    AsyncAgentRef,
    AsyncAgentSnapshot,
    AsyncStaleAgentRefError,
)
from pyagentbrowser.browser import Browser, PendingAction
from pyagentbrowser.browser_async import AsyncBrowser, AsyncPendingAction
from pyagentbrowser.cdp import (
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
from pyagentbrowser.launch import BrowserSessionOptions, CDPAttach, LaunchOptions
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
from pyagentbrowser.session_id import generate_session_id as session_id
from pyagentbrowser.skills import Skill, SkillFile, SkillPart

try:
    __version__ = version(PACKAGE_NAME)
except PackageNotFoundError:
    __version__ = PACKAGE_VERSION

__agent_browser_version__ = __upstream_version__
__agent_browser_commit__ = UPSTREAM_COMMIT
__upstream_commit__ = UPSTREAM_COMMIT
notebook = import_module("pyagentbrowser.notebook")

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
    "BrowserResponse",
    "BrowserSessionOptions",
    "CDPAttach",
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
    "LaunchOptions",
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
    "notebook",
    "session_id",
    "skills",
]
