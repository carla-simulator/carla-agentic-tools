#!/usr/bin/env bash
# Self-contained environment for the import-carla-map skill.
# Source before the skill's other scripts:  source env.sh
#
# carla-agentic-tools is standalone (not inside a CARLA checkout), so the target
# instance is chosen at runtime. Both roots are overridable and must point at a
# real, built CARLA + UE4:
#
#   CARLA_UE4_ROOT  the carla source checkout to import the map into
#   UE4_ROOT        the built CarlaUnreal UE 4.26 fork (runs the editor)
#
# Unlike prop import, a MAP import needs a carla-capable python:
# Util/BuildTools/Import.py does `import carla` at module scope and calls
# carla.Map(...).cook_in_memory_map(...) to build the Traffic Manager binary.
# So the client wheel is a HARD requirement here (see activate_env.sh /
# check_env.sh), not an optional verify-only extra.

# NOTE: this file deliberately sets no shell options. It is sourced by other
# scripts, and `set -e` here would silently change THEIR error semantics (a
# plain `[ -n "$x" ] && ...` test would abort the caller). Each script that does
# work sets its own `set -euo pipefail`; check_env.sh sets -uo on purpose.

# --- Resolve the target CARLA checkout --------------------------------------
# Precedence: explicit CARLA_UE4_ROOT  >  $PWD if it is a checkout  >  the
# path-derived guess (only meaningful when this repo sits inside a checkout).
_SKILL_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_DERIVED_ROOT="$(cd "${_SKILL_SCRIPTS_DIR}/../../../.." && pwd)"
_UPROJECT_REL="Unreal/CarlaUE4/CarlaUE4.uproject"

if [ -z "${CARLA_UE4_ROOT:-}" ]; then
  if [ -f "${PWD}/${_UPROJECT_REL}" ]; then
    CARLA_UE4_ROOT="${PWD}"
  elif [ -f "${_DERIVED_ROOT}/${_UPROJECT_REL}" ]; then
    CARLA_UE4_ROOT="${_DERIVED_ROOT}"
  fi
fi
export CARLA_UE4_ROOT="${CARLA_UE4_ROOT:-}"

# UE4_ROOT has no derivable default — export it, or let check_env.sh fail loudly
# with the path it looked for.
export UE4_ROOT="${UE4_ROOT:-}"

# --- Optional Python pin -----------------------------------------------------
# Set CARLA_PY_VERSION only to force a specific minor (e.g. 3.10) for the client
# python that runs Import.py. It must resolve as `python<pin>` INSIDE the
# active env, and that interpreter is the one that must import `carla`.
export CARLA_PY_VERSION="${CARLA_PY_VERSION:-}"

# --- Where maps land ---------------------------------------------------------
# The map's own directory is an argument to import_map.py, not an env var: it is
# read in place, from wherever it is.

# Content is commonly a symlink to one clone shared by every worktree; the
# imported map lands under Content/<package>/, which every checkout then sees.
export CARLA_CONTENT_DIR="${CARLA_UE4_ROOT:+${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Content}"

echo "[env] CARLA_UE4_ROOT  = ${CARLA_UE4_ROOT:-<unset — export it>}"
echo "[env] UE4_ROOT        = ${UE4_ROOT:-<unset — export it>}"
