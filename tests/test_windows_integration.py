from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from agentbrowser import Browser, LaunchOptions

pytestmark = pytest.mark.integration

if sys.platform == "win32":

    def test_forced_python_exit_reaps_owned_chrome_tree(chrome_path: Path, tmp_path: Path) -> None:
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
        kernel.TerminateProcess.restype = wintypes.BOOL

        ready = tmp_path / "processes.json"
        script = """
import json
import sys
import time
from pathlib import Path
from agentbrowser import Browser, LaunchOptions

with Browser.launch(LaunchOptions(executable_path=Path(sys.argv[1]))) as browser:
    browser.page.open('data:text/html,<title>Owned tree</title><h1>Renderer</h1>')
    processes = browser.cdp.send('SystemInfo.getProcessInfo')['processInfo']
    ready = Path(sys.argv[2])
    staging = ready.with_suffix('.tmp')
    staging.write_text(json.dumps(processes), encoding='utf-8')
    staging.replace(ready)
    time.sleep(60)
"""
        handles: list[int] = []
        with Browser.launch(LaunchOptions(executable_path=chrome_path)) as unrelated:
            unrelated.open("data:text/html,<title>Independent browser</title>")
            with (tmp_path / "owner.log").open("w+", encoding="utf-8") as log:
                owner = subprocess.Popen(
                    [sys.executable, "-c", script, str(chrome_path), str(ready)],
                    stdout=log,
                    stderr=log,
                )
                try:
                    deadline = time.monotonic() + 45
                    while not ready.exists() and owner.poll() is None:
                        if time.monotonic() >= deadline:
                            break
                        time.sleep(0.1)
                    log.seek(0)
                    assert ready.exists(), log.read()
                    processes = json.loads(ready.read_text(encoding="utf-8"))
                    assert any(process["type"] == "browser" for process in processes)
                    assert any(process["type"] == "renderer" for process in processes)
                    for process in processes:
                        handle = kernel.OpenProcess(0x00100001, False, int(process["id"]))
                        assert handle, ctypes.WinError(ctypes.get_last_error())
                        handles.append(handle)
                        assert kernel.WaitForSingleObject(handle, 0) == 258

                    owner.kill()
                    owner.wait(timeout=10)

                    for handle in handles:
                        assert kernel.WaitForSingleObject(handle, 10000) == 0
                    assert unrelated.title() == "Independent browser"
                finally:
                    if owner.poll() is None:
                        owner.kill()
                        owner.wait(timeout=10)
                    for handle in handles:
                        if kernel.WaitForSingleObject(handle, 0) == 258:
                            kernel.TerminateProcess(handle, 1)
                            kernel.WaitForSingleObject(handle, 5000)
                        kernel.CloseHandle(handle)
