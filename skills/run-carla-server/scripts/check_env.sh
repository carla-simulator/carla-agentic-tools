#!/usr/bin/env bash
# Preflight for run-carla-server. Read-only; exits non-zero only on hard
# blockers. Run by the MCP check_prerequisites(name) tool.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HERE}/env.sh" >/dev/null

rc=0
ok(){   echo "  PASS $*"; }
warn(){ echo "  WARN $*"; }
bad(){  echo "  FAIL $*"; rc=1; }

echo "== Uncooked modes (default / WINDOW=1) =="
[ -x "${UE4_ROOT}/Engine/Binaries/Linux/UE4Editor" ] \
  && ok "UE4Editor built" || bad "UE4Editor missing — run build-carla-ue4 step 03"
[ -f "${CARLA_UE4_ROOT}/Unreal/CarlaUE4/CarlaUE4.uproject" ] \
  && ok "CarlaUE4.uproject present" || bad "CarlaUE4.uproject missing"
CONTENT="${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Content/Carla"
# -L: Content/Carla may be a symlink to a shared content checkout.
if [ -d "${CONTENT}/.git" ] && [ -n "$(find -L "${CONTENT}" -mindepth 1 -maxdepth 1 ! -name '.git' -print -quit 2>/dev/null)" ]; then
  ok "Content/Carla populated (maps available)"
else
  bad "Content/Carla missing/incomplete — run build-carla-ue4 step 05"
fi

echo "== Packaged mode (PACKAGED=1) =="
PKG="$(ls -1dt "${CARLA_UE4_ROOT}"/Dist/CARLA_*/LinuxNoEditor 2>/dev/null | head -1)"
[ -n "${PKG}" ] && ok "package found: ${PKG}" \
  || warn "no Dist/ package — PACKAGED=1 unavailable until build step 06 (make package); uncooked modes unaffected"

echo "== ROS 2 native interface (ROS2=${ROS2}) =="
if [ "${ROS2}" != "1" ]; then
  ok "ROS 2 off (set ROS2=1 to publish DDS topics; needs a ROS-2-built binary)"
else
  case "$(carla_ros2_ini_state)" in
    on)  ok "checkout built with Ros2 ON — uncooked modes will publish";;
    off) bad "checkout built with Ros2 OFF — --ros2 does nothing; rebuild with build-carla-ue4 ROS2=1";;
    absent) warn "OptionalModules.ini absent — cannot tell if ROS 2 is compiled in (a Dist/ package carries its own state)";;
  esac
  case "${RMW}" in
    ""|fastdds|cyclonedds|zenoh) ok "RMW=${RMW:-<server default: fastdds>}";;
    *) bad "RMW='${RMW}' is not a valid middleware (fastdds | cyclonedds | zenoh) — the server DISABLES ROS 2 on an unknown value";;
  esac
  # The domain must match on the subscriber side or topics are invisible.
  if [ -n "${ROS_DOMAIN_ID:-}" ]; then
    if [ "${ROS_DOMAIN_ID}" -ge 0 ] 2>/dev/null && [ "${ROS_DOMAIN_ID}" -le 232 ] 2>/dev/null; then
      ok "ROS_DOMAIN_ID=${ROS_DOMAIN_ID} (subscribers must use the same)"
    else
      bad "ROS_DOMAIN_ID='${ROS_DOMAIN_ID}' out of range 0..232 — the server logs an error and falls back to the default domain"
    fi
  else
    ok "ROS_DOMAIN_ID unset — default domain 0 on both sides"
  fi
  if [ "${RMW}" = "zenoh" ]; then
    pgrep -f rmw_zenohd >/dev/null 2>&1 && ok "Zenoh router (rmw_zenohd) running" \
      || warn "no rmw_zenohd process — start the Zenoh router before the server (references/ros2.md)"
  fi
  # Consuming the topics needs ROS 2 or the demo images; the server itself does not.
  command -v ros2 >/dev/null 2>&1 && ok "ros2 CLI available for verification" \
    || warn "no ros2 CLI here — verify topics from a ROS 2 container (visualize-ros-rviz)"
fi

echo "== Ports / display =="
if command -v nc >/dev/null 2>&1 && nc -z 127.0.0.1 2000 2>/dev/null; then
  warn "port 2000 already in use — a server is running; pass a different RPC_PORT or stop it (pkill -x UE4Editor)"
else
  ok "default RPC port 2000 free"
fi
[ -n "${DISPLAY:-}" ] && ok "DISPLAY=${DISPLAY} (WINDOW=1 usable)" \
  || warn "DISPLAY unset — WINDOW=1 will default to :1; headless modes unaffected"

echo "== Result =="
[ "$rc" -eq 0 ] && echo "  preflight OK (warnings are non-blocking)" || echo "  HARD BLOCKERS present — fix FAIL items."
exit $rc
