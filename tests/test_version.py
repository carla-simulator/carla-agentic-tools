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
