#!/usr/bin/env -S python3 -I -S
"""Link with the locked Linux GCC sysroot without Conda's environment RPATH."""

# Ignore pip's Python startup hooks; this linker only needs the standard library.

from __future__ import annotations

import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    compiler = Path(os.environ["CONDA_PREFIX"]) / "bin" / f"{platform.machine()}-conda-linux-gnu-cc"
    sysroot = Path(
        subprocess.check_output([str(compiler), "-print-sysroot"], text=True).strip()
    ).resolve()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".specs") as specs:
        subprocess.run([str(compiler), "-dumpspecs"], stdout=specs, check=True)
        # Rust's LLD needs the sysroot directly to resolve glibc linker scripts.
        return subprocess.call(
            [
                str(compiler),
                f"--sysroot={sysroot}",
                "-Xlinker",
                f"--sysroot={sysroot}",
                f"-specs={specs.name}",
                *sys.argv[1:],
            ]
        )


if __name__ == "__main__":
    sys.exit(main())
