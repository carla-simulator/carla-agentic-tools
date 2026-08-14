"""Structural tests for the skill library and the MCP surface.

These guard the invariants a published package must not break: every skill is
discoverable, its frontmatter is complete, its group matches where it lives, its
in-repo links resolve, and its scripts parse. Run with `pytest -q`.

Deliberately no CARLA/UE4 required — these are static checks plus the three MCP
tools against the local tree, so they run in CI on a bare runner.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
GROUPS = {"setup", "python-api", "ue4", "ue5", "ros2", "scenario-runner", "scenic"}

sys.path.insert(0, str(REPO / "src"))


def skill_dirs() -> list[Path]:
    return sorted(p.parent for p in SKILLS.glob("*/*/SKILL.md"))


def frontmatter(skill: Path) -> str:
    text = (skill / "SKILL.md").read_text()
    assert text.startswith("---\n"), f"{skill.name}: no YAML frontmatter"
    return text.split("---", 2)[1]


def test_library_is_not_empty():
    assert skill_dirs(), "no skills discovered under skills/<group>/<name>/"


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_frontmatter_is_complete(skill: Path):
    fm = frontmatter(skill)
    name = re.search(r"^name:\s*(\S+)", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    assert name, f"{skill.name}: missing name"
    assert desc, f"{skill.name}: missing description"
    # The router only ever sees name + description, so a stub description makes a
    # skill unreachable however good its body is.
    assert len(desc.group(1)) >= 40, f"{skill.name}: description too short to route on"
    assert name.group(1) == skill.name, f"{skill.name}: name != directory"


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_group_matches_directory(skill: Path):
    group = skill.parent.name
    assert group in GROUPS, f"{skill.name}: unknown group directory {group!r}"
    declared = re.search(r"^\s+group:\s*(\S+)", frontmatter(skill), re.M)
    assert declared, f"{skill.name}: no metadata.group"
    assert declared.group(1) == group, (
        f"{skill.name}: metadata.group={declared.group(1)!r} but lives in {group!r}"
    )


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_relative_links_resolve(skill: Path):
    """Every markdown link to a repo path must exist (anchors stripped)."""
    body = (skill / "SKILL.md").read_text()
    for target in re.findall(r"\]\((references/[^)]+|scripts/[^)]+|\.\./[^)]+)\)", body):
        path = (skill / target.split("#", 1)[0]).resolve()
        assert path.exists(), f"{skill.name}: dead link -> {target}"


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_declared_prerequisites_exist(skill: Path):
    m = re.search(r"^\s+prerequisites:\s*(\S+)", frontmatter(skill), re.M)
    if not m:
        return
    assert (skill / m.group(1)).is_file(), f"{skill.name}: prerequisites path missing"


@pytest.mark.parametrize("skill", skill_dirs(), ids=lambda p: p.name)
def test_scripts_parse(skill: Path):
    """Shell scripts pass `bash -n`; Python scripts parse. Catches broken edits."""
    for script in sorted((skill / "scripts").glob("*")) if (skill / "scripts").is_dir() else []:
        if script.suffix == ".sh":
            r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
            assert r.returncode == 0, f"{script}: {r.stderr}"
        elif script.suffix == ".py":
            ast.parse(script.read_text())


def test_skill_names_are_unique():
    names = [d.name for d in skill_dirs()]
    dupes = {n for n in names if names.count(n) > 1}
    assert not dupes, f"duplicate skill names across groups: {dupes}"


def test_no_scratch_files_in_library():
    junk = [p for p in SKILLS.rglob("*")
            if p.is_file() and (p.suffix in {".pyc", ".log", ".orig"} or "__pycache__" in p.parts)]
    assert not junk, f"scratch files would ship in the wheel: {junk[:5]}"


# --- MCP surface -------------------------------------------------------------

def test_mcp_tools_work_against_the_tree(monkeypatch):
    monkeypatch.setenv("CARLA_SKILLS_DIR", str(SKILLS))
    for mod in [m for m in list(sys.modules) if m.startswith("carla_agentic_tools")]:
        del sys.modules[mod]
    import carla_agentic_tools.server as server

    listed = server.list_skills()
    assert len(listed) == len(skill_dirs())
    assert {e["group"] for e in listed} <= GROUPS
    assert all(e["description"] for e in listed)

    one = listed[0]["name"]
    assert server.read_skill(one).startswith("---")
    with pytest.raises(ValueError):
        server.read_skill("no-such-skill")

    # A group gated on an env var is listed but flagged, never hidden.
    monkeypatch.delenv("CARLA_UE4_ROOT", raising=False)
    for mod in [m for m in list(sys.modules) if m.startswith("carla_agentic_tools")]:
        del sys.modules[mod]
    import carla_agentic_tools.server as server2

    ue4 = [e for e in server2.list_skills(group="ue4")]
    assert ue4, "ue4 group vanished when CARLA_UE4_ROOT was unset"
    assert all(e["available"] is False and "CARLA_UE4_ROOT" in e["unavailable_reason"] for e in ue4)
