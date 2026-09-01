"""carla-agentic-tools MCP server.

Skills-first design: capabilities live in ``skills/<group>/<name>/`` as a ``SKILL.md``
plus executable scripts. This server exposes the skill registry over MCP so an
agent can discover skills, read their procedure, and check their prerequisites.
Mutating steps (a cook/package is a long, ~30GB operation) are intentionally NOT
auto-run here — the server surfaces the procedure and prerequisite checks, and
the agent/user drives execution deliberately.

This repo is standalone and targets a CARLA instance chosen at runtime: the
skills read CARLA_UE4_ROOT / UE4_ROOT from the environment (see the skill's
env.sh and README), so one install can drive any checkout.

Run:  carla-agentic-tools   (stdio transport)
"""
from __future__ import annotations

import inspect
import os
import subprocess
from pathlib import Path

# The MCP SDK renamed the high-level server class in 2.0 (FastMCP -> MCPServer)
# and dropped the old import path. Both expose the same surface used here
# (constructor kwargs, the .tool() decorator, .run() defaulting to stdio), so
# support either: a published package is installed fresh by `uvx`, which resolves
# the newest SDK, while existing checkouts still have 1.x.
try:  # mcp >= 2.0
    from mcp.server import MCPServer as _MCPServer
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _MCPServer

def _resolve_skills_dir() -> Path:
    """Locate the skill library, installed or in a checkout.

    Two layouts must both work, because the same code serves `uvx
    carla-agentic-tools` and a developer's `pip install -e .`:

      installed  <site-packages>/carla_agentic_tools/skills/   (wheel package data)
      checkout   <repo root>/skills/                           (source of truth)

    The in-package copy wins so an installed server never reads a stale sibling
    checkout. CARLA_SKILLS_DIR overrides both, for authoring against a working
    tree without reinstalling.
    """
    override = os.environ.get("CARLA_SKILLS_DIR")
    if override:
        return Path(override).expanduser().resolve()
    packaged = Path(__file__).resolve().parent / "skills"
    if packaged.is_dir():
        return packaged
    return Path(__file__).resolve().parents[2] / "skills"


SKILLS_DIR = _resolve_skills_dir()

# Which env var makes a group's skills usable. A group with no entry here (or an
# unset var) is still listed — it is annotated `available: false` rather than
# hidden, because the agent may be about to create that very environment (asking
# to build CARLA is the normal way CARLA_UE4_ROOT comes to exist).
# A group is satisfied when ANY of its variables is set: `ue4` covers both a
# source checkout and a downloaded release, because run-carla-server can serve
# either — the build/import skills inside it still fail loudly on their own if the
# source is missing, which is what check_prerequisites is for.
# `setup` is deliberately absent: download-carla and install-python-api are the
# bootstrap pair, and gating them on an existing CARLA would hide exactly the two
# skills a user with nothing needs.
GROUP_REQUIREMENTS = {
    "ue4": (("CARLA_UE4_ROOT", "CARLA_TARGET", "CARLA_PACKAGE_ROOT"),
            "a CARLA ue4-dev checkout or an extracted release"),
    # ue5 and ue58 are deliberately separate groups, not one engine-agnostic group:
    # they track different CARLA branches (ue5-dev / ue58-dev) against different
    # engine forks (ue5-dev-carla = UE 5.5, ue58-dev-carla = UE 5.8), and a skill
    # that names the wrong engine branch sends the user into a multi-hour build of
    # the wrong thing. If the branches converge later, merge the groups then.
    "ue5": (("CARLA_UE5_ROOT",), "a CARLA ue5-dev checkout (UE 5.5)"),
    "ue58": (("CARLA_UE58_ROOT",), "a CARLA ue58-dev checkout (UE 5.8)"),
    "scenario-runner": (("SCENARIO_RUNNER_ROOT",), "a scenario_runner checkout"),
    "leaderboard": (("LEADERBOARD_ROOT",), "a leaderboard checkout (plus its matching scenario_runner)"),
    "scenic": (("SCENIC_ROOT",), "a Scenic install"),
}

# The `instructions` field is returned in the MCP initialize handshake; clients
# MAY add it to the system prompt. It makes the skill library self-advertising in
# an agent-agnostic way — any MCP client gets the routing rule from the server
# alone, with no client-side configuration.
SERVER_INSTRUCTIONS = """\
CARLA build, packaging, cooking, map, vehicle, asset, and server/simulation
tasks have vetted procedures in this server's skill library, each with its
failure modes encoded. The skills are the source of truth for these tasks;
the raw Makefile and Util/BuildTools scripts are a fallback when none matches.
list_skills finds a skill, read_skill(name) returns its procedure,
check_prerequisites(name) verifies its environment.
"""

