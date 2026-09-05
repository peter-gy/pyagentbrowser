from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "development_docs"
INDEX = DOCS / "index.md"
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def main() -> None:
    pages = sorted(DOCS.glob("*.md"))
    index_text = INDEX.read_text()
    errors: list[str] = []

    for page in pages:
        if page != INDEX and f"({page.name})" not in index_text:
            errors.append(f"{page.relative_to(ROOT)} is not linked from development_docs/index.md")

        for target in MARKDOWN_LINK.findall(page.read_text()):
            path = target.split("#", 1)[0]
            if not path or "://" in path:
                continue
            destination = (page.parent / path).resolve()
            if not destination.is_relative_to(ROOT) or not destination.exists():
                errors.append(f"{page.relative_to(ROOT)} has a broken link to {target}")

    if errors:
        raise SystemExit("\n".join(errors))

    print(f"Verified {len(pages)} contributor documentation pages.")


if __name__ == "__main__":
    main()
