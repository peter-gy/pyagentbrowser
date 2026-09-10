from pathlib import Path


def exclusive_source(
    label: str,
    *,
    inline: str | None,
    path: str | Path | None,
) -> str:
    if inline is None and path is None:
        raise ValueError(f"{label} requires either script=... or path=...")
    if inline is not None and path is not None:
        raise ValueError(f"{label} accepts script=... or path=..., not both")
    if path is not None:
        return Path(path).read_text()
    return str(inline)
