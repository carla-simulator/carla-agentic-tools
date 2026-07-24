#!/usr/bin/env bash
# Resolve the Python that `make import` will use, WITHOUT assuming any
# particular environment manager (uv/venv, conda, pyenv, system, ...).
# Meant to be `source`d.
#
# Contract: the caller has the CARLA client environment ACTIVE (its `python3` on
# PATH), or has arranged one of the optional auto-pickups below.
# Util/BuildTools/Import.py does `import carla` at MODULE scope — it dies on the
# first line if the active interpreter lacks the wheel — and later calls
# carla.Map() to cook the Traffic Manager binary. We verify that here, before
# `make` spends anything, and otherwise stay out of the way.
#
# Optional, best-effort auto-pickups (NONE are required):
#   - CARLA_ENV_ACTIVATE : path to any activation script to source. The single
#     escape hatch that works for every env manager.
#   - direnv             : if installed AND an .envrc is present, its exports are
#     loaded (a non-interactive shell does not do this on its own).

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

# Pick the interpreter Import.sh will call and verify it can `import carla`.
# Sets CARLA_PY_BIN and CARLA_PY_ARG:
#   - no pin  -> plain `python3` (the active env); CARLA_PY_ARG stays empty so
#     `make import` is NOT told a version and the active env wins.
#   - pinned  -> `python<pin>`; CARLA_PY_ARG="--python-version=<pin>" is
#     forwarded so a version-suffixed interpreter is used deliberately.
# Non-zero with actionable, manager-agnostic guidance on failure.
carla_require_client_python() {
  local pin="${1:-}"
  local py
  if [ -n "${pin}" ]; then
    py="python${pin}"
    CARLA_PY_ARG="--python-version=${pin}"
  else
    py="python3"
    CARLA_PY_ARG=""
  fi
  CARLA_PY_BIN="$(command -v "${py}" 2>/dev/null || true)"
  if [ -z "${CARLA_PY_BIN}" ]; then
    echo "[env] no '${py}' on PATH." >&2
    echo "[env] Activate the environment holding your CARLA client python" >&2
    echo "[env] (venv/conda/system), or set CARLA_ENV_ACTIVATE to its activate" >&2
    echo "[env] script. Do NOT set CARLA_PY_VERSION unless you truly need a" >&2
    echo "[env] version-suffixed interpreter (it must resolve INSIDE that env)." >&2
    return 1
  fi
  if ! "${CARLA_PY_BIN}" -c 'import carla' 2>/dev/null; then
    echo "[env] ${CARLA_PY_BIN} cannot 'import carla'." >&2
    echo "[env] Import.py imports carla on its first line, so the import aborts" >&2
    echo "[env] immediately. Activate the env holding the CARLA wheel, or build +" >&2
    echo "[env] install it there (build-carla-ue4 step 04). See references/props.md P1." >&2
    return 1
  fi
  echo "[env] python: ${CARLA_PY_BIN} (has carla)"
  export CARLA_PY_BIN CARLA_PY_ARG
  return 0
}
