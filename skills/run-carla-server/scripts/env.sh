#!/usr/bin/env bash
# Self-contained environment for the run-carla-server skill.
# Source this before the skill's scripts:  source env.sh
#
# carla-agentic-tools is a STANDALONE repo — it does not live inside a CARLA
# checkout — so the target instance is chosen at runtime. Both roots below are
# overridable and must point at a real, built CARLA + UE4:
#
#   CARLA_UE4_ROOT  the carla source checkout (branch ue4-dev) to serve
#   UE4_ROOT        the built CarlaUnreal UE 4.26 fork (uncooked modes launch it)
#
# No environment-manager assumption is made: the verify client uses whatever
# `python3` your active CARLA client env provides.

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
# check_env.sh fail loudly with the path it looked for. Only the uncooked modes
# (default / WINDOW=1) need it; PACKAGED=1 runs from Dist/ without it.
export UE4_ROOT="${UE4_ROOT:-}"

echo "[env] CARLA_UE4_ROOT  = ${CARLA_UE4_ROOT:-<unset — export it>}"
echo "[env] UE4_ROOT        = ${UE4_ROOT:-<unset — needed for uncooked modes>}"
