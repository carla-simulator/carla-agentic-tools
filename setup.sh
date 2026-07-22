#!/usr/bin/env bash
# setup.sh — prepare carla-agentic-tools so MCP-capable agents auto-detect it.
#
# What it does, idempotently:
#   1. Installs the MCP server into the active system Python (`pip install -e .`).
#   2. Verifies tools are registered and skills are auto-discovered.
#   3. Writes .mcp.json into the CARLA checkout — the config file Claude Code and
#      most MCP clients auto-detect for a project — invoking the server as
#      `<python> -m carla_agentic_tools.server`, pinned to the absolute
#      interpreter path so detection never depends on PATH or a console-script
#      shebang. The entry is merged in; any other servers there are preserved.
#
# The CARLA *skill* uses whatever python has `carla`+`build` at run time — a
# separate env chosen when a skill runs, unaffected by which python serves MCP.
#
# Usage:
#   bash setup.sh --carla /path/to/carla --ue4 /path/to/UnrealEngine_4.26
#   bash setup.sh --uninstall [--carla /path/to/carla]
#   PYTHON=python3.11 bash setup.sh ...    # pick the interpreter
#
# Options:
#   --carla PATH   CARLA checkout to make detectable; baked as CARLA_UE4_ROOT default.
#                  Falls back to $CARLA_UE4_ROOT. Required to install.
#   --ue4   PATH   built CarlaUnreal UE4; baked as UE4_ROOT default (else $UE4_ROOT).
#   --uninstall    remove the server entry from the CARLA checkout's .mcp.json and
#                  pip-uninstall the package. Undoes everything this script did.
# A live export of the same var still wins over the baked default at launch.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVER_NAME="carla-agentic-tools"

log()  { printf '\033[1;36m[setup]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[setup]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[setup] error:\033[0m %s\n' "$*" >&2; exit 1; }

# --- 0. Parse args ----------------------------------------------------------
CARLA_ARG=""
UE4_ARG=""
UNINSTALL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --carla)     CARLA_ARG="${2:?--carla needs a path}"; shift 2 ;;
    --ue4)       UE4_ARG="${2:?--ue4 needs a path}"; shift 2 ;;
    --uninstall) UNINSTALL=1; shift ;;
    *)           die "unknown argument: $1" ;;
  esac
done

carla_default="${CARLA_ARG:-${CARLA_UE4_ROOT:-}}"
ue4_default="${UE4_ARG:-${UE4_ROOT:-}}"

# --- 1. Resolve a Python >= 3.10 --------------------------------------------
PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || die "python interpreter '$PYTHON' not found (set PYTHON=...)"
"$PYTHON" - <<'PY' || die "need Python >= 3.10 (got an older one); set PYTHON=python3.x"
import sys
raise SystemExit(0 if sys.version_info[:2] >= (3, 10) else 1)
PY
PYEXE="$("$PYTHON" -c 'import sys; print(sys.executable)')"

# Remove the server entry from the .mcp.json at $1, preserving other servers;
# delete the file if it held nothing but our entry.
remove_mcp_entry() {
  MCP_TARGET="$1" MCP_NAME="$SERVER_NAME" "$PYEXE" - <<'PY'
import json, os, pathlib
target = pathlib.Path(os.environ["MCP_TARGET"])
name = os.environ["MCP_NAME"]
if not target.is_file():
    raise SystemExit(0)
try:
    data = json.loads(target.read_text())
except Exception:
    raise SystemExit(0)
servers = data.get("mcpServers") if isinstance(data, dict) else None
if not isinstance(servers, dict) or name not in servers:
    raise SystemExit(0)
del servers[name]
if not servers and list(data.keys()) == ["mcpServers"]:
    target.unlink()
else:
    target.write_text(json.dumps(data, indent=2) + "\n")
PY
}

