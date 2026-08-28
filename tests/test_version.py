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
