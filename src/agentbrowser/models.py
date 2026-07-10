from __future__ import annotations

import builtins
import importlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeAlias, TypeVar, cast

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage

else:
    PILImage = Any

JSONPrimitive: TypeAlias = str | int | float | bool | None
# Command-level JSON stays shallow so raw native payloads can pass through.
# Stable SDK helpers expose typed models for response shapes the SDK owns.
JSONValue: TypeAlias = object
JSONObject: TypeAlias = dict[str, JSONValue]
JSONMapping: TypeAlias = Mapping[str, JSONValue]
LoadState = Literal["load", "domcontentloaded", "networkidle", "none"]
LlmsMode = Literal["index", "full"]
MouseButton = Literal["left", "right", "middle"]
MouseEventType = Literal["mouseMoved", "mousePressed", "mouseReleased", "mouseWheel"]
RestoreSave = Literal["auto", "always", "never"]
SameSite = Literal["Strict", "Lax", "None"]
SessionIdScope = Literal["worktree", "cwd", "git-root"]
StorageArea = Literal["local", "session"]
WaitSelectorState = Literal["attached", "detached", "hidden", "visible"]
ColorScheme = Literal["dark", "light", "no-preference"]
T = TypeVar("T")
RefT = TypeVar("RefT")
SnapshotT = TypeVar("SnapshotT")


@dataclass(frozen=True, slots=True)
class RestoreOptions:
    """State restore policy for a native browser session."""

    key: str
    save: RestoreSave | None = None
    autosave_interval_ms: int | None = None
    check_url: str | None = None
    check_text: str | None = None
    check_fn: str | None = None

    def __post_init__(self) -> None:
        if not _is_valid_session_component(self.key):
            raise ValueError(
                f"Invalid restore key '{self.key}'. Only alphanumeric characters, "
                "hyphens, and underscores are allowed."
            )
        if self.save is not None and self.save not in {"auto", "always", "never"}:
            raise ValueError("save must be 'auto', 'always', or 'never'")
        if self.autosave_interval_ms is not None and self.autosave_interval_ms < 0:
            raise ValueError("autosave_interval_ms must be non-negative")


def _is_valid_session_component(value: str) -> bool:
    return bool(value) and all(char.isalnum() or char in {"-", "_"} for char in value)


class _OmitType:
    __slots__ = ()

    def __repr__(self) -> str:
        return "OMIT"


OMIT = _OmitType()


class AgentBrowserError(RuntimeError):
    """Common catchable base for Python SDK errors."""


class NativeParseError(AgentBrowserError, ValueError):
    """Raised when native payloads cannot be parsed into typed SDK models."""


class BrowserError(AgentBrowserError):
    """Raised when the native agent-browser engine returns an unsuccessful response.

    Command behavior follows https://agent-browser.dev/commands.
    """

    def __init__(
        self,
        action: str,
        message: str,
        response: Mapping[str, Any],
        *,
        code: str | None = None,
    ) -> None:
        super().__init__(f"{action} failed: {message}")
        self.action = action
        self.response = dict(response)
        self.code = code or _error_code_from_response(response)


class ConfirmationRequired(BrowserError, Generic[T]):
    """Raised when the native policy requires confirmation before execution."""

    def __init__(
        self,
        action: str,
        data: Mapping[str, Any],
        response: Mapping[str, Any],
    ) -> None:
        confirmation_id = data.get("confirmation_id") or response.get("id")
        super().__init__(
            action,
            f"confirmation required for {action}",
            response,
        )
        self.confirmation_id = str(confirmation_id) if confirmation_id is not None else None
        self.data = dict(data)
        self.pending = cast(T, None)


@dataclass(frozen=True, slots=True)
class BrowserResponse:
    """Native response envelope returned by `browser.native.execute()`.

    Attributes
    ----------
    id
        Native command id.
    action
        Native action name.
    success
        Whether the native command succeeded.
    data
        Raw response data.
    raw
        Complete native response mapping.
    warning
        Optional native warning message.
    """

    id: str
    action: str
    success: bool
    data: JSONValue
    raw: JSONMapping
    warning: str | None = None


