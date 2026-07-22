"""carla-agentic-tools MCP server.

Skills-first design: capabilities live in ``skills/<name>/`` as a ``SKILL.md``
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

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# Repo root = three levels up from this file (src/carla_agentic_tools/server.py):
# server.py -> carla_agentic_tools -> src -> <repo root>. Skills are discovered
# under <repo root>/skills, so any skills/<name>/SKILL.md is picked up with no
# registration step.
REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO_ROOT / "skills"

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

mcp = FastMCP("carla-agentic-tools", instructions=SERVER_INSTRUCTIONS)


def _skill_dirs() -> list[Path]:
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file())


@mcp.tool()
def list_skills() -> list[dict]:
    """List the available CARLA skills as {name, description} entries.

    The library is the source of procedure for CARLA tasks — match a skill by
    its description and call read_skill(name), rather than improvising from the
    Makefile. One entry per skills/<name>/SKILL.md.
    """
    out: list[dict] = []
    for d in _skill_dirs():
        desc = ""
        for line in (d / "SKILL.md").read_text().splitlines():
            if line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
                break
        out.append({"name": d.name, "description": desc})
    return out


@mcp.tool()
def read_skill(name: str) -> str:
    """Return a skill's full SKILL.md — the step-by-step procedure and its gotchas.

    Call after list_skills once a skill matches the task, and read it before
    running the commands it describes. `name` is a name from list_skills.
    """
    skill = SKILLS_DIR / name / "SKILL.md"
    if not skill.is_file():
        raise ValueError(f"unknown skill {name!r}; see list_skills()")
    return skill.read_text()


@mcp.tool()
def check_prerequisites(name: str) -> str:
    """Run a skill's read-only prerequisite checks and return its PASS/WARN/FAIL report.

    Call before executing a skill to confirm the environment is ready — checks
    disk, tools, and whether UE4/CARLA are in place. Read-only; does not modify
    the system. `name` is a name from list_skills.
    """
    script = SKILLS_DIR / name / "scripts" / "check_env.sh"
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
