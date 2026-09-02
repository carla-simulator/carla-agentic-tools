"""The version is written in two places; make drift a test failure."""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def _pyproject_version() -> str:
    text = (REPO / "pyproject.toml").read_text()
    # Only the [project] table's own version; a dependency pin must not match.
    project = text.split("[project]", 1)[1].split("\n[", 1)[0]
    match = re.search(r'^version\s*=\s*"([^"]+)"', project, re.M)
    assert match, "no version in [project]"
    return match.group(1)


def test_package_version_matches_pyproject():
    from carla_agentic_tools import __version__

    assert __version__ == _pyproject_version(), (
        f"__init__.py says {__version__}, pyproject.toml says "
        f"{_pyproject_version()} — update both"
    )


def test_version_is_pep440_release():
    assert re.fullmatch(r"\d+\.\d+\.\d+", _pyproject_version()), \
        "expected a plain X.Y.Z release version"


def _reported_version(server) -> str:
    """The version a client sees, however this SDK exposes it.

    mcp 2.x takes `version` on the constructor and keeps it on the server object;
    1.x's FastMCP has no such parameter and holds a low-level Server that does.
    A published install resolves whichever SDK is newest, so both must be read.
    """
    low = getattr(server.mcp, "_mcp_server", None)
    if low is not None and hasattr(low, "create_initialization_options"):
        return low.create_initialization_options().server_version
    return getattr(server.mcp, "version", "")


def test_server_reports_its_own_version():
    """serverInfo.version must be the skill library's, not the MCP SDK's.

    FastMCP silently drops a `version` kwarg it does not declare, which reports
    the SDK release to every client instead.
    """
    sys.path.insert(0, str(REPO / "src"))
    import carla_agentic_tools.server as server

    reported = _reported_version(server)
    assert reported == _pyproject_version(), \
        f"serverInfo.version is {reported!r}, expected {_pyproject_version()}"


# --- the npm package -------------------------------------------------------

def _npm_package() -> dict:
    import json
    return json.loads((REPO / "package.json").read_text())


def test_npm_version_matches_pyproject():
    """Two packages, one codebase: a user on npx and a user on uvx must be told
    the same version, and `serverInfo.version` is read from whichever they ran."""
    got = _npm_package()["version"]
    assert got == _pyproject_version(), (
        f"package.json says {got}, pyproject.toml says {_pyproject_version()}"
    )


def test_npm_ships_what_it_declares():
    """A file named in `files` but absent ships a package missing part of itself."""
    for name in _npm_package()["files"]:
        target = REPO / name.rstrip("/")
        assert target.exists(), f"package.json lists {name}, which is missing"


def test_npm_ships_the_skills_and_no_python():
    """The npm package must stand alone — that is the whole point of it.

    The skills are the product, so they travel in the tarball; and nothing in
    `files` may pull in the Python half, or `npx` users download a server they
    cannot run twice over.
    """
    files = _npm_package()["files"]
    assert "skills/" in files, "the skills must ship in the npm tarball"
    assert not any(f.startswith(("src/", "tests/")) for f in files), \
        "the Python implementation must not ship to npm"
    assert not _npm_package().get("dependencies"), \
        "a runtime dependency defeats the point: npx would install at first run"


def test_npm_entry_point_exists_and_is_executable():
    import os
    bin_rel = _npm_package()["bin"]["carla-agentic-tools"]
    entry = REPO / bin_rel
    assert entry.is_file(), f"{bin_rel} is missing"
    assert os.access(entry, os.X_OK), f"{bin_rel} is not executable"
    assert entry.read_text().startswith("#!"), "no shebang, so `npx` cannot exec it"