def _error_code_from_response(response: Mapping[str, Any]) -> str | None:
    for key in ("code", "error_code", "errorCode"):
        value = response.get(key)
        if value is not None:
            return str(value)

    data = response.get("data")
    if isinstance(data, Mapping):
        for key in ("code", "error_code", "errorCode"):
            value = data.get(key)
            if value is not None:
                return str(value)
    return None


@dataclass(frozen=True, slots=True)
class DashboardOptions:
    """Options for opt-in upstream dashboard observability.

    Parameters
    ----------
    port
        Dashboard port, or `0` to request an ephemeral port.
    cli_version
        Expected upstream CLI version for dashboard compatibility checks.
    """

    port: int | None = None
    cli_version: str | None = None

    def __post_init__(self) -> None:
        if self.port is not None and not 0 <= self.port <= 65535:
            raise ValueError("dashboard port must be between 0 and 65535")
        if self.cli_version is not None and not self.cli_version.strip():
            raise ValueError("dashboard cli_version must not be empty")


@dataclass(frozen=True, slots=True)
class SnapshotSpec:
    """Options that define a reproducible accessibility snapshot."""

    selector: str | None = None
    interactive: bool = True
    compact: bool = False
    max_depth: int | None = None
    urls: bool = False

    def __post_init__(self) -> None:
        if self.max_depth is not None and self.max_depth < 0:
            raise ValueError("max_depth must be non-negative")


@dataclass(frozen=True, slots=True)
class Wait:
    """Condition applied after an agent action."""

    kind: Literal["text", "url", "load", "all"]
    value: str | None = None
    timeout_ms: int | None = None
    conditions: tuple[Wait, ...] = ()

    def __post_init__(self) -> None:
        if self.timeout_ms is not None and self.timeout_ms < 0:
            raise ValueError("timeout_ms must be non-negative")
        if self.kind == "all":
            if not self.conditions:
                raise ValueError("Wait.all requires at least one condition")
            if self.value is not None:
                raise ValueError("Wait.all does not accept a value")
        elif self.value is None or self.conditions:
            raise ValueError(f"Wait.{self.kind} requires one value")

    @classmethod
    def text(cls, text: str, *, timeout_ms: int | None = None) -> Wait:
        """Wait for page text after an action."""
        return cls("text", text, timeout_ms)

    @classmethod
    def url(cls, url: str, *, timeout_ms: int | None = None) -> Wait:
        """Wait for a URL pattern after an action."""
        return cls("url", url, timeout_ms)

    @classmethod
    def loaded(
        cls,
        state: LoadState = "load",
        *,
        timeout_ms: int | None = None,
    ) -> Wait:
        """Wait for a page load state after an action."""
        return cls("load", state, timeout_ms)

    @classmethod
    def all(cls, *conditions: Wait) -> Wait:
        """Apply several wait conditions in order."""
        return cls("all", conditions=tuple(conditions))


@dataclass(frozen=True, slots=True)
class SnapshotData:
    """Parsed native accessibility snapshot data.

    Attributes
    ----------
    text
        Human-readable snapshot text.
    origin
        Page URL or origin reported by the native engine.
    refs
        Mapping of snapshot ref ids to accessible metadata.
    raw
        Complete native response mapping.
    """

    text: str
    origin: str
    refs: Mapping[str, Mapping[str, Any]]
    raw: Mapping[str, Any]
    spec: SnapshotSpec = field(default_factory=SnapshotSpec)

    def ref(self, ref_id: str) -> SnapshotRef:
        """Return one snapshot ref by id.

        Parameters
        ----------
        ref_id
            Ref id with or without the leading `@`.

        Returns
        -------
        SnapshotRef
            Parsed ref metadata.
        """
        normalized = normalize_ref(ref_id)
        metadata = self.refs.get(normalized)
        if metadata is None:
            raise KeyError(f"snapshot has no ref {ref_selector(ref_id)}")
        return SnapshotRef(
            id=normalized,
            role=str(metadata.get("role", "")),
            name=str(metadata.get("name", "")),
            raw=metadata,
        )

    def find_refs(
        self,
        *,
        role: str | None = None,
        name: str | None = None,
        contains: str | None = None,
        exact: bool = False,
    ) -> list[SnapshotRef]:
        """Return refs matching role/name/text criteria."""
        refs = [self.ref(ref_id) for ref_id in self.refs]
        return [
            ref
            for ref in refs
            if _matches_ref(ref, role=role, name=name, contains=contains, exact=exact)
        ]


