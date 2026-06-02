from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

SEARCH_ROOTS = (Path("README.md"), Path("docs"), Path("examples"))
TEXT_SUFFIXES = {".md", ".py"}

FORBIDDEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ab.visit", re.compile(r"ab\.visit")),
    ("ab.screenshot", re.compile(r"ab\.screenshot")),
    ("browser.open", re.compile(r"browser\.open")),
    ("Browser.evaluate", re.compile(r"Browser\.evaluate")),
    ("browser.evaluate", re.compile(r"browser\.evaluate")),
    ("browser.locator", re.compile(r"browser\.locator")),
    ("browser.get_by_", re.compile(r"browser\.get_by_")),
    ("browser.cdp frame sugar", re.compile(r"browser\.cdp\.(frames|frame|contexts)")),
    ("screenshot_image", re.compile(r"screenshot_image")),
    ("to_pil", re.compile(r"to_pil")),
    ("as_markdown", re.compile(r"as_markdown")),
    ("get_all", re.compile(r"get_all")),
    (".file(", re.compile(r"\.file\(")),
)


@dataclass(frozen=True, slots=True)
class ForbiddenMatch:
    path: Path
    line_number: int
    label: str
    line: str

    def format(self) -> str:
        return f"{self.path}:{self.line_number}: forbidden {self.label}: {self.line.strip()}"


class DocsCheckError(RuntimeError):
    pass


def _die(message: str) -> NoReturn:
    raise DocsCheckError(message)


def iter_text_files(roots: tuple[Path, ...] = SEARCH_ROOTS) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            _die(f"docs check path does not exist: {root}")
        if root.is_file():
            if root.suffix in TEXT_SUFFIXES:
                files.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if "__pycache__" in path.parts:
                continue
            if path.is_file() and path.suffix in TEXT_SUFFIXES:
                files.append(path)
    return files


def find_forbidden_matches(files: list[Path]) -> list[ForbiddenMatch]:
    matches: list[ForbiddenMatch] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            _die(f"could not read {path}: {exc}")
        except UnicodeDecodeError as exc:
            _die(f"{path} is not valid UTF-8 text: {exc}")

        for line_number, line in enumerate(text.splitlines(), start=1):
            for label, pattern in FORBIDDEN_PATTERNS:
                if pattern.search(line):
                    matches.append(ForbiddenMatch(path, line_number, label, line))
    return matches


def find_support_junk() -> list[Path]:
    figures = Path("docs/figures")
    if not figures.exists():
        return []
    return sorted(path for path in figures.rglob("*") if path.is_file())


def check_docs(roots: tuple[Path, ...] = SEARCH_ROOTS) -> None:
    files = iter_text_files(roots)
    matches = find_forbidden_matches(files)
    support_junk = find_support_junk()

    errors = [match.format() for match in matches]
    errors.extend(f"unreferenced docs support artifact: {path}" for path in support_junk)
    if errors:
        raise DocsCheckError("\n".join(errors))


def main() -> int:
    try:
        check_docs()
    except DocsCheckError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
