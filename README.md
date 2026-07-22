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

```bash
pip install -e .        # editable install from a checkout (keeps skills/ resolvable)
```

Requires Python ≥ 3.10 and `mcp>=1.2.0` (pulled in automatically). The console
script `carla-agentic-tools` serves over stdio.

## Register with an MCP client

```json
{
  "mcpServers": {
    "carla-agentic-tools": {
      "command": "carla-agentic-tools",
      "env": {
        "CARLA_UE4_ROOT": "/path/to/your/carla",
        "UE4_ROOT": "/path/to/your/UnrealEngine_4.26"
      }
    }
  }
}
```

The client then sees three tools: `list_skills`, `read_skill(name)`,
`check_prerequisites(name)`.

## Targeting a CARLA instance

The skills operate on a real, built CARLA + UE4. Point them at the instance you
want with two environment variables:

| Var | Meaning |
|---|---|
| `CARLA_UE4_ROOT` | the carla source checkout (branch `ue4-dev`) to build/package |
| `UE4_ROOT` | the built CarlaUnreal UE 4.26 fork |

`CARLA_UE4_ROOT` also auto-resolves to `$PWD` when you run a skill from within a
checkout; otherwise export it. `check_prerequisites` fails loudly, naming the
paths it checked, when either is missing or wrong.

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
discovered automatically on the next server start.

For how to structure and write one, see the [`author-carla-skill`](skills/author-carla-skill/SKILL.md)
skill: the repo's [layout and conventions](skills/author-carla-skill/references/conventions.md)
and copy-paste templates
([SKILL.md](skills/author-carla-skill/assets/SKILL.template.md),
[env.sh](skills/author-carla-skill/assets/env.sh.template),
[check_env.sh](skills/author-carla-skill/assets/check_env.sh.template)).
`package-carla-ue4` is the worked example.

## License

MIT — see [LICENSE](LICENSE).
