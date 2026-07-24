# carla-agentic-tools

A standalone [MCP](https://modelcontextprotocol.io) server that exposes a
library of **vetted CARLA procedures** ("skills") to any MCP client. Each skill
is a `SKILL.md` plus executable scripts with its failure modes encoded, so an
agent discovers the right procedure and checks its prerequisites instead of
improvising from the Makefile.

This repo is independent of any CARLA checkout: it targets a **specific CARLA
instance at runtime** via environment variables, so one install can drive any
build.

## Layout

```
carla-agentic-tools/
├── pyproject.toml
├── src/carla_agentic_tools/
│   ├── __init__.py
│   └── server.py            # MCP server: list_skills / read_skill / check_prerequisites
└── skills/
    └── package-carla-ue4/   # a skill: SKILL.md + references/ + scripts/
```

Skills are **auto-discovered** at runtime: any `skills/<name>/SKILL.md` is
picked up — no registration step. Discovery is computed relative to
`server.py` (`<repo root>/skills`).

## Install

Run `setup.sh`, pointing it at the CARLA instance you want to drive:

```bash
bash setup.sh --carla /path/to/your/carla --ue4 /path/to/your/UnrealEngine_4.26
```

It installs the server (`pip install -e .`) into the active Python, verifies the
tools and skill discovery, then writes an `.mcp.json` **into the CARLA checkout**
so any MCP client run from there auto-detects the server (the entry is merged in;
other servers already there are preserved). `--carla` may be omitted if `CARLA_UE4_ROOT`
is exported; `--ue4` likewise falls back to `$UE4_ROOT`. Pick the interpreter with
`PYTHON=python3.11 bash setup.sh …`.

Requires Python ≥ 3.10 and `mcp>=1.2.0` (pulled in automatically). The baked
`CARLA_UE4_ROOT` / `UE4_ROOT` are defaults only — a live export of either wins at
launch. Remove everything with:

```bash
bash setup.sh --uninstall --carla /path/to/your/carla
```

This drops the server entry from the checkout's `.mcp.json` and pip-uninstalls
the package.

## Registering with an MCP client

`setup.sh` writes the registration for you: an `.mcp.json` inside the CARLA
checkout that Claude Code and most MCP clients auto-detect when launched from
there. Nothing else to configure — start the client in the checkout and approve
the `carla-agentic-tools` server. It then exposes three tools: `list_skills`,
`read_skill(name)`, `check_prerequisites(name)`.

The generated entry looks like this (paths come from your `--carla`/`--ue4`):

```json
{
  "mcpServers": {
    "carla-agentic-tools": {
      "type": "stdio",
      "command": "/usr/bin/python3",
      "args": ["-m", "carla_agentic_tools.server"],
      "env": {
        "CARLA_UE4_ROOT": "${CARLA_UE4_ROOT:-/path/to/your/carla}",
        "UE4_ROOT": "${UE4_ROOT:-/path/to/your/UnrealEngine_4.26}"
      }
    }
  }
}
```

For detection from any directory (Claude Code user scope) instead of only the
checkout, run `claude mcp add carla-agentic-tools --scope user -- <python> -m
carla_agentic_tools.server` (setup.sh prints the exact line).

## Targeting a CARLA instance

The skills operate on a real, built CARLA + UE4, chosen via two variables:

| Var | Meaning | Setup flag |
|---|---|---|
| `CARLA_UE4_ROOT` | the carla source checkout (branch `ue4-dev`) to build/package | `--carla` |
| `UE4_ROOT` | the built CarlaUnreal UE 4.26 fork | `--ue4` |

Point setup at a specific instance with the flags:

```bash
bash setup.sh --carla /path/to/your/carla --ue4 /path/to/your/UnrealEngine_4.26
```

Each flag is **baked as a default** into the generated `.mcp.json`
(`${VAR:-<baked>}`), so the server starts already targeting that instance. A
flag falls back to the same-named variable exported when you run setup, and at
launch a live export still wins over the baked default — so you can override
per-run without re-running setup. To retarget permanently, re-run setup with new
flags. `CARLA_UE4_ROOT` also auto-resolves to `$PWD` when a skill runs from
inside a checkout; `check_prerequisites` fails loudly, naming the paths it
checked, when either is missing or wrong.

## Running a skill directly (no server)

The scripts are runnable with plain bash — the server is only the discovery
layer:

```bash
cd skills/package-carla-ue4
export CARLA_UE4_ROOT=/path/to/your/carla
export UE4_ROOT=/path/to/your/UnrealEngine_4.26
# activate the python env whose python3 has `carla` + `build` first

bash scripts/check_env.sh                 # check prerequisites
PACKAGES=Town15 bash scripts/package.sh   # cook + package (see SKILL.md for knobs)
```

See `skills/package-carla-ue4/SKILL.md` and `references/packaging.md` for the
full procedure, knobs (`PACKAGE_DEST`, `CLEAN_INTERMEDIATE`, …), and gotchas.

## Adding a skill

Drop a new `skills/<name>/` directory containing at minimum a `SKILL.md` (with a
`description:` line) and, for prerequisite checks, a `scripts/check_env.sh`. It is
discovered automatically on the next server start. `package-carla-ue4` is the
worked example to model a new skill on.

## License

MIT — see [LICENSE](LICENSE).
