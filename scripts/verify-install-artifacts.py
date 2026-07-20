from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from email.message import Message
from email.parser import Parser
from pathlib import Path

INSTALL_CHECK = r"""
from __future__ import annotations

import importlib.metadata as metadata
import importlib.util
import importlib.resources as resources
from pathlib import Path

import agentbrowser as ab
import agentbrowser.skills as skills
from agentbrowser import Browser, CloseResult, RestoreSaveError, SessionStatus
from agentbrowser.cdp import CDPClient
from agentbrowser.models import Screenshot

assert Browser
assert metadata.version("pyagentbrowser")
assert isinstance(ab.__agent_browser_version__, str)
assert ab.__agent_browser_version__
assert importlib.util.find_spec("pyagentbrowser") is None
assert resources.files("agentbrowser").joinpath("py.typed").is_file()

browser = Browser()
assert isinstance(browser.session.status(), SessionStatus)
assert isinstance(browser.close(), CloseResult)

assert "core" in skills.available()
assert "derive-client" in skills.available()
assert skills.get("core").parts
assert skills.get("derive-client").parts
core = skills.get("core", full=True)
assert core.files
full_markdown = skills.markdown("core", full=True)
core_content = skills.read("core")
assert core_content
assert core_content in full_markdown
for supplement in core.files:
    supplement_content = skills.read("core", supplement.path)
    assert supplement_content
    assert supplement.path in full_markdown
    assert supplement_content in full_markdown

try:
    Screenshot(path=Path("missing.png"), format="png", annotations=(), raw={}).pil()
except ImportError as exc:
    assert "pyagentbrowser" in str(exc)
    assert "images" in str(exc)
else:
    raise AssertionError("Screenshot.pil() should explain the missing images extra")

try:
    CDPClient("ws://127.0.0.1:9", timeout=0.01).send("Browser.getVersion")
except ImportError as exc:
    assert "pyagentbrowser[cdp]" in str(exc)
else:
    raise AssertionError("CDPClient should explain the missing cdp extra")
"""

EXTRAS_CHECK = r"""
from __future__ import annotations

import base64
import json
import tempfile
import threading
from pathlib import Path

from agentbrowser.cdp import CDPClient
from agentbrowser.models import Screenshot
from websockets.sync.server import serve

def cdp_handler(websocket):
    request = json.loads(websocket.recv())
    websocket.send(json.dumps({"id": request["id"], "result": {"ok": True}}))

with serve(cdp_handler, "127.0.0.1", 0) as server:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.socket.getsockname()[1]
        client = CDPClient(f"ws://127.0.0.1:{port}", timeout=2)
        assert client.send("Runtime.evaluate") == {"ok": True}
        client.close()
    finally:
        server.shutdown()
        thread.join(timeout=2)

png = Path(tempfile.gettempdir()) / "pyagentbrowser-extra-smoke.png"
png.write_bytes(
    base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42m"
        "P8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
    )
)
image = Screenshot(path=png, format="png", annotations=(), raw={}).pil()
assert image.size == (1, 1)
"""


def venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def create_clean_venv(root: Path, python_version: str) -> None:
    if shutil.which("uv") is None:
        if python_version != f"{sys.version_info.major}.{sys.version_info.minor}":
            raise RuntimeError("uv is required to create non-current Python smoke environments")
        import venv

        venv.EnvBuilder(with_pip=True).create(root)
        return

    subprocess.check_call(["uv", "venv", "--seed", "--python", python_version, str(root)])


def requirement(artifact: Path, *, extras: tuple[str, ...] = ()) -> str:
    extra = f"[{','.join(extras)}]" if extras else ""
    return f"pyagentbrowser{extra} @ {artifact.resolve().as_uri()}"


