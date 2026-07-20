"""Agent-first Python SDK for the native agent-browser engine."""

from importlib.metadata import PackageNotFoundError, version

from agentbrowser._native import __agent_browser_version__ as __upstream_version__
from agentbrowser._version import PACKAGE_NAME, PACKAGE_VERSION, UPSTREAM_COMMIT
from agentbrowser.agent import Ref, Snapshot, StaleRefError
from agentbrowser.agent_async import AsyncRef, AsyncSnapshot, AsyncStaleRefError
from agentbrowser.browser import Browser, PendingAction
from agentbrowser.browser_async import AsyncBrowser, AsyncPendingAction
from agentbrowser.install import BrowserInstallError, InstallResult, ensure_installed
from agentbrowser.launch import (
    CDPTarget,
    LaunchOptions,
    SessionOptions,
)
from agentbrowser.models import (
    ActionResult,
    ActionTransitionError,
    AgentBrowserError,
    BrowserError,
    BrowserResponse,
    CloseResult,
    ConfirmationRequired,
    ConsoleMessage,
    Cookie,
    DashboardOptions,
    HarContentMode,
    NativeParseError,
    NetworkRequest,
    ProxyConfig,
    ReadMode,
    ReadResult,
    RequestDetail,
    RestoreOptions,
    RestoreSaveError,
    RouteResponse,
    Screenshot,
    SessionId,
    SessionStatus,
    SnapshotDiff,
    SnapshotSpec,
    TabInfo,
    Wait,
)
from agentbrowser.query import Query
from agentbrowser.query_async import AsyncQuery
from agentbrowser.session_id import generate_session_id as session_id

try:
    __version__ = version(PACKAGE_NAME)
except PackageNotFoundError:
    __version__ = PACKAGE_VERSION

__agent_browser_version__ = __upstream_version__
__agent_browser_commit__ = UPSTREAM_COMMIT

__all__ = [
    "ActionResult",
    "ActionTransitionError",
    "AgentBrowserError",
    "AsyncBrowser",
    "AsyncPendingAction",
    "AsyncQuery",
    "AsyncRef",
    "AsyncSnapshot",
    "AsyncStaleRefError",
    "Browser",
    "BrowserError",
    "BrowserInstallError",
    "BrowserResponse",
    "CDPTarget",
    "CloseResult",
    "ConfirmationRequired",
    "ConsoleMessage",
    "Cookie",
    "DashboardOptions",
    "HarContentMode",
    "InstallResult",
    "LaunchOptions",
    "NativeParseError",
    "NetworkRequest",
    "PendingAction",
    "ProxyConfig",
    "Query",
    "ReadMode",
    "ReadResult",
    "Ref",
    "RequestDetail",
    "RestoreOptions",
    "RestoreSaveError",
    "RouteResponse",
    "Screenshot",
    "SessionId",
    "SessionOptions",
    "SessionStatus",
    "Snapshot",
    "SnapshotDiff",
    "SnapshotSpec",
    "StaleRefError",
    "TabInfo",
    "Wait",
    "ensure_installed",
    "session_id",
]
