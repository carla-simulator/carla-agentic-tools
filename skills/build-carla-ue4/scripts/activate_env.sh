#!/usr/bin/env bash
# Resolve the Python the client build (boost.python bindings + wheel) will use,
# WITHOUT assuming any environment manager (venv, conda, pyenv, system, ...).
# Meant to be `source`d, after env.sh.
#
# Contract: the caller has the CARLA client environment ACTIVE (its `python3`
# on PATH), or has arranged one of the optional auto-pickups below. This mirrors
# package-carla-ue4/scripts/activate_env.sh; the build is stricter in one way —
# boost.python (Setup.sh) and the wheel (BuildPythonAPI.sh) must bind to the
# SAME interpreter (references/lessons.md L7), so we DERIVE the active
# interpreter's exact X.Y and export it as CARLA_PY_VERSION, and the make steps
# forward `--python-version=${CARLA_PY_VERSION}` to keep both stages consistent.
#
# Sets, on success:
#   CARLA_PY_BIN      absolute path to the interpreter to build against
#   CARLA_PY_VERSION  its X.Y (honoured if the caller pinned it; else derived)
#
# Optional, best-effort auto-pickups (NONE are required):
#   CARLA_ENV_ACTIVATE : path to any activation script to source (the single
#                        escape hatch that works for every env manager).
#   direnv             : if installed AND an .envrc is present, its exports load.

# Load project-local env vars into this (possibly non-interactive) shell.
# Best-effort — a silent no-op when neither hook is present. Never required.
carla_load_local_env() {
  local from="${1:-.}"
  if [ -n "${CARLA_ENV_ACTIVATE:-}" ] && [ -f "${CARLA_ENV_ACTIVATE}" ]; then
    # shellcheck disable=SC1090
    source "${CARLA_ENV_ACTIVATE}"
  fi
  if command -v direnv >/dev/null 2>&1; then
    local exports
    exports="$(cd "${from}" 2>/dev/null && direnv export bash 2>/dev/null)" || true
    [ -n "${exports:-}" ] && eval "${exports}"
  fi
  return 0
}

# Resolve CARLA_PY_BIN + CARLA_PY_VERSION for the client build. Non-zero with
# actionable, manager-agnostic guidance on failure.
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
    echo "[env] (venv/conda/system), or set CARLA_ENV_ACTIVATE to its activate" >&2
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