def artifact_metadata(artifact: Path) -> Message:
    if artifact.suffix == ".whl":
        with zipfile.ZipFile(artifact) as archive:
            metadata_names = [
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            ]
            if len(metadata_names) != 1:
                raise RuntimeError(f"expected one wheel METADATA file, found {metadata_names}")
            return Parser().parsestr(archive.read(metadata_names[0]).decode())
    if artifact.name.endswith(".tar.gz"):
        with tarfile.open(artifact) as archive:
            metadata_names = [name for name in archive.getnames() if name.endswith("/PKG-INFO")]
            if len(metadata_names) != 1:
                raise RuntimeError(f"expected one sdist PKG-INFO file, found {metadata_names}")
            member = archive.extractfile(metadata_names[0])
            if member is None:
                raise RuntimeError("sdist PKG-INFO could not be read")
            return Parser().parsestr(member.read().decode())
    raise RuntimeError(f"unsupported artifact type: {artifact}")


def artifact_extras(artifact: Path) -> tuple[str, ...]:
    return tuple(sorted(artifact_metadata(artifact).get_all("Provides-Extra") or []))


def pip_install(
    python: Path,
    artifact: Path,
    *,
    extras: tuple[str, ...] = (),
    no_binary: bool = False,
) -> None:
    command = [str(python), "-m", "pip", "install"]
    if no_binary:
        command.extend(["--no-binary", "pyagentbrowser", "--no-cache-dir"])
    command.append(requirement(artifact, extras=extras))
    subprocess.check_call(command)


def verify_install(
    artifact: Path,
    *,
    python_version: str,
    no_binary: bool = False,
    check_extras: bool = True,
) -> None:
    with tempfile.TemporaryDirectory(prefix="pyagentbrowser-install-") as workspace_root:
        workspace = Path(workspace_root)
        env_dir = workspace / "venv"
        local_artifact = workspace / artifact.name
        shutil.copy2(artifact, local_artifact)
        create_clean_venv(env_dir, python_version)
        python = venv_python(env_dir)
        pip_install(python, local_artifact, no_binary=no_binary)
        subprocess.check_call([str(python), "-m", "pip", "check"])
        subprocess.check_call([str(python), "-c", INSTALL_CHECK])
        if not check_extras:
            return
        pip_install(
            python,
            local_artifact,
            extras=artifact_extras(local_artifact),
            no_binary=no_binary,
        )
        subprocess.check_call([str(python), "-m", "pip", "check"])
        subprocess.check_call([str(python), "-c", EXTRAS_CHECK])


def python_versions() -> list[str]:
    raw = os.environ.get("PYAGENTBROWSER_PYTHON_VERSIONS")
    if raw:
        return raw.split()
    return [f"{sys.version_info.major}.{sys.version_info.minor}"]


def endpoint_versions(versions: list[str]) -> list[str]:
    return list(dict.fromkeys((versions[0], versions[-1])))


def _python_tag_version(tag: str) -> tuple[int, int]:
    digits = tag.removeprefix("cp")
    return int(digits[0]), int(digits[1:])


def wheel_for_version(dist: Path, python_version: str) -> Path:
    tag = f"cp{python_version.replace('.', '')}"
    wheels = sorted(path for path in dist.glob("pyagentbrowser-*.whl") if f"-{tag}-" in path.name)
    if not wheels:
        requested = tuple(int(part) for part in python_version.split(".", 1))
        wheels = sorted(
            path
            for path in dist.glob("pyagentbrowser-*.whl")
            if (match := re.match(r"^pyagentbrowser-[^-]+-(cp\d+)-abi3-", path.name))
            and _python_tag_version(match.group(1)) <= requested
        )
    if len(wheels) != 1:
        raise RuntimeError(
            f"expected exactly one {tag} or compatible abi3 wheel in {dist}, "
            f"found {[path.name for path in wheels]}"
        )
    return wheels[0]


def main() -> None:
    dist = Path(sys.argv[1])
    versions = python_versions()
    for version in versions:
        wheel = wheel_for_version(dist, version)
        verify_install(wheel, python_version=version)
        print(f"wheel install smoke passed: {wheel.name} on Python {version}")

    sdists = sorted(dist.glob("pyagentbrowser-*.tar.gz"))
    if len(sdists) > 1:
        raise RuntimeError(f"expected at most one sdist, found {[path.name for path in sdists]}")
    if sdists:
        for version in endpoint_versions(versions):
            verify_install(sdists[0], python_version=version, no_binary=True, check_extras=False)
            print(f"sdist install smoke passed: {sdists[0].name} on Python {version}")


if __name__ == "__main__":
    main()
