#!/usr/bin/env bash
# Self-contained environment for the build-carla-ue4 skill.
# Source this before running the skill's scripts:  source env.sh
#
# carla-agentic-tools is a STANDALONE repo — it does not live inside a CARLA
# checkout — so the target instance is chosen at runtime. Both roots below are
# overridable and must ultimately point at a real CARLA + UE4:
#
#   CARLA_UE4_ROOT  the carla source checkout (branch ue4-dev) to build
#   UE4_ROOT        the built CarlaUnreal UE 4.26 fork
#
# No environment-manager assumption is made: the Python client stage uses
# whatever interpreter the active env provides (see scripts/activate_env.sh and
# references/lessons.md L5-L7).

set -euo pipefail

# --- Resolve the target CARLA checkout --------------------------------------
# Precedence: explicit CARLA_UE4_ROOT  >  $PWD if it is a checkout  >  the
# path-derived guess (only meaningful when this repo was dropped INTO a checkout).
_SKILL_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_DERIVED_ROOT="$(cd "${_SKILL_SCRIPTS_DIR}/../../../.." && pwd)"

if [ -z "${CARLA_UE4_ROOT:-}" ]; then
  if [ -f "${PWD}/Util/BuildTools/Setup.sh" ]; then
    CARLA_UE4_ROOT="${PWD}"
  elif [ -f "${_DERIVED_ROOT}/Util/BuildTools/Setup.sh" ]; then
    CARLA_UE4_ROOT="${_DERIVED_ROOT}"
  fi
fi
export CARLA_UE4_ROOT="${CARLA_UE4_ROOT:-}"

# UE4_ROOT has no derivable default from a standalone repo — export it, or let
# check_env.sh fail loudly with the path it looked for.
export UE4_ROOT="${UE4_ROOT:-}"

# --- Optional Python pin ----------------------------------------------------
# CARLA's boost.python bindings and the wheel must bind to ONE interpreter
# (references/lessons.md L7), which activate_env.sh derives from the ACTIVE env.
# Set CARLA_PY_VERSION only to force a specific minor (e.g. 3.10) — it must then
# resolve as `python<pin>` INSIDE the active env. Left unset, the active
# `python3`'s own X.Y is used. No default is pinned here.
export CARLA_PY_VERSION="${CARLA_PY_VERSION:-}"

# --- Build tuning -----------------------------------------------------------
# Parallelism for CARLA make steps. UE4's own top-level `make` must NOT use -j
# (it OOMs / races, L9); that is handled inside 03_build_ue4.sh, not here.
export CARLA_MAKE_JOBS="${CARLA_MAKE_JOBS:-$(nproc)}"

echo "[env] CARLA_UE4_ROOT  = ${CARLA_UE4_ROOT:-<unset — export it>}"
echo "[env] UE4_ROOT        = ${UE4_ROOT:-<unset — export it>}"
