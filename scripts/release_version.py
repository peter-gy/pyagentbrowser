from __future__ import annotations

import re
from dataclasses import dataclass

_NUMBER = r"(?:0|[1-9][0-9]*)"
_RELEASE_PATTERN = re.compile(
    rf"(?P<upstream>{_NUMBER}\.{_NUMBER}\.{_NUMBER})"
    rf"(?:\.(?P<revision>[1-9][0-9]*))?"
    rf"(?:rc(?P<rc>{_NUMBER}))?"
)


class ReleaseVersionError(ValueError):
    pass


@dataclass(frozen=True)
class ReleaseVersion:
    upstream: str
    revision: int = 0
    release_candidate: int | None = None

    @classmethod
    def parse(cls, value: str) -> ReleaseVersion:
        match = _RELEASE_PATTERN.fullmatch(value)
        if match is None:
            raise ReleaseVersionError(
                f"invalid pyagentbrowser version {value!r}: expected "
                "X.Y.Z, X.Y.Z.N, X.Y.ZrcN, or X.Y.Z.NrcN"
            )
        revision = match.group("revision")
        release_candidate = match.group("rc")
        return cls(
            upstream=match.group("upstream"),
            revision=int(revision) if revision is not None else 0,
            release_candidate=(int(release_candidate) if release_candidate is not None else None),
        )

    @classmethod
    def from_tag(cls, tag: str) -> ReleaseVersion:
        if not tag.startswith("v"):
            raise ReleaseVersionError(
                f"invalid pyagentbrowser tag {tag!r}: expected vX.Y.Z, vX.Y.Z.N, "
                "vX.Y.ZrcN, or vX.Y.Z.NrcN"
            )
        return cls.parse(tag.removeprefix("v"))

    @property
    def public(self) -> str:
        value = self.upstream
        if self.revision:
            value += f".{self.revision}"
        if self.release_candidate is not None:
            value += f"rc{self.release_candidate}"
        return value

    @property
    def tag(self) -> str:
        return f"v{self.public}"

    @property
    def cargo(self) -> str:
        value = self.upstream
        if self.release_candidate is not None:
            value += f"-rc.{self.release_candidate}"
        if self.revision:
            value += f"+py.{self.revision}"
        return value

    def __str__(self) -> str:
        return self.public
