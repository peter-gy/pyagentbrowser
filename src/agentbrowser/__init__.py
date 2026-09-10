"""Agent-first Python SDK for the native agent-browser engine."""

from importlib.metadata import PackageNotFoundError, version

from agentbrowser._evidence import Ref, Snapshot, StaleRefError
from agentbrowser._native import __agent_browser_version__ as __upstream_version__
from agentbrowser._version import PACKAGE_NAME, PACKAGE_VERSION, UPSTREAM_COMMIT
from agentbrowser.agent_async import AsyncRef, AsyncSnapshot, AsyncStaleRefError
from agentbrowser.browser import Browser, PendingAction
from agentbrowser.browser_async import AsyncBrowser, AsyncPendingAction
from agentbrowser.domains import Frame, Page
from agentbrowser.domains_async import AsyncFrame, AsyncPage
from agentbrowser.health import BrowserCapabilities, HealthCheck, HealthCheckEntry
from agentbrowser.host import (
    AgentConnectionStatus,
    AgentHost,
    AttachedTarget,
    BrowserTarget,
    CallbackHost,
    ExecutionContext,
    ImageContent,
    ImageDelivery,
    ManagedTask,
    ManagedTaskHost,
    ManagedTaskStatus,
    OpenTarget,
    bind_host,
    current_host,
    reset_host,
)
from agentbrowser.install import BrowserInstallError, InstallResult, ensure_installed
from agentbrowser.launch import (
    CDPTarget,
    LaunchOptions,
    SessionOptions,
)
from agentbrowser.manifest import EvidenceAssertion, EvidenceManifest, EvidenceRecord
from agentbrowser.models import (
    AccessibilityAudit,
    AccessibilityCounts,
    AccessibilityIssue,
    AccessibilityNode,
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
    DocumentScope,
    ElementGeometry,
    FrameLookupError,
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
    ScrollPosition,
    ScrollResult,
    SessionId,
    SessionStatus,
    SnapshotDiff,
    SnapshotSpec,
    TabCloseResult,
    TabInfo,
    TabSwitchResult,
    Wait,
    WebMCPInvocation,
    WebMCPInvocationStatus,
    WebMCPTool,
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
    "AccessibilityAudit",
    "AccessibilityCounts",
    "AccessibilityIssue",
    "AccessibilityNode",
    "ActionResult",
    "ActionTransitionError",
    "AgentBrowserError",
    "AgentConnectionStatus",
    "AgentHost",
    "AsyncBrowser",
    "AsyncFrame",
    "AsyncPage",
    "AsyncPendingAction",
    "AsyncQuery",
    "AsyncRef",
    "AsyncSnapshot",
    "AsyncStaleRefError",
    "AttachedTarget",
    "Browser",
    "BrowserCapabilities",
    "BrowserError",
    "BrowserInstallError",
    "BrowserResponse",
    "BrowserTarget",
    "CDPTarget",
    "CallbackHost",
    "CloseResult",
    "ConfirmationRequired",
    "ConsoleMessage",
    "Cookie",
    "DashboardOptions",
    "DocumentScope",
    "ElementGeometry",
    "EvidenceAssertion",
    "EvidenceManifest",
    "EvidenceRecord",
    "ExecutionContext",
    "Frame",
    "FrameLookupError",
    "HarContentMode",
    "HealthCheck",
    "HealthCheckEntry",
    "ImageContent",
    "ImageDelivery",
    "InstallResult",
    "LaunchOptions",
    "ManagedTask",
    "ManagedTaskHost",
    "ManagedTaskStatus",
    "NativeParseError",
    "NetworkRequest",
    "OpenTarget",
    "Page",
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
    "ScrollPosition",
    "ScrollResult",
    "SessionId",
    "SessionOptions",
    "SessionStatus",
    "Snapshot",
    "SnapshotDiff",
    "SnapshotSpec",
    "StaleRefError",
    "TabCloseResult",
    "TabInfo",
    "TabSwitchResult",
    "Wait",
    "WebMCPInvocation",
    "WebMCPInvocationStatus",
    "WebMCPTool",
    "bind_host",
    "current_host",
    "ensure_installed",
    "reset_host",
    "session_id",
]
