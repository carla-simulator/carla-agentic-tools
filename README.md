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
    ├── ue5/                  # what UE 5.5 cannot do that 5.8 can
    ├── ue58/                 # needs a UE 5.8 checkout (build, package, run, import, Autoware)
    ├── ros2/                 # native ROS 2 interface (publishers, msg types, RViz)
    ├── scenario-runner/      # CARLA's scenario engine (scenarios, OpenSCENARIO, routes)
    ├── leaderboard/          # the AD Leaderboard on top of it (agents, evaluation, scoring)
    └── scenic/               # probabilistic scenarios (write and run .scenic)
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

### Which CARLA each group is about

The group names are engine branches, not release numbers, because one release
number spans two of them:

| Group | Branch | CARLA |
|---|---|---|
| `ue4` | `ue4-dev` | 0.9.x, through 0.9.16 |
| `ue5` | `ue5-dev` | the UE5 line at UE 5.5 — an earlier revision, reports `0.10.0` |
| `ue58` | `ue58-dev` | the same line at UE 5.8 — **CARLA 1.0** |

`ue5-dev` and `ue58-dev` are one line, not parallel products, so the `ue58`
skills are the procedures for 5.5 too, minus five gaps that
[`check-ue5-limitations`](skills/ue5/check-ue5-limitations/SKILL.md) enumerates.
Pre-1.0 builds of `ue58-dev` report `0.10.0`, and that is the version string most
measurements in this repo were taken against — where a skill says `0.10.0`, read
it as naming the UE5 line unless it is quoting a specific build.

`python-api`, `scenario-runner`, `leaderboard`, `scenic` and `ros2` are not tied
to an engine: they bind to a running server, a checkout of the companion repo, or
CARLA's native ROS 2 sources.

## Two servers, one library

The skills, and everything that decides which are usable, exist in both
languages. Which one you pick decides only what has to be on the machine:

| | needs | runner |
|---|---|---|
| **npm** | Node >= 12, nothing else | `npx` |
| **PyPI** | Python >= 3.10 | `uvx` |

The npm package carries the skills in its own tarball and has **no runtime
dependencies** — no Python, no `uv`, no build step at first run. The Python
package is the same thing for people whose tooling is already Python. Both are
the same server at the same version, so pick whichever runtime you already have.

The skills themselves still shell out to `bash`, and the ones that drive the
CARLA client need an interpreter with the `carla` wheel — that is the `PYTHON`
key, part of the user's environment rather than the server's runtime. Building
CARLA needs a CARLA checkout either way.

Both read and write the same config file, so a path recorded through one is
visible to the other.

## Install

**There is usually nothing to install.** An MCP client starts a server by
running a command, and both packages ship an on-demand runner, so the command
you register *is* the install:

```bash
npx -y @carla-simulator/agentic-tools   # npm
uvx carla-agentic-tools                 # PyPI
```

Run either in a terminal to check it before wiring it into a client. A healthy
start is **silent** — it says nothing on either stream and blocks waiting for
MCP traffic on stdin, so a process that just sits there is the success case, and
Ctrl-C ends it. To see it actually answer, hand it a handshake:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"c","version":"1"}}}' \
  | npx -y @carla-simulator/agentic-tools
```

which replies with the server name, the version you resolved, and the
instructions the client will load.

The first launch downloads the package and starts it. Later launches re-resolve
the version, so a release published upstream arrives on its own — nobody
reinstalls anything. That resolution is the runner's behaviour, not the client's:
no agent is tracking versions on your behalf, and the client only ever re-runs
the string it was given.

Diagnostics go to stderr and stdio is inherited, never piped, so stdout stays a
clean MCP stream and the client talks to the server directly.

### Following latest, or pinning

Tracking latest is usually right for a skill library that is still growing, but
the version is part of the command, so changing that behaviour is an args edit
and needs no reinstall:

| args | effect |
|---|---|
| `-y @carla-simulator/agentic-tools` | latest, re-resolved at each launch |
| `-y @carla-simulator/agentic-tools@<version>` | frozen at one version |
| `-y @carla-simulator/agentic-tools@latest` | forces past a stale `npx` cache |

For `uvx` the same three are `carla-agentic-tools`, `carla-agentic-tools@<version>`,
and `uvx --refresh carla-agentic-tools`. The middle row is what to use when a
result has to be reproducible later; the last is worth knowing because `npx` can
serve a cached copy after a new release, and a user stuck on an old version is
almost always looking at that.

### A durable install instead

Installing the package outright puts a `carla-agentic-tools` executable on
`PATH`, and the client then launches that with no network access and no
resolution step:

```bash
npm install -g @carla-simulator/agentic-tools   # npm
pipx install carla-agentic-tools                # PyPI
```

Register it as `command: "carla-agentic-tools"` with empty `args`. Upgrades
become explicit (`npm update -g @carla-simulator/agentic-tools`, `pipx upgrade
carla-agentic-tools`), which is the point: this is the shape for offline and
air-gapped machines, for CI, and for anywhere a pinned version matters more than
getting new skills as they land.

## Registering with an MCP client

The server is ordinary stdio MCP with nothing client-specific in it, so any MCP
client can run it. Most take the same block — Claude Code (`.mcp.json` beside
your project, or `~/.claude.json`), Claude Desktop, Cursor (`~/.cursor/mcp.json`),
Windsurf (`~/.codeium/windsurf/mcp_config.json`), Gemini CLI
(`~/.gemini/settings.json`):

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

Swap `command`/`args` for `uvx` + `["carla-agentic-tools"]` to run the Python
package instead. **No paths go here** — you would have to know them before the
skills that create them have run.

Two clients want a different shape for the same server:

- **VS Code** (`.vscode/mcp.json`, or the user `mcp.json`) uses `servers`, not
  `mcpServers`, and wants an explicit `"type": "stdio"`. A block copied from
  above is ignored with no error, which is the most common setup mistake.
- **Codex** uses TOML in `~/.codex/config.toml`:

  ```toml
  [mcp_servers.carla]
  command = "npx"
  args = ["-y", "@carla-simulator/agentic-tools"]
  ```

Clients with a CLI will write that entry for you:

```bash
claude mcp add carla -s user -- npx -y @carla-simulator/agentic-tools
codex mcp add carla -- npx -y @carla-simulator/agentic-tools
gemini mcp add -s user carla npx -- -y @carla-simulator/agentic-tools
code --add-mcp '{"name":"carla","command":"npx","args":["-y","@carla-simulator/agentic-tools"]}'
```

Each of these only records the entry — nothing is fetched until the client first
starts the server. Note where the `--` falls: for `claude` and `codex` it
separates the whole server command from the client's own flags, while `gemini`
takes the command as a positional and needs the `--` after it so npx's `-y` is
not read as a flag for `gemini` itself.

Five tools, whatever the client: `list_skills` (optionally `group`-filtered),
`read_skill(name)`, `check_prerequisites(name)`, `get_config()`,
`set_config(paths)`.

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
