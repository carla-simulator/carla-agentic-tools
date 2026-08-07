#!/usr/bin/env bash
# Launch a CARLA RPC server on this host. Three modes:
#
#   (default)   UNCOOKED headless: UE4Editor -game -nullrhi. RPC + physics +
#               traffic manager, NO sensor images. Ready in ~15-20s. The mode
#               for spawn/registration/drive smoke-tests — no cook needed.
#   WINDOW=1    UNCOOKED windowed: real renderer in a window on $DISPLAY.
#               Mesh distance-field generation is disabled via -ini: override,
#               because uncooked meshes have null distance fields and the real
#               renderer SIGSEGVs on them (build-carla-ue4 L17). No DF
#               shadows/AO; cook for full fidelity.
#   PACKAGED=1  COOKED package from Dist/ (cook it with the package-carla-ue4
#               skill): CarlaUE4.sh -RenderOffScreen. Full rendering headless —
#               camera/lidar work. Requires `make package` to have produced
#               Dist/CARLA_* (the build-carla-ue4 skill no longer packages).
#
# Usage:
#   bash run_server.sh [MAP] [RPC_PORT]
#     MAP       default /Game/Carla/Maps/Town02 (light map = fast first load;
#               uncooked modes only — the packaged build boots its cooked
#               default map; switch maps via client.load_world instead)
#     RPC_PORT  default 2000 (streaming port = RPC+1)
#     RESX/RESY window size for WINDOW=1 (default 1280x720)
#
# ROS 2 (opt-in, composes with every mode above — see references/ros2.md):
#   ROS2=1          add --ros2: the server publishes DDS topics itself. Needs a
#                   binary BUILT with ROS 2 (build-carla-ue4 ROS2=1) — on a plain
#                   build the flag is accepted and does nothing.
#   RMW=            fastdds (default) | cyclonedds | zenoh -> --rmw=; an unknown
#                   or not-compiled-in value makes the server DISABLE ROS 2.
#                   zenoh also needs a running rmw_zenohd router.
#   ROS_DOMAIN_ID=  0..232 -> --ros-domain-id=; must match the subscriber side.
#
# Runs in the FOREGROUND (blocks). Background it from the caller:
#   bash run_server.sh >server.log 2>&1 &
# Wait for readiness by polling the RPC port, not by sleeping:
#   until nc -z 127.0.0.1 2000; do sleep 1; done
# Stop with:
#   pkill -x UE4Editor        # uncooked modes
#   pkill -x CarlaUE4-Linux-           # packaged mode (comm is TRUNCATED to 15
#                                      # chars; -x ...-Shipping matches NOTHING)
# NEVER `pkill -f CarlaUE4.uproject` — it matches (and kills) the calling
# shell itself (exit 144; see ue4-editor-python P6).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${HERE}/env.sh"

MAP="${1:-/Game/Carla/Maps/Town02}"
RPC_PORT="${2:-2000}"
STREAM_PORT="$((RPC_PORT + 1))"

# --- ROS 2 (opt-in) ---------------------------------------------------------
# ROS2=1 appends --ros2 [--rmw=..] [--ros-domain-id=..] to whichever binary this
# script launches, in every mode. Requires a ROS-2-BUILT binary; the flag is
# silently ignored otherwise, which is why the state is reported here.
# Word-splitting of the flag string is intended (it is a flag list, not a path).
# shellcheck disable=SC2206
ROS2_FLAGS=($(carla_ros2_flags))
if [ "${ROS2:-0}" = "1" ]; then
  echo "[server] ROS2=1 -> ${ROS2_FLAGS[*]}"
  if [ "${PACKAGED:-0}" != "1" ]; then
    # Source builds only: the ini is authoritative for what got compiled in.
    case "$(carla_ros2_ini_state)" in
      on) : ;;
      off|absent)
        echo "[server] WARN: this checkout was last built with Ros2 $(carla_ros2_ini_state)."
        echo "[server]       --ros2 will be accepted and do NOTHING: no topics will appear."
        echo "[server]       Rebuild with build-carla-ue4 ROS2=1 first."
        ;;
    esac
  fi
  if [ "${RMW}" = "zenoh" ]; then
    echo "[server] NOTE: RMW=zenoh needs a Zenoh router running (rmw_zenohd) —"
    echo "[server]       start it BEFORE the server; see references/ros2.md."
  fi
  # A domain mismatch is the most common "no topics" cause and is invisible in
  # the log, so state the effective domain the subscriber side must match.
  echo "[server] ROS domain: ${ROS_DOMAIN_ID:-<unset -> server uses \$ROS_DOMAIN_ID in its own env, else 0>}"
fi

if [ "${PACKAGED:-0}" = "1" ]; then
  # Newest package wins if several exist.
  PKG="$(ls -1dt "${CARLA_UE4_ROOT}"/Dist/CARLA_*/LinuxNoEditor 2>/dev/null | head -1)"
  [ -n "${PKG}" ] && [ -x "${PKG}/CarlaUE4.sh" ] \
    || { echo "[server] ERROR: no package in ${CARLA_UE4_ROOT}/Dist — cook one with the package-carla-ue4 skill (make package)."; exit 1; }
  echo "[server] PACKAGED ${PKG} rpc=${RPC_PORT} stream=${STREAM_PORT} (-RenderOffScreen)"
  exec "${PKG}/CarlaUE4.sh" \
    -RenderOffScreen -nosound \
    -carla-rpc-port="${RPC_PORT}" -carla-streaming-port="${STREAM_PORT}" \
    "${ROS2_FLAGS[@]}"
fi

UE4_EDITOR="${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor"
UPROJECT="${CARLA_UE4_ROOT}/Unreal/CarlaUE4/CarlaUE4.uproject"
[ -x "${UE4_EDITOR}" ] || { echo "[server] ERROR: UE4Editor not built (build skill step 03)."; exit 1; }
[ -f "${UPROJECT}" ]   || { echo "[server] ERROR: CarlaUE4.uproject missing: ${UPROJECT}"; exit 1; }

export DISPLAY="${DISPLAY:-:1}"
cd "${CARLA_UE4_ROOT}/Unreal/CarlaUE4"

if [ "${WINDOW:-0}" = "1" ]; then
  echo "[server] map=${MAP} rpc=${RPC_PORT} WINDOWED on ${DISPLAY} (real render, DF off, uncooked)"
  exec "${UE4_EDITOR}" "${UPROJECT}" "${MAP}" \
    -game -windowed -ResX="${RESX:-1280}" -ResY="${RESY:-720}" -nosound \
    "-ini:Engine:[/Script/Engine.RendererSettings]:r.GenerateMeshDistanceFields=False" \
    -carla-rpc-port="${RPC_PORT}" -carla-streaming-port="${STREAM_PORT}" \
    "${ROS2_FLAGS[@]}"
else
  echo "[server] map=${MAP} rpc=${RPC_PORT} stream=${STREAM_PORT} (-game -nullrhi, headless, uncooked)"
  exec "${UE4_EDITOR}" "${UPROJECT}" "${MAP}" \
    -game -nullrhi -nosound \
    -carla-rpc-port="${RPC_PORT}" -carla-streaming-port="${STREAM_PORT}" \
    "${ROS2_FLAGS[@]}"
fi
