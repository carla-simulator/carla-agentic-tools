# carla-agentic-tools

A library of **vetted CARLA procedures** ("skills") for any agent. Each skill is
a `SKILL.md` plus executable scripts with its failure modes encoded, so an agent
discovers the right procedure and checks its prerequisites instead of improvising
from the Makefile.

Nothing in a skill is client-specific — plain Markdown and POSIX shell. A
standalone [MCP](https://modelcontextprotocol.io) server serves them to any MCP
client, and ships **twice**: on npm as a self-contained Node package, and on
PyPI as a Python one. Same skills, same answers, no wrapper between them —
`tests/test_node_parity.py` runs both and diffs what they return.

This repo is independent of any CARLA checkout: it targets a **specific CARLA
instance at runtime**, recorded on first use, so one install can drive any build.

## Layout

```
carla-agentic-tools/
├── pyproject.toml            # hatchling; maps skills/ into the wheel
├── package.json              # the npm package; ships bin/ lib/ skills/
├── bin/carla-agentic-tools.js # npx entry point
├── lib/                      # the Node server: server.js, skills.js, config.js
│                             #   zero dependencies, Node >= 12
├── src/carla_agentic_tools/  # the Python server: server.py, config.py
├── test/node_smoke.js        # `npm test`
├── tests/                    # pytest, including the Node/Python parity checks
├── upload.sh                 # publishes both, one confirmation each
└── skills/
    ├── _common/env_common.sh # every env.sh loads the recorded paths through this
    ├── setup/                # get the pieces at all: download-carla, install-python-api,
    │                         #   install-scenario-runner, install-leaderboard
    ├── python-api/           # drives any running server (world-data, create-sensor, …)
    ├── ue4/                  # needs a UE4 checkout (build, package, run, import)
    ├── ros2/                 # native ROS 2 interface (publishers, msg types, RViz)
    ├── scenario-runner/      # CARLA's scenario engine (scenarios, OpenSCENARIO, routes)
    └── leaderboard/          # the AD Leaderboard on top of it (agents, evaluation, scoring)
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

## Two servers, one library

The skills, and everything that decides which are usable, exist in both
languages. Which one you install decides only what has to be on the machine:

| | needs | get it with |
|---|---|---|
| **npm** | Node >= 12, nothing else | `npx -y @carla-simulator/agentic-tools` |
| **PyPI** | Python >= 3.10 | `uvx carla-agentic-tools` |

The npm package carries the skills in its own tarball and has **no runtime
dependencies** — no Python, no `uv`, no install step at first run. The Python
package is the same thing for people whose tooling is already Python.

The skills themselves still shell out to `bash`, and the ones that drive the
CARLA client need an interpreter with the `carla` wheel — that is the `PYTHON`
key, part of the user's environment rather than the server's runtime. Building
CARLA needs a CARLA checkout either way.

Both read and write the same config file, so a path recorded through one is
visible to the other.

## Install

```bash
# npm — no Python needed
npx -y @carla-simulator/agentic-tools

# PyPI — if your tooling is already Python
uvx carla-agentic-tools
pipx install carla-agentic-tools     # or a durable install
```

Both are the same server at the same version. Pick whichever runtime you already
have; the section above says what each needs.

Diagnostics go to stderr and stdio is inherited, never piped, so stdout stays a
clean MCP stream and the client talks to the server directly.

## Registering with an MCP client

Point the client at the command. **No paths go here** — you would have to know
them before the skills that create them have run:

```json
{
  "mcpServers": {
    "carla": {
      "command": "npx",
      "args": ["-y", "@carla-simulator/agentic-tools"]
    }
  }
}
```

Swap `command`/`args` for `uvx` + `["carla-agentic-tools"]` for the Python
package instead. Claude Code reads `.mcp.json` from the project directory; Cursor and
Claude Desktop take the same block in their own config. The CLI equivalent:

```bash
claude mcp add carla -s user -- carla-agentic-tools
```

Five tools: `list_skills` (optionally `group`-filtered), `read_skill(name)`,
`check_prerequisites(name)`, `get_config()`, `set_config(paths)`.

## Paths, and when you are asked for them

Nothing is configured up front. `list_skills` on a bare machine already returns
the `setup` group (download CARLA, install the Python API) and `python-api`
(drives any running server) as available; everything else is listed with
`available: false` and a reason, because obtaining the missing piece is usually
the task at hand.

A path is asked for the first time a skill needs one it does not have.
`check_prerequisites` reports it as a `needs` block naming the key, the skill
that would obtain it, and every candidate found on the machine **with its flavor
and branch** — several CARLA checkouts side by side is normal, and picking the
wrong one fails slowly. The agent asks; `set_config` records the answer.

`CARLA_ROOT` is the only CARLA path anyone is asked for. `set_config` inspects
the directory and writes the engine-specific variable itself:

```
set_config({"CARLA_ROOT": "/home/me/carla"})
  CARLA_ROOT is source, ue58, branch ue58-dev; also set CARLA_UE58_ROOT
```

That is what gates the `ue58` group — the flavor comes from structural markers in
the tree, not from which of the five variable names you happened to set.

Resolution order for every key, highest first:

| # | source | for |
|---|---|---|
| 1 | an exported environment variable | a one-off override, CI |
| 2 | `./.carla-tools.env` | a repo carrying its own CARLA |
| 3 | `${XDG_CONFIG_HOME:-~/.config}/carla-agentic-tools/config.env` | the normal case |
| 4 | each `env.sh`'s own search list | last resort |

The config outranks the search lists deliberately: once the user has confirmed
which checkout to use, detection must not silently pick the other one. Override
the file's location with `CARLA_TOOLS_CONFIG`. It is `KEY=value` lines, parsed
rather than sourced, so nothing in it can execute.

The install skills record what they created, so a group flips to `available:
true` right after the install that enabled it, and stays that way next session.

## Developing on the skills

Work from a checkout when you are *writing* skills:

```bash
pip install -e .                       # the Python server from source
pytest -q tests/                       # structural + MCP + Node/Python parity
node test/node_smoke.js                # the Node server (also `npm test`)
CARLA_SKILLS_DIR=$PWD/skills uvx carla-agentic-tools   # a published server, live skills
```

`CARLA_SKILLS_DIR` points either server at a working tree, so you can edit a
`SKILL.md` and re-run without reinstalling.

Change how a skill is *selected* — the gating, the config keys, the detection
markers — and you are editing two implementations. `tests/test_node_parity.py`
runs both servers over stdio and diffs every answer, so a change made on one
side only fails there rather than reaching a user.

## Releasing

```bash
bash upload.sh --check     # preflight and build, publish nothing
bash upload.sh             # then confirm PyPI and npm separately
```

The version lives in `pyproject.toml`, `src/carla_agentic_tools/__init__.py` and
`package.json`; `tests/test_version.py` fails on drift and `upload.sh` refuses to
run. Neither index replaces a published version, and npm only allows unpublish
within 72 hours, so each publish asks for a literal `yes`.

## Targeting a CARLA instance

One install drives any CARLA. These are the keys the skills read; see **Paths,
and when you are asked for them** above for how they get set — in normal use you
answer a prompt and never type a variable name.

Asked for, when a skill needs one:

| Key | Meaning |
|---|---|
| `CARLA_ROOT` | **the only CARLA path you are asked for**: a release or a source checkout. Its flavor is detected and the engine variable below is written for you |
| `PYTHON` | the interpreter that has the `carla` wheel. Needed whenever the server runs under `uvx`/`npx`, whose own python is first on PATH |
| `SCENARIO_RUNNER_ROOT` | a scenario_runner checkout — gates the `scenario-runner` group |
| `LEADERBOARD_ROOT` | a leaderboard checkout — gates the `leaderboard` group |
| `SCENIC_ROOT` | a Scenic checkout or installed package — gates the `scenic` group |
| `CARLA_UNREAL_ENGINE_PATH` | the Unreal Engine fork CARLA builds against |

Derived from `CARLA_ROOT`, or set by hand to override:

| Key | Written when `CARLA_ROOT` is |
|---|---|
| `CARLA_UE4_ROOT` | a `ue4-dev` checkout (`Unreal/CarlaUE4/CarlaUE4.uproject`) |
| `CARLA_UE5_ROOT` | a `ue5-dev` checkout (`CMakePresets.json` + `Unreal/CarlaUnreal`) |
| `CARLA_UE58_ROOT` | as above, plus the Autoware plugin and `CMake/DLSS.cmake` |
| `CARLA_PACKAGE_ROOT`, `CARLA_TARGET` | an extracted release (a `CarlaUE4.sh` at the top) |

Defaults, rarely touched: `CARLA_HOST` / `CARLA_PORT` (`127.0.0.1:2000`),
`CARLA_TM_PORT` (`8000`), `CARLA_TIMEOUT`, `CARLA_PRESET`, `ROS_DOMAIN_ID`.

No `carla` wheel yet? The `install-python-api` skill installs it from your
release's bundled wheel or from PyPI, checks it matches the simulator, and
records `PYTHON`.

One install can still drive several checkouts: give a repo its own
`./.carla-tools.env`, or export a variable for a single run — an export always
wins over the config.

**Version pairing matters** for the scenario-runner and leaderboard groups: a
scenario_runner branch belongs to a CARLA version, and a leaderboard version
belongs to a scenario_runner branch. The two installer skills derive the pairing
and every `check_env.sh` in those groups fails loudly on a mismatch, because the
symptom otherwise is scenarios that silently never trigger.

Paths also auto-resolve to `$PWD` when a skill runs from inside the relevant
checkout, and `check_prerequisites` fails loudly, naming what it checked, when
something is missing or wrong. That search is the last resort, below the config:
a recorded answer is never silently overridden by a guess.

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
prerequisite checks, a `scripts/check_env.sh`. The MCP server discovers it on the
next start.

`pytest -q tests/` checks the invariants (frontmatter, group, links, script
syntax) the release gates on.

Body prose must reach `scripts/` and `references/` by **absolute** path: the
agent's working directory is the user's project, not the skill directory. Each
`SKILL.md` opens with a `> **Paths.**` note saying so, and `read_skill` prefixes
its output with the skill's absolute directory. A new skill also needs its
`scripts/env.sh` to source `skills/_common/env_common.sh`, or it cannot see the
paths the user recorded — `tests/test_config.py` fails when one does not.

Groups are directories: add `skills/ue5/` or `skills/scenic/` and register the
variable that gates it in `GROUP_REQUIREMENTS` — in **both** `src/carla_agentic_tools/server.py`
and `lib/skills.js`, or the two servers disagree about what is usable.
`tests/test_node_parity.py` fails when they do.
`skills/ue4/package-carla-ue4` is the worked example to model a new skill on.

## License

MIT — see [LICENSE](LICENSE).
