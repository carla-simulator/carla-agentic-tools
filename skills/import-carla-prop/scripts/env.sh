#!/usr/bin/env bash
# Self-contained environment for the import-carla-prop skill.
# Source before the skill's other scripts:  source env.sh
#
# carla-agentic-tools is standalone (not inside a CARLA checkout), so the target
# instance is chosen at runtime. Both roots are overridable and must point at a
# real, built CARLA + UE4:
#
#   CARLA_UE4_ROOT  the carla source checkout to import into
#   UE4_ROOT        the built CarlaUnreal UE 4.26 fork (runs the editor)
#
# The importer drives UE4Editor directly (-run=pythonscript) rather than going
# through `make import`, so no Python environment is needed to IMPORT a prop.
# The client wheel is only needed to VERIFY one — see activate_env.sh.

set -euo pipefail

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

# --- Optional Python pin (verification only) --------------------------------
# Set CARLA_PY_VERSION only to force a specific minor (e.g. 3.10) for the client
# python that runs verify_prop.py. It must resolve as `python<pin>` INSIDE the
# active env, and that interpreter is the one that must import `carla`.
export CARLA_PY_VERSION="${CARLA_PY_VERSION:-}"

# --- Where content lives ----------------------------------------------------
# Commonly a symlink to one content clone shared by every worktree; the stock
# import route writes into it. import_prop.py says so when that is the case.
export CARLA_CONTENT_DIR="${CARLA_UE4_ROOT:+${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Content}"

echo "[env] CARLA_UE4_ROOT  = ${CARLA_UE4_ROOT:-<unset — export it>}"
echo "[env] UE4_ROOT        = ${UE4_ROOT:-<unset — export it>}"
