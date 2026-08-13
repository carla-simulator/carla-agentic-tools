#!/usr/bin/env bash
# Step 04 — build the CARLA Python API client (LibCarla client + boost.python
# bindings + osm2odr) and install the wheel into the active client env.
#
# Prereqs: step 03 (UE4 built -> bundled clang SDK) and step 02 (client env
# prepared: a compatible interpreter active, with requirements.txt + numpy<2).
#
# Key correctness points encoded here:
#   * env.sh resolves the ACTIVE interpreter and exports its exact
#     minor as CARLA_PY_VERSION. We forward --python-version=${CARLA_PY_VERSION}
#     to `make PythonAPI`, which passes ARGS to the `setup` target too — so
#     boost.python (Setup.sh) and the wheel (BuildPythonAPI.sh) bind to the SAME
#     interpreter. Mismatch => ImportError at `import carla` (L7).
#   * The build invokes `/usr/bin/env python${CARLA_PY_VERSION}` by exact minor,
#     so that interpreter must be on PATH — it is, because it IS the active env's.
#   * On Ubuntu 24.04 the build sets _SKIP_PIP_INSTALL (PEP 668), leaving the
#     wheel in PythonAPI/carla/dist/. We install it explicitly into the env.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HERE}/env.sh"
[ -x "${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor" ] \
  || { echo "[py] ERROR: UE4 not built yet (run step 03)."; exit 1; }

carla_require_build_python || exit 1   # sets CARLA_PY_BIN + CARLA_PY_VERSION
echo "[py] building against: ${CARLA_PY_BIN} (${CARLA_PY_VERSION})"

# Idempotent ("if needed"): skip when carla already imports in this env unless
# FORCE=1. `make PythonAPI` is also incremental, so a re-run is not wasteful.
if [ "${FORCE:-0}" != "1" ] && "${CARLA_PY_BIN}" -c "import carla" >/dev/null 2>&1; then
  echo "[py] carla already importable in ${CARLA_PY_BIN} — skipping. FORCE=1 to rebuild."
  exit 0
fi

cd "${CARLA_UE4_ROOT}"

echo "[py] make PythonAPI (boost + LibCarla client + osm2odr + wheel)..."
make PythonAPI ARGS="--python-version=${CARLA_PY_VERSION} --build-wheel"

# Install the freshly built wheel into the active env (PEP 668 left it in dist/).
WHEEL="$(ls -t "${CARLA_UE4_ROOT}"/PythonAPI/carla/dist/*.whl 2>/dev/null | head -1 || true)"
[ -n "${WHEEL}" ] || { echo "[py] ERROR: no wheel produced in PythonAPI/carla/dist/"; exit 1; }
echo "[py] installing ${WHEEL} into ${CARLA_PY_BIN}..."
"${CARLA_PY_BIN}" -m pip install --force-reinstall "${WHEEL}"

echo "[py] verifying import..."
"${CARLA_PY_BIN}" -c "import carla; print('carla', getattr(carla, '__version__', 'imported OK'))"
echo "[py] DONE."
