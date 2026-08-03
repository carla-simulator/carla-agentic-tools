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
# whatever interpreter the active env provides (references/lessons.md L5-L7).

# Sets no shell options on purpose: this file is sourced, and `set -e` here
# would change its callers' error semantics. Each script sets its own.

# --- Optional environment hook ----------------------------------------------
# CARLA_ENV_ACTIVATE, when set, names an activation script to source into this
# (possibly non-interactive) shell — the one hook for driving this skill without
# an already-active environment. Unset, it is a silent no-op. Nothing else is
# detected: no environment-manager binary is probed, no dotfile is searched for.
# Roots the caller exported explicitly outrank anything that script sets.
_KEEP_CARLA_ROOT="${CARLA_UE4_ROOT:-}" _KEEP_UE4_ROOT="${UE4_ROOT:-}"
if [ -n "${CARLA_ENV_ACTIVATE:-}" ] && [ -f "${CARLA_ENV_ACTIVATE}" ]; then
  # shellcheck disable=SC1090
  source "${CARLA_ENV_ACTIVATE}"
fi
[ -n "${_KEEP_CARLA_ROOT}" ] && CARLA_UE4_ROOT="${_KEEP_CARLA_ROOT}"
[ -n "${_KEEP_UE4_ROOT}" ] && UE4_ROOT="${_KEEP_UE4_ROOT}"

# --- Resolve the target CARLA checkout --------------------------------------
# Precedence: explicit CARLA_UE4_ROOT  >  $PWD if it is a checkout  >  the
# path-derived guess (only meaningful when this repo was dropped INTO a checkout).
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

# UE4_ROOT has no derivable default from a standalone repo — export it, or let
# check_env.sh fail loudly with the path it looked for.
export UE4_ROOT="${UE4_ROOT:-}"

# --- Optional Python pin ----------------------------------------------------
# CARLA's boost.python bindings and the wheel must bind to ONE interpreter
# (references/lessons.md L7), derived below from the ACTIVE env.
# Set CARLA_PY_VERSION only to force a specific minor (e.g. 3.10) — it must then
# resolve as `python<pin>` INSIDE the active env. Left unset, the active
# `python3`'s own X.Y is used. No default is pinned here.
export CARLA_PY_VERSION="${CARLA_PY_VERSION:-}"

# --- Client Python ----------------------------------------------------------
# boost.python (Setup.sh) and the wheel (BuildPythonAPI.sh) must bind to the
# SAME interpreter (references/lessons.md L7), so this derives the ACTIVE
# interpreter's exact X.Y into CARLA_PY_VERSION and the make steps forward
# --python-version=${CARLA_PY_VERSION} to keep both stages consistent.
# Sets CARLA_PY_BIN + CARLA_PY_VERSION; non-zero with actionable guidance.
carla_require_build_python() {
  local pin="${CARLA_PY_VERSION:-}"
  local py

  if [ -n "${pin}" ]; then
    # Caller pinned a minor; it must resolve INSIDE the active env.
    py="python${pin}"
  else
    py="python3"
  fi

  CARLA_PY_BIN="$(command -v "${py}" 2>/dev/null || true)"
  if [ -z "${CARLA_PY_BIN}" ]; then
    echo "[env] no '${py}' on PATH." >&2
    echo "[env] Activate the environment holding your CARLA client python" >&2
    echo "[env] in this shell, or set CARLA_ENV_ACTIVATE to its activate" >&2
    echo "[env] script. Set CARLA_PY_VERSION only to force a specific minor —" >&2
    echo "[env] it must then resolve as 'python<pin>' INSIDE that env." >&2
    return 1
  fi

  # Derive the exact X.Y so boost + wheel bind to one interpreter (L7). When the
  # caller pinned, keep the pin; otherwise adopt the active interpreter's own.
  local derived
  derived="$("${CARLA_PY_BIN}" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || true)"
  [ -n "${derived}" ] || { echo "[env] ${CARLA_PY_BIN} did not report a version." >&2; return 1; }
  export CARLA_PY_VERSION="${pin:-${derived}}"

  # numpy < 2 is required: CARLA's bindings are compiled against the numpy 1.x
  # C-API and crash on import under 2.x (L6). Warn (not fail) — 02_client_env.sh
  # installs it, and this file also runs before that step.
  if "${CARLA_PY_BIN}" -c 'import numpy, sys; sys.exit(0 if numpy.__version__.split(".")[0]=="1" else 1)' 2>/dev/null; then
    echo "[env] python: ${CARLA_PY_BIN} (${CARLA_PY_VERSION}, numpy 1.x OK)"
  elif "${CARLA_PY_BIN}" -c 'import numpy' 2>/dev/null; then
    echo "[env] WARN: ${CARLA_PY_BIN} has numpy>=2 — pin numpy<2 (run 02_client_env.sh); 'import carla' will crash otherwise" >&2
  else
    echo "[env] python: ${CARLA_PY_BIN} (${CARLA_PY_VERSION}, numpy not yet installed — 02_client_env.sh adds it)"
  fi

  export CARLA_PY_BIN CARLA_PY_VERSION
  return 0
}

unset _KEEP_CARLA_ROOT _KEEP_UE4_ROOT _SKILL_SCRIPTS_DIR _DERIVED_ROOT _UPROJECT_REL

echo "[env] CARLA_UE4_ROOT  = ${CARLA_UE4_ROOT:-<unset — export it>}"
echo "[env] UE4_ROOT        = ${UE4_ROOT:-<unset — export it>}"