def _version() -> str:
    """Installed distribution version, or "" from a bare checkout."""
    try:
        from importlib.metadata import version

        return version("carla-agentic-tools")
    except Exception:
        return ""


# mcp 2.x reports serverInfo.version (clients show it, and it identifies which
# skill library a run used); 1.x has no such parameter, so pass it only when the
# constructor accepts it rather than branching on SDK version numbers.
_kwargs: dict = {"name": "carla-agentic-tools", "instructions": SERVER_INSTRUCTIONS}
if "version" in inspect.signature(_MCPServer.__init__).parameters:
    _kwargs["version"] = _version()
mcp = _MCPServer(**_kwargs)


def _skill_dirs() -> list[Path]:
    """Every skill directory, in either layout.

    Skills live in groups (`skills/<group>/<name>/SKILL.md`); the flat form
    (`skills/<name>/SKILL.md`) is still accepted so an ungrouped checkout or a
    user's own drop-in directory keeps working.
    """
    if not SKILLS_DIR.is_dir():
        return []
    found = {p.parent for p in SKILLS_DIR.glob("*/SKILL.md")}
    found |= {p.parent for p in SKILLS_DIR.glob("*/*/SKILL.md")}
    return sorted(found, key=lambda p: (p.parent.name, p.name))


def _group_of(d: Path) -> str:
    """The skill's group: its parent directory, or "" when stored flat."""
    return d.parent.name if d.parent != SKILLS_DIR else ""


def _group_available(group: str) -> tuple[bool, str]:
    vars_, what = GROUP_REQUIREMENTS.get(group, ((), ""))
    if not vars_:
        return True, ""
    if any(os.environ.get(v) for v in vars_):
        return True, ""
    return False, f"none of {'/'.join(vars_)} is set (needs {what})"


def _find_skill(name: str) -> Path | None:
    for d in _skill_dirs():
        if d.name == name:
            return d
    return None


@mcp.tool()
def list_skills(group: str | None = None) -> list[dict]:
    """List the available CARLA skills as {name, group, description, available} entries.

    The library is the source of procedure for CARLA tasks — match a skill by
    its description and call read_skill(name), rather than improvising from the
    Makefile.

    Groups say what a skill binds to: `python-api` drives any running server,
    `ue4`/`ue5` need that engine's checkout, `ros2` covers the native ROS 2
    interface. `available: false` means the group's environment variable is not
    set yet (see `unavailable_reason`) — the skill is still listed, because
    building or checking out that environment is itself a valid next step.
    Pass `group` to list one group only.
    """
    out: list[dict] = []
    for d in _skill_dirs():
        g = _group_of(d)
        if group is not None and g != group:
            continue
        desc = ""
        for line in (d / "SKILL.md").read_text().splitlines():
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
                break
        ok, why = _group_available(g)
        entry = {"name": d.name, "group": g, "description": desc, "available": ok}
        if why:
            entry["unavailable_reason"] = why
        out.append(entry)
    return out


@mcp.tool()
def read_skill(name: str) -> str:
    """Return a skill's full SKILL.md — the step-by-step procedure and its gotchas.

    Call after list_skills once a skill matches the task, and read it before
    running the commands it describes. `name` is a name from list_skills.
    """
    d = _find_skill(name)
    if d is None:
        raise ValueError(f"unknown skill {name!r}; see list_skills()")
    return (d / "SKILL.md").read_text()


@mcp.tool()
def check_prerequisites(name: str) -> str:
    """Run a skill's read-only prerequisite checks and return its PASS/WARN/FAIL report.

    Call before executing a skill to confirm the environment is ready — checks
    disk, tools, and whether UE4/CARLA are in place. Read-only; does not modify
    the system. `name` is a name from list_skills.
    """
    d = _find_skill(name)
    if d is None:
        raise ValueError(f"unknown skill {name!r}; see list_skills()")
    script = d / "scripts" / "check_env.sh"
    if not script.is_file():
        raise ValueError(f"skill {name!r} has no prerequisite checks (scripts/check_env.sh)")
    proc = subprocess.run(
        ["bash", str(script)],
        capture_output=True, text=True, timeout=120,
    )
    return f"exit={proc.returncode}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"


def main() -> None:
    """Console-script entrypoint: serve over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
