from __future__ import annotations

import builtins
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copyfile
from typing import TYPE_CHECKING, Any

from agentbrowser.contracts.images import ImageContent
from agentbrowser.contracts.scope import DocumentScope

if TYPE_CHECKING:
    from PIL.Image import Image as PILImage
else:
    PILImage = Any


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
    scope: DocumentScope | None = None
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

    def content(self) -> ImageContent:
        """Return image bytes and MIME type for an agent host."""
        return ImageContent(self.bytes(), _image_mime_type(self.format), self.path)

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
            scope=self.scope,
        )


def _normalize_image_format(value: str) -> str:
    normalized = value.lower()
    return "jpeg" if normalized in {"jpg", "jpeg"} else normalized


def _image_mime_type(format: str) -> str:
    return f"image/{_normalize_image_format(format)}"
