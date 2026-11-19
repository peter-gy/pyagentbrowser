from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging

ROOT = Path(__file__).resolve().parents[2]


def test_pixi_supplies_the_rust_toolchain_that_rust_toolchain_toml_pins() -> None:
    channel = tomllib.loads((ROOT / "rust-toolchain.toml").read_text())["toolchain"]["channel"]
    pixi = tomllib.loads((ROOT / "pixi.toml").read_text())

    assert pixi["dependencies"]["rust"] == f"=={channel}"
