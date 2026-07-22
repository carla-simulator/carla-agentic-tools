#!/usr/bin/env bash
# Preflight for run-carla-server. Read-only; exits non-zero only on hard
# blockers. Run by the MCP check_prerequisites(name) tool.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HERE}/env.sh" >/dev/null
set +e  # env.sh enables -e; a preflight must report, not abort

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
