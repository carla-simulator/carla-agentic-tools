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
├── pyproject.toml            # hatchling; maps skills/ into the wheel
├── npm/                      # npx front door -> uvx -> the PyPI package
├── src/carla_agentic_tools/
│   └── server.py             # MCP server: list_skills / read_skill / check_prerequisites
├── tests/                    # structural checks the release gates on
└── skills/
    ├── setup/                # get CARLA at all: download-carla, install-python-api
    ├── python-api/           # drives any running server (world-data, create-sensor, …)
    ├── ue4/                  # needs a UE4 checkout (build, package, run, import)
    └── ros2/                 # native ROS 2 interface (publishers, msg types, RViz)
```

**Starting from nothing?** Three skills, in order: `download-carla` (fetches a
release and prints the path), `install-python-api` (installs the client wheel from
inside that download, so versions cannot mismatch), `run-carla-server` (detects the
download and launches it). The `setup` group is never gated on an environment
variable, so it stays visible to a user who has no CARLA yet.

Skills are **auto-discovered**: any `skills/<group>/<name>/SKILL.md` is picked up,
no registration step. The **group** says what a skill binds to — `python-api`
works against any CARLA server regardless of engine version, while `ue4`/`ue5`
need that engine's checkout. `list_skills` reports the group and whether its
environment is present (`available: false` plus a reason when e.g.
`CARLA_UE4_ROOT` is unset); unavailable skills are still listed, because creating
that environment is often the task at hand.

## Install

Nothing to clone. Pick whichever front door suits the client:

```bash
# npx (Node available)
npx -y @carla-simulator/agentic-tools

# uvx (Python tooling; what the npx wrapper calls under the hood)
uvx carla-agentic-tools

# or a durable install
pipx install carla-agentic-tools
```

The npm package is a thin wrapper: it finds `uvx`/`uv`/`pipx` and execs the
Python server, pinning the *same* version, so `npx -y @carla-simulator/agentic-tools@0.2.0`
and `uvx carla-agentic-tools@0.2.0` are the same server. It never
`pip install`s into your environment, and it keeps stdout free for the MCP
stream (diagnostics go to stderr).

## Registering with an MCP client

Point the client at the command and pass the CARLA paths as env — no file is
written into your checkout, and one install drives any instance:

```json
{
  "mcpServers": {
    "carla": {
      "command": "npx",
      "args": ["-y", "@carla-simulator/agentic-tools"],
      "env": {
        "CARLA_UE4_ROOT": "/path/to/carla",
        "UE4_ROOT": "/path/to/UnrealEngine_4.26"
      }
    }
  }
}
```

Swap `command`/`args` for `uvx` + `["carla-agentic-tools"]` if you would rather
skip Node. Claude Code reads `.mcp.json` from the project directory; Cursor and
Claude Desktop take the same block in their own config.

The server exposes three tools: `list_skills` (optionally `group`-filtered),
`read_skill(name)`, `check_prerequisites(name)`.

## Developing on the skills

Work from a checkout when you are *writing* skills:

```bash
pip install -e .                  # server from source
pytest -q tests/                  # structural + MCP checks
CARLA_SKILLS_DIR=$PWD/skills uvx carla-agentic-tools   # installed server, live skills
```

`CARLA_SKILLS_DIR` points a published server at a working tree, so you can edit a
`SKILL.md` and re-run without reinstalling. `setup.sh` is the legacy convenience
path (editable install + `.mcp.json` written into a CARLA checkout) and is now
only for local development.

## Releasing

Bump the version in **both** `pyproject.toml` and `npm/package.json` (CI fails on
a mismatch, since the wrapper resolves its own version from PyPI), then:

```bash
git tag v0.2.0 && git push --tags
```

`.github/workflows/release.yml` publishes the wheel to PyPI via trusted
publishing and then the wrapper to npm — in that order, so the front door never
points at a version that does not exist yet.

## Targeting a CARLA instance

The skills operate on a real, built CARLA + UE4, chosen via two variables:

| Var | Meaning |
|---|---|
| `CARLA_TARGET` | **the simplest option**: any CARLA — an extracted release or a checkout. `run-carla-server` detects which and launches it accordingly |
| `CARLA_UE4_ROOT` | a carla source checkout (branch `ue4-dev`), needed by the build/package/import skills |
| `UE4_ROOT` | the built CarlaUnreal UE 4.26 fork — editor mode only |
| `PYTHON` | the interpreter that has the `carla` wheel. Set this whenever the server runs under `uvx`/`npx`, whose own python is first on PATH |
| `CARLA_HOST` / `CARLA_PORT` | where the simulator listens (default `127.0.0.1:2000`) |

No `carla` wheel yet? The `install-python-api` skill installs it from your release's
bundled wheel or from PyPI, and checks it matches the simulator's version.

Set them in the client's `env` block (above) or export them before launching —
a live export always wins. One install can therefore drive several checkouts:
give each client entry its own `env`. Future groups follow the same pattern
(`CARLA_UE5_ROOT`, `SCENARIO_RUNNER_ROOT`, `SCENIC_ROOT`), and `list_skills`
marks a group unavailable when its variable is unset.

`CARLA_UE4_ROOT` also auto-resolves to `$PWD` when a skill runs from inside a
checkout; `check_prerequisites` fails loudly, naming the paths it checked, when
either is missing or wrong. The legacy `setup.sh --carla … --ue4 …` bakes these
as defaults into a `.mcp.json` inside the checkout; that path still works but is
no longer needed to install.

## Running a skill directly (no server)

The scripts are runnable with plain bash — the server is only the discovery
layer:

```bash
cd skills/ue4/package-carla-ue4
export CARLA_UE4_ROOT=/path/to/your/carla
export UE4_ROOT=/path/to/your/UnrealEngine_4.26
# activate the python env whose python3 has `carla` + `build` first

bash scripts/check_env.sh                 # check prerequisites
PACKAGES=Town15 bash scripts/package.sh   # cook + package (see SKILL.md for knobs)
```

See `skills/ue4/package-carla-ue4/SKILL.md` and `references/packaging.md` for the
full procedure, knobs (`PACKAGE_DEST`, `CLEAN_INTERMEDIATE`, …), and gotchas.

## Adding a skill

Drop a new `skills/<group>/<name>/` directory containing at minimum a `SKILL.md`
(with `description:` and `metadata.group:` matching the directory) and, for
prerequisite checks, a `scripts/check_env.sh`. It is discovered automatically on
the next server start, and `pytest -q tests/` checks the invariants (frontmatter,
group, links, script syntax) that the release gates on.

Groups are directories: add `skills/ue5/` or `skills/scenic/` and register the
environment variable that gates it in `GROUP_REQUIREMENTS` (`server.py`).
`skills/ue4/package-carla-ue4` is the worked example to model a new skill on.

## License

MIT — see [LICENSE](LICENSE).