@dataclass(frozen=True, slots=True)
class SnapshotRef:
    """A deterministic element ref produced by an agent-browser snapshot."""

    id: str
    role: str
    name: str
    raw: Mapping[str, Any]

    @property
    def selector(self) -> str:
        """Selector form accepted by native commands, for example `@r1`."""
        return ref_selector(self.id)


def snapshot_from_data(
    data: Mapping[str, Any],
    *,
    spec: SnapshotSpec | None = None,
) -> SnapshotData:
    text = data.get("snapshot")
    origin = data.get("origin")
    raw_refs = data.get("refs")
    if not isinstance(text, str):
        raise NativeParseError("Snapshot field 'snapshot' must be a string")
    if not isinstance(origin, str):
        raise NativeParseError("Snapshot field 'origin' must be a string")
    if not isinstance(raw_refs, Mapping):
        raise NativeParseError("Snapshot field 'refs' must be an object")
    refs: dict[str, dict[str, Any]] = {}
    for key, value in raw_refs.items():
        if not isinstance(value, Mapping):
            raise NativeParseError("Snapshot ref metadata must be objects")
        if not isinstance(value.get("role"), str) or not isinstance(value.get("name"), str):
            raise NativeParseError("Snapshot refs require string 'role' and 'name' fields")
        refs[str(key)] = {str(ref_key): ref_value for ref_key, ref_value in value.items()}
    return SnapshotData(
        text=text,
        origin=origin,
        refs=refs,
        raw=data,
        spec=spec or SnapshotSpec(),
    )


@dataclass(frozen=True, slots=True)
class SnapshotDiff:
    """Parsed snapshot diff result."""

    text: str
    additions: int
    removals: int
    unchanged: int
    changed: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ActionResult(Generic[RefT, SnapshotT]):
    """Before/after evidence for an agent action."""

    action: str
    target: RefT
    before: SnapshotT
    after: SnapshotT
    diff: SnapshotDiff


class ActionTransitionError(AgentBrowserError, Generic[RefT, SnapshotT]):
    """Raised after an action succeeds but transition evidence cannot complete."""

    def __init__(
        self,
        *,
        action: str,
        target: RefT,
        stage: Literal["wait", "snapshot", "diff"],
        before: SnapshotT,
        after: SnapshotT | None,
        cause: BaseException,
    ) -> None:
        super().__init__(f"{action} completed, then {stage} failed: {cause}")
        self.action = action
        self.target = target
        self.stage = stage
        self.before = before
        self.after = after
        self.cause = cause


