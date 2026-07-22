#!/usr/bin/env bash
# Step 06 — build the CarlaUE4 SERVER (editor C++ modules), and OPTIONALLY open
# the editor UI.
#
# This skill's job is to compile CARLA's source artifacts — engine (03), server
# (this step) and PythonAPI (04). COOKING/PACKAGING into a distributable Dist/
# tarball is NOT built here: that is [[package-carla-ue4]] (`make package`).
# RUNNING the result is [[run-carla-server]]. See SKILL.md "Scope".
#
# Targets (TARGET=, default `server`):
#   server  -> `make CarlaUE4Editor`. Editor C++ modules incl the Carla server
#              plugin (libUE4Editor-Carla*.so) and the CarlaTools plugin
#              (libUE4Editor-CarlaTools*.so, VehicleAuthoringLibrary). Binaries
#              only — no cook, no UI. This is what an uncooked -nullrhi server
#              ([[run-carla-server]]) and the verify step (07) need, and the
#              cheap incremental recompile after touching Unreal/CarlaUE4/Plugins/
#              — the target [[add-carla-vehicle]] points at when it reports
#              STATUS=REBUILD_CARLATOOLS_REQUIRED.
#   launch  -> `make launch`. Builds CarlaUE4Editor (as above) AND opens the UE4
#              editor UI. Interactive; needs a display. Opt-in — for editor work,
#              not headless/agent runs.
#
# No client Python env is required here: unlike `make package` (L15), neither
# CarlaUE4Editor nor launch build the Python wheel.
#
# Idempotent (TARGET=server): skips when the server plugin .so is already present
# unless FORCE=1. `make` is incremental regardless, so a re-run is cheap.
#
# NOTE (L16): the top-level make MUST see UE4_ROOT exported, or the generated
# Build/clang{,++}.sh wrappers bake a broken '/Engine/...' compiler path and
# every compile fails. env.sh (sourced below) guarantees it.
#
# Prereqs: step 03 (UE4 built). Content (05) only matters at run time, not here.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HERE}/env.sh"

TARGET="${TARGET:-server}"

[ -x "${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor" ] \
  || { echo "[server] ERROR: UE4 not built (step 03)."; exit 1; }

PLUGIN_SRC="${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Plugins/CarlaTools/Source/CarlaTools"
[ -d "${PLUGIN_SRC}" ] \
  || { echo "[server] ERROR: CarlaTools plugin source missing at ${PLUGIN_SRC} — update the ue4-dev checkout."; exit 1; }
[ -n "$(find "${PLUGIN_SRC}" -name 'VehicleAuthoringLibrary.h' -print -quit)" ] \
  || echo "[server] WARN: VehicleAuthoringLibrary.h not found — branch may predate PR #9805; add-carla-vehicle will not work."

CARLATOOLS_SO="$(find "${CARLA_UE4_ROOT}/Unreal/CarlaUE4" -name 'libUE4Editor-CarlaTools*.so' -print -quit 2>/dev/null || true)"

case "${TARGET}" in
  server)
    if [ -n "${CARLATOOLS_SO}" ] && [ "${FORCE:-0}" != "1" ]; then
      echo "[server] already built (CarlaTools .so present) — skipping. FORCE=1 to rebuild."
      echo "[server] ${CARLATOOLS_SO}"
      exit 0
    fi
    cd "${CARLA_UE4_ROOT}"
    echo "[server] make CarlaUE4Editor (UBT incremental; minutes)..."
    make CarlaUE4Editor
    # Ground truth is the produced module, not make's exit code (L13).
    SO="$(find "${CARLA_UE4_ROOT}/Unreal/CarlaUE4" -name 'libUE4Editor-CarlaTools*.so' -print -quit)"
    [ -n "${SO}" ] \
      || { echo "[server] ERROR: build finished but libUE4Editor-CarlaTools.so was not produced."; exit 1; }
    echo "[server] DONE (server): ${SO}"
    ;;
  launch)
    cd "${CARLA_UE4_ROOT}"
    echo "[server] make launch (build CarlaUE4Editor + open the editor UI; ~30-60min first run)..."
    echo "[server] NOTE: interactive — needs a display; opt-in for editor work."
    make launch
    echo "[server] DONE (launch)."
    ;;
  *)
    echo "[server] ERROR: unknown TARGET='${TARGET}' (expected 'server' or 'launch')."; exit 1
    ;;
esac
