"""Agent-first Python SDK for the native agent-browser engine."""

from importlib.metadata import PackageNotFoundError, version

from agentbrowser._native import __agent_browser_version__ as __upstream_version__
from agentbrowser._version import PACKAGE_NAME, PACKAGE_VERSION, UPSTREAM_COMMIT
from agentbrowser.browser import Browser
from agentbrowser.browser_async import AsyncBrowser
from agentbrowser.contracts.connection import ProxyConfig
from agentbrowser.contracts.errors import (
    AgentBrowserError,
    BrowserError,
    ConfirmationRequired,
    FrameLookupError,
    NativeParseError,
)
from agentbrowser.contracts.execution import ExecutionContext
from agentbrowser.contracts.images import ImageContent, ImageDelivery
from agentbrowser.contracts.protocol import BrowserResponse
from agentbrowser.contracts.scope import DocumentScope
from agentbrowser.execution.commands import AsyncExecutor, Command, Executor
from agentbrowser.execution.pending import AsyncPendingAction, PendingAction
from agentbrowser.features.capture.models import Screenshot
from agentbrowser.features.diagnostics.models import (
    AccessibilityAudit,
    AccessibilityCounts,
    AccessibilityIssue,
    AccessibilityNode,
    ConsoleMessage,
)
from agentbrowser.features.documents.handles import Frame, Page
from agentbrowser.features.documents.handles_async import AsyncFrame, AsyncPage
from agentbrowser.features.documents.models import ElementGeometry, ScrollPosition, ScrollResult
from agentbrowser.features.documents.read import ReadMode, ReadResult
from agentbrowser.features.evidence.changes import ActionResult, ActionTransitionError, SnapshotDiff
from agentbrowser.features.evidence.errors import AsyncStaleRefError, StaleRefError
from agentbrowser.features.evidence.manifest import (
    EvidenceAssertion,
    EvidenceManifest,
    EvidenceRecord,
)
from agentbrowser.features.evidence.models import SnapshotSpec
from agentbrowser.features.evidence.ref import Ref
from agentbrowser.features.evidence.ref_async import AsyncRef
from agentbrowser.features.evidence.snapshots import AsyncSnapshot, Snapshot
from agentbrowser.features.evidence.waits import Wait
from agentbrowser.features.network.models import (
    HarContentMode,
    NetworkRequest,
    RequestDetail,
    RouteResponse,
)
from agentbrowser.features.queries import AsyncQuery, Query
from agentbrowser.features.session.models import (
    CloseResult,
    DashboardOptions,
    RestoreOptions,
    RestoreSaveError,
    SessionId,
    SessionStatus,
)
from agentbrowser.features.storage.models import Cookie
from agentbrowser.features.tabs.models import TabCloseResult, TabInfo, TabSwitchResult
from agentbrowser.features.webmcp.models import WebMCPInvocation, WebMCPInvocationStatus, WebMCPTool
from agentbrowser.health import BrowserCapabilities, HealthCheck, HealthCheckEntry
from agentbrowser.install import BrowserInstallError, InstallResult, ensure_installed
from agentbrowser.integrations.host import (
    AgentConnectionStatus,
    AgentHost,
    AttachedTarget,
    BrowserTarget,
    CallbackHost,
    ManagedTask,
    ManagedTaskHost,
    ManagedTaskStatus,
    OpenTarget,
    bind_host,
    current_host,
    reset_host,
)
from agentbrowser.integrations.runtime import CodeSession
from agentbrowser.integrations.tasks import Task, Tasks
from agentbrowser.launch import (
    CDPTarget,
    LaunchOptions,
    SessionOptions,
)
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
    "AsyncExecutor",
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
    "CodeSession",
    "Command",
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
    "Executor",
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
    "Task",
    "Tasks",
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