def diff_snapshot_data(before: SnapshotData, after: SnapshotData) -> SnapshotDiff:
    """Compare two captured snapshots without reading live browser state again."""
    before_lines = [f"origin: {before.origin}", *before.text.splitlines()]
    after_lines = [f"origin: {after.origin}", *after.text.splitlines()]
    additions = 0
    removals = 0
    unchanged = 0
    for tag, before_start, before_end, after_start, after_end in SequenceMatcher(
        None,
        before_lines,
        after_lines,
        autojunk=False,
    ).get_opcodes():
        if tag == "equal":
            unchanged += before_end - before_start
        elif tag == "insert":
            additions += after_end - after_start
        elif tag == "delete":
            removals += before_end - before_start
        else:
            removals += before_end - before_start
            additions += after_end - after_start
    text = "\n".join(
        unified_diff(
            before_lines,
            after_lines,
            fromfile="before",
            tofile="after",
            lineterm="",
        )
    )
    return SnapshotDiff(
        text=text,
        additions=additions,
        removals=removals,
        unchanged=unchanged,
        changed=before_lines != after_lines,
        raw={
            "before": before.text,
            "after": after.text,
            "beforeOrigin": before.origin,
            "afterOrigin": after.origin,
        },
    )


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Element bounding box in CSS pixels."""

    x: float
    y: float
    width: float
    height: float
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TabInfo:
    """Metadata for one browser tab or target."""

    id: str
    url: str
    title: str = ""
    label: str | None = None
    active: bool = False
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Cookie:
    """Browser cookie metadata."""

    name: str
    value: str
    domain: str | None = None
    path: str | None = None
    expires: float | None = None
    http_only: bool | None = None
    secure: bool | None = None
    same_site: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NetworkRequest:
    """Captured network request summary."""

    id: str
    url: str
    method: str = ""
    resource_type: str = ""
    status: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RequestDetail:
    """Detailed request and response metadata."""

    id: str
    url: str = ""
    method: str = ""
    status: int | None = None
    request_headers: Mapping[str, Any] = field(default_factory=dict)
    response_headers: Mapping[str, Any] = field(default_factory=dict)
    body: str | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReadResult:
    """Markdown-oriented content returned by `browser.read()`."""

    url: str
    final_url: str
    status: int | None
    content_type: str
    source: str
    truncated: bool
    content: str
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ReadMode:
    """Native read mode passed to `browser.read(mode=...)`."""

    raw: bool = False
    require_markdown: bool = False
    llms: LlmsMode | None = None
    outline: bool = False

    def __post_init__(self) -> None:
        if self.llms not in {None, "index", "full"}:
            raise ValueError("llms must be 'index', 'full', or None")
        if self.raw and (self.require_markdown or self.llms is not None or self.outline):
            raise ValueError("ReadMode.html() cannot be combined with markdown, llms, or outline")
        if self.outline and (self.require_markdown or self.llms is not None):
            raise ValueError("ReadMode.outline_only() cannot be combined with markdown or llms")

    @classmethod
    def html(cls) -> ReadMode:
        """Return raw HTML content when native read supports it."""
        return cls(raw=True)

    @classmethod
    def markdown(cls, *, require: bool = False) -> ReadMode:
        """Return Markdown-oriented content."""
        return cls(require_markdown=require)

    @classmethod
    def llms_index(cls, *, require_markdown: bool = False) -> ReadMode:
        """Read through llms.txt index discovery."""
        return cls(require_markdown=require_markdown, llms="index")

    @classmethod
    def llms_full(cls, *, require_markdown: bool = False) -> ReadMode:
        """Read through full llms.txt content discovery."""
        return cls(require_markdown=require_markdown, llms="full")

    @classmethod
    def outline_only(cls) -> ReadMode:
        """Return outline extraction content."""
        return cls(outline=True)


@dataclass(frozen=True, slots=True)
class SessionId:
    """Stable session id derived from a filesystem scope."""

    session: str
    scope: SessionIdScope
    path: str
    hash: str

    def __str__(self) -> str:
        return self.session


@dataclass(frozen=True, slots=True)
class ConsoleMessage:
    """Captured browser console message."""

    type: str
    text: str
    level: str | None = None
    url: str | None = None
    line: int | None = None
    column: int | None = None
    raw: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScreenshotBox:
    """Rectangle for one screenshot annotation."""

    x: int
    y: int
    width: int
    height: int
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class ScreenshotAnnotation:
    """Annotation entry for an interactable screenshot element."""

    ref: str
    number: int
    role: str
    name: str | None
    box: ScreenshotBox
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Screenshot:
    """Screenshot file and optional annotation metadata.

    Attributes
    ----------
    path
        Path to the captured image file.
    format
        Image format, such as `png` or `jpeg`.
    annotations
        Native element annotations, if requested.
    raw
        Complete native response mapping.
    """

    path: Path
    format: str
    annotations: tuple[ScreenshotAnnotation, ...]
    raw: Mapping[str, Any]
    _image: PILImage | None = field(default=None, init=False, compare=False, repr=False)

    @property
    def image(self) -> PILImage:
        """Lazily load and cache the screenshot as a Pillow image."""
        if self._image is None:
            image = self.pil()
            object.__setattr__(self, "_image", image)
            return image
        return self._image

    def pil(self, *, mode: str | None = None) -> PILImage:
        """Load the screenshot as a Pillow image.

        Pillow is an optional dependency so non-image workflows keep the core
        SDK lightweight.

        Parameters
        ----------
        mode
            Optional Pillow mode to convert to, for example `RGB`.

        Returns
        -------
        PIL.Image.Image
            Loaded image.
        """

        try:
            from PIL import Image
        except ModuleNotFoundError as exc:
            raise ImportError(
                "Pillow is required for Screenshot.pil(). "
                'install pyagentbrowser with the "images" extra or install pillow.'
            ) from exc

        image = Image.open(self.path)
        image.load()
        if mode is not None:
            return image.convert(mode)
        return image

    def bytes(self) -> builtins.bytes:
        """Return the screenshot file bytes."""
        return self.path.read_bytes()

    def _repr_png_(self) -> builtins.bytes | None:
        """Return PNG bytes for notebook frontends when applicable."""
        if self.format != "png":
            return None
        return self.bytes()

    def _repr_mimebundle_(
        self,
        include: object = None,
        exclude: object = None,
    ) -> tuple[dict[str, builtins.bytes], dict[str, Any]]:
        """Return notebook display data for the screenshot image."""
        del include, exclude
        return {_image_mime_type(self.format): self.bytes()}, {}

    def marimo(
        self,
        *,
        alt: str | None = None,
        width: int | str | None = None,
        height: int | str | None = None,
        rounded: bool = False,
        caption: str | None = None,
        style: Mapping[str, Any] | None = None,
    ) -> Any:
        """Return a `marimo.image` view for this screenshot."""
        try:
            mo = importlib.import_module("marimo")
        except ModuleNotFoundError as exc:
            raise ImportError("marimo is required for Screenshot.marimo().") from exc
        image = cast(Any, mo).image
        return image(
            src=str(self.path),
            alt=alt,
            width=width,
            height=height,
            rounded=rounded,
            caption=caption,
            style=dict(style) if style is not None else None,
        )

    def save(self, path: str | Path) -> Screenshot:
        """Copy the screenshot file and return metadata for the new path."""
        target = Path(path)
        if target != self.path:
            target.parent.mkdir(parents=True, exist_ok=True)
            copyfile(self.path, target)
        return Screenshot(
            path=target,
            format=self.format,
            annotations=self.annotations,
            raw={**self.raw, "path": str(target)},
        )


def screenshot_from_data(
    data: Mapping[str, Any],
    *,
    format: str = "png",
) -> Screenshot:
    path = data.get("path")
    if not isinstance(path, str):
        raise NativeParseError("Screenshot field 'path' must be a string")
    return Screenshot(
        path=Path(path),
        format=_normalize_image_format(format),
        annotations=_parse_screenshot_annotations(data.get("annotations")),
        raw=data,
    )


def bounding_box_from_data(data: Mapping[str, Any]) -> BoundingBox | None:
    box = _first_mapping(data, "box", "boundingBox", "rect") or data
    if not any(key in box for key in ("x", "y", "width", "height")):
        return None
    _require_keys(box, "BoundingBox", "x", "y", "width", "height")
    return BoundingBox(
        x=_float(box.get("x")),
        y=_float(box.get("y")),
        width=_float(box.get("width")),
        height=_float(box.get("height")),
        raw=box,
    )


def tabs_from_data(data: Mapping[str, Any]) -> tuple[TabInfo, ...]:
    raw_tabs = data.get("tabs")
    if not isinstance(raw_tabs, list):
        raise NativeParseError("TabInfo collection field 'tabs' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_tabs):
        raise NativeParseError("TabInfo collection entries must be objects")
    return tuple(_tab_info(cast(Mapping[str, Any], item)) for item in raw_tabs)


def tab_from_data(data: Mapping[str, Any]) -> TabInfo:
    raw = _first_mapping(data, "tab", "page") or data
    return _tab_info(raw)


def cookies_from_data(data: Mapping[str, Any]) -> tuple[Cookie, ...]:
    raw_cookies = data.get("cookies")
    if not isinstance(raw_cookies, list):
        raise NativeParseError("Cookie collection field 'cookies' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_cookies):
        raise NativeParseError("Cookie collection entries must be objects")
    return tuple(_cookie(cast(Mapping[str, Any], item)) for item in raw_cookies)


def network_requests_from_data(data: Mapping[str, Any]) -> tuple[NetworkRequest, ...]:
    raw_requests = data.get("requests")
    if not isinstance(raw_requests, list):
        raise NativeParseError("NetworkRequest collection field 'requests' must be an array")
    if any(not isinstance(item, Mapping) for item in raw_requests):
        raise NativeParseError("NetworkRequest collection entries must be objects")
    return tuple(_network_request(cast(Mapping[str, Any], item)) for item in raw_requests)


def request_detail_from_data(data: Mapping[str, Any]) -> RequestDetail:
    raw = _first_mapping(data, "request", "detail") or data
    id_value = _first_present(raw, "requestId", "id", model="RequestDetail", field="id")
    url_value = _first_present(raw, "url", model="RequestDetail", field="url")
    request_headers = raw.get("requestHeaders") or raw.get("headers") or {}
    response_headers = raw.get("responseHeaders") or {}
    return RequestDetail(
        id=str(id_value),
        url=str(url_value),
        method=str(raw.get("method", "")),
        status=_optional_int(raw.get("status")),
        request_headers=dict(request_headers) if isinstance(request_headers, Mapping) else {},
        response_headers=dict(response_headers) if isinstance(response_headers, Mapping) else {},
        body=str(raw["body"]) if raw.get("body") is not None else None,
        raw=raw,
    )


def read_result_from_data(data: Mapping[str, Any]) -> ReadResult:
    _require_keys(data, "ReadResult", "content")
    return ReadResult(
        url=str(data.get("url", "")),
        final_url=str(data.get("finalUrl") or data.get("final_url") or data.get("url") or ""),
        status=_optional_int(data.get("status")),
        content_type=str(data.get("contentType") or data.get("content_type") or ""),
        source=str(data.get("source", "")),
        truncated=bool(data.get("truncated", False)),
        content=str(data.get("content", "")),
        raw=data,
    )


def console_messages_from_data(data: Mapping[str, Any]) -> tuple[ConsoleMessage, ...]:
    raw_messages = next(
        (data[field] for field in ("messages", "logs", "entries") if field in data),
        None,
    )
    if not isinstance(raw_messages, list):
        raise NativeParseError("ConsoleMessage collection must be an array")
    if any(not isinstance(item, Mapping) for item in raw_messages):
        raise NativeParseError("ConsoleMessage collection entries must be objects")
    return tuple(_console_message(cast(Mapping[str, Any], item)) for item in raw_messages)


@dataclass(frozen=True, slots=True)
class RouteResponse:
    """Static route response used by `browser.network.route()`."""

    status: int | None = None
    body: str | None = None
    content_type: str | None = None
    headers: Mapping[str, str] | None = None

    def as_command_value(self) -> JSONObject:
        return {
            key: value
            for key, value in {
                "status": self.status,
                "body": self.body,
                "contentType": self.content_type,
                "headers": dict(self.headers) if self.headers is not None else None,
            }.items()
            if value is not None
        }


def path_value(value: str | Path | None) -> str | None:
    return str(value) if value is not None else None


@dataclass(frozen=True, slots=True)
class ProxyConfig:
    """Browser proxy configuration."""

    server: str
    bypass: str | None = None
    username: str | None = None
    password: str | None = None

    def as_command_value(self) -> JSONObject:
        return {
            key: value
            for key, value in {
                "server": self.server,
                "bypass": self.bypass,
                "username": self.username,
                "password": self.password,
            }.items()
            if value is not None
        }


def ref_selector(ref_id: str) -> str:
    return f"@{normalize_ref(ref_id)}"


def normalize_ref(ref_id: str) -> str:
    return ref_id[1:] if ref_id.startswith("@") else ref_id


def proxy_value(
    value: str | ProxyConfig | Mapping[str, Any] | None,
) -> str | JSONObject | None:
    if isinstance(value, ProxyConfig):
        return value.as_command_value()
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items() if item is not None}
    return value


def paths_value(values: SequencePath) -> list[str]:
    return [str(value) for value in values]


SequencePath = Sequence[str | Path]


def _normalize_image_format(value: str) -> str:
    normalized = value.lower()
    return "jpeg" if normalized in {"jpg", "jpeg"} else normalized


def _image_mime_type(format: str) -> str:
    return f"image/{_normalize_image_format(format)}"


def _parse_screenshot_annotations(value: Any) -> tuple[ScreenshotAnnotation, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(
        annotation
        for item in value
        if isinstance(item, Mapping)
        for annotation in [_parse_screenshot_annotation(item)]
        if annotation is not None
    )


def _parse_screenshot_annotation(raw: Mapping[str, Any]) -> ScreenshotAnnotation | None:
    box_raw = raw.get("box")
    if not isinstance(box_raw, Mapping):
        return None
    return ScreenshotAnnotation(
        ref=str(raw.get("ref", "")),
        number=int(raw.get("number", 0)),
        role=str(raw.get("role", "")),
        name=str(raw["name"]) if raw.get("name") is not None else None,
        box=ScreenshotBox(
            x=int(box_raw.get("x", 0)),
            y=int(box_raw.get("y", 0)),
            width=int(box_raw.get("width", 0)),
            height=int(box_raw.get("height", 0)),
            raw=box_raw,
        ),
        raw=raw,
    )


def _first_mapping(data: Mapping[str, Any], *keys: str) -> Mapping[str, Any] | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def _require_keys(raw: Mapping[str, Any], model: str, *keys: str) -> None:
    missing = [key for key in keys if raw.get(key) is None]
    if missing:
        raise NativeParseError(f"{model} missing required native field: {', '.join(missing)}")


def _first_present(
    raw: Mapping[str, Any],
    *keys: str,
    model: str,
    field: str,
) -> Any:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    raise NativeParseError(f"{model} missing required native field: {field}")


def _tab_info(raw: Mapping[str, Any]) -> TabInfo:
    id_value = _first_present(raw, "id", "tabId", "targetId", model="TabInfo", field="id")
    url_value = _first_present(raw, "url", model="TabInfo", field="url")
    return TabInfo(
        id=str(id_value),
        url=str(url_value),
        title=str(raw.get("title", "")),
        label=str(raw["label"]) if raw.get("label") is not None else None,
        active=bool(raw.get("active") or raw.get("selected") or raw.get("current")),
        raw=raw,
    )


def _cookie(raw: Mapping[str, Any]) -> Cookie:
    http_only = raw.get("httpOnly") if "httpOnly" in raw else raw.get("http_only")
    _require_keys(raw, "Cookie", "name", "value")
    return Cookie(
        name=str(raw.get("name", "")),
        value=str(raw.get("value", "")),
        domain=str(raw["domain"]) if raw.get("domain") is not None else None,
        path=str(raw["path"]) if raw.get("path") is not None else None,
        expires=_optional_float(raw.get("expires")),
        http_only=_optional_bool(http_only),
        secure=_optional_bool(raw.get("secure")),
        same_site=str(raw["sameSite"]) if raw.get("sameSite") is not None else None,
        raw=raw,
    )


def _network_request(raw: Mapping[str, Any]) -> NetworkRequest:
    id_value = _first_present(raw, "requestId", "id", model="NetworkRequest", field="id")
    url_value = _first_present(raw, "url", model="NetworkRequest", field="url")
    return NetworkRequest(
        id=str(id_value),
        url=str(url_value),
        method=str(raw.get("method", "")),
        resource_type=str(raw.get("type") or raw.get("resourceType") or ""),
        status=_optional_int(raw.get("status")),
        raw=raw,
    )


def _console_message(raw: Mapping[str, Any]) -> ConsoleMessage:
    type_value = _first_present(raw, "type", "kind", "level", model="ConsoleMessage", field="type")
    text_value = _first_present(raw, "text", "message", model="ConsoleMessage", field="text")
    return ConsoleMessage(
        type=str(type_value),
        text=str(text_value),
        level=str(raw["level"]) if raw.get("level") is not None else None,
        url=str(raw["url"]) if raw.get("url") is not None else None,
        line=_optional_int(raw.get("line") or raw.get("lineNumber")),
        column=_optional_int(raw.get("column") or raw.get("columnNumber")),
        raw=raw,
    )


def _optional_bool(value: Any) -> bool | None:
    return bool(value) if value is not None else None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _float(value: Any) -> float:
    return float(value if value is not None else 0)


def _matches_ref(
    ref: SnapshotRef,
    *,
    role: str | None,
    name: str | None,
    contains: str | None,
    exact: bool,
) -> bool:
    if role is not None and ref.role != role:
        return False
    if name is not None:
        matches_name = ref.name == name if exact else name in ref.name
        if not matches_name:
            return False
    if contains is None:
        return True
    return ref.name == contains if exact else contains in ref.name
