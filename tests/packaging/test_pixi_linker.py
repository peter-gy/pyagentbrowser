from __future__ import annotations

import ctypes
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.packaging


@pytest.mark.skipif(
    sys.platform != "linux" or not os.environ.get("PIXI_PROJECT_ROOT"),
    reason="requires the Pixi Linux compiler",
)
def test_pixi_linker_produces_a_loadable_library_without_an_environment_rpath(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "sitecustomize.py").write_text("import sys\nsys.path.clear()\n")
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    linker = os.environ[f"CARGO_TARGET_{platform.machine().upper()}_UNKNOWN_LINUX_GNU_LINKER"]
    library_path = tmp_path / "library with spaces.so"
    subprocess.run(
        [linker, "-shared", "-fPIC", "-x", "c", "-", "-o", str(library_path)],
        input="int answer(void) { return 42; }\n",
        text=True,
        capture_output=True,
        check=True,
    )
    assert os.environ["CONDA_PREFIX"].encode() not in library_path.read_bytes()
    library = ctypes.CDLL(str(library_path))
    assert library.answer() == 42

    executable = tmp_path / "rust executable"
    subprocess.run(
        [
            "rustc",
            "-C",
            f"linker={linker}",
            "--crate-name",
            "linker_probe",
            "-o",
            str(executable),
            "-",
        ],
        input='fn main() { println!("{}", 42); }\n',
        text=True,
        capture_output=True,
        check=True,
    )
    assert os.environ["CONDA_PREFIX"].encode() not in executable.read_bytes()
    result = subprocess.run([str(executable)], text=True, capture_output=True, check=True)
    assert result.stdout == "42\n"