# --- Uninstall path ---------------------------------------------------------
if [ -n "$UNINSTALL" ]; then
  if [ -n "$carla_default" ]; then
    remove_mcp_entry "${carla_default%/}/.mcp.json" && \
      log "removed '${SERVER_NAME}' from ${carla_default%/}/.mcp.json"
  else
    warn "no CARLA path (--carla / \$CARLA_UE4_ROOT) — cannot clean a checkout's .mcp.json"
  fi
  # Legacy: earlier versions also wrote one into this repo.
  [ -f "${REPO_ROOT}/.mcp.json" ] && rm -f "${REPO_ROOT}/.mcp.json" && log "removed stale ${REPO_ROOT}/.mcp.json"
  "$PYEXE" -m pip uninstall --quiet --yes "$SERVER_NAME" >/dev/null 2>&1 \
    && log "pip-uninstalled ${SERVER_NAME}" || warn "package was not installed"
  find "$REPO_ROOT" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
  rm -rf "$REPO_ROOT"/src/*.egg-info 2>/dev/null || true
  log "uninstall complete."
  exit 0
fi

# --- 2. Install the server (editable) ---------------------------------------
[ -n "$carla_default" ] || die "no CARLA checkout given — pass --carla /path/to/carla or export CARLA_UE4_ROOT"
[ -d "$carla_default" ] || die "CARLA path '$carla_default' is not a directory"

log "installing into $PYEXE ($("$PYEXE" -c 'import sys;print(".".join(map(str,sys.version_info[:3])))'))"
"$PYEXE" -m pip install --quiet --disable-pip-version-check -e "$REPO_ROOT" \
  || die "pip install failed. If Python is externally managed, retry with:\n  $PYEXE -m pip install --user -e $REPO_ROOT\nor set PYTHON to a writable interpreter."

# --- 3. Verify: tools registered + skills auto-discovered -------------------
log "verifying tools and skill discovery"
"$PYEXE" - <<'PY' || die "server import/discovery failed — install looks broken"
import sys
from carla_agentic_tools import server
tools = {t for t in ("list_skills", "read_skill", "check_prerequisites") if hasattr(server, t)}
if tools != {"list_skills", "read_skill", "check_prerequisites"}:
    print(f"missing tools: {tools}", file=sys.stderr); raise SystemExit(1)
skills = server.list_skills()
if not skills or not all(s.get("description") for s in skills):
    print(f"no skills discovered (or missing descriptions): {skills}", file=sys.stderr); raise SystemExit(1)
print(f"[verify] tools OK; discovered {len(skills)} skill(s): " + ", ".join(s["name"] for s in skills))
PY

# --- 4. Write .mcp.json into the CARLA checkout only ------------------------
# env values use ${VAR:-default}: a live export at launch wins, falling back to
# the baked default (--flag > value exported at setup > empty). CARLA_UE4_ROOT
# defaults to the checkout's own path since the config lives inside it.
MCP_JSON="${carla_default%/}/.mcp.json"
MCP_TARGET="$MCP_JSON" MCP_CMD="$PYEXE" MCP_NAME="$SERVER_NAME" MCP_CARLA="$carla_default" MCP_UE4="$ue4_default" \
"$PYEXE" - <<'PY'
import json, os, pathlib
target = pathlib.Path(os.environ["MCP_TARGET"])
data = {}
if target.is_file():
    try:
        data = json.loads(target.read_text())
    except Exception:
        data = {}
if not isinstance(data, dict):
    data = {}
data.setdefault("mcpServers", {})
data["mcpServers"][os.environ["MCP_NAME"]] = {
    "type": "stdio",
    "command": os.environ["MCP_CMD"],
    "args": ["-m", "carla_agentic_tools.server"],
    "env": {
        "CARLA_UE4_ROOT": "${CARLA_UE4_ROOT:-%s}" % os.environ["MCP_CARLA"],
        "UE4_ROOT": "${UE4_ROOT:-%s}" % os.environ["MCP_UE4"],
    },
}
target.write_text(json.dumps(data, indent=2) + "\n")
PY
log "wrote ${MCP_JSON} (merged; other servers preserved)"
log "CARLA path used: ${carla_default}"
log "UE4 path used:   ${ue4_default:-<unset>}"

# --- 5. Drop any .mcp.json this repo carried from older versions ------------
if [ -f "${REPO_ROOT}/.mcp.json" ]; then
  rm -f "${REPO_ROOT}/.mcp.json"
  log "removed stale ${REPO_ROOT}/.mcp.json (server lives in the CARLA checkout now)"
fi
if [ -f "${REPO_ROOT}/.gitignore" ]; then
  sed -i '/^\.mcp\.json$/d' "${REPO_ROOT}/.gitignore"
fi

# --- Done -------------------------------------------------------------------
cat <<DONE

$(log "setup complete.")

Agents auto-detect the server via ${MCP_JSON}:
  • Claude Code — run \`claude\` from ${carla_default} and approve the
    "${SERVER_NAME}" project MCP server when prompted (\`/mcp\` lists it).
  • Other MCP clients — point them at that .mcp.json.

To make it detectable from ANY directory (Claude Code user scope), instead run:
  claude mcp add ${SERVER_NAME} --scope user -- ${PYEXE} -m carla_agentic_tools.server

Remove everything later with:
  bash setup.sh --uninstall --carla ${carla_default}
DONE
