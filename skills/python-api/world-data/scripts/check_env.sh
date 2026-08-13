#!/usr/bin/env bash
# Prerequisite checks for world-data. Read-only, no sudo. Fast probe so
# the MCP check_prerequisites(name) tool never hangs.
# Exits non-zero ONLY on hard blockers: no `carla` module, or no reachable server.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${HERE}/env.sh" >/dev/null

"${PYTHON}" - "$CARLA_HOST" "$CARLA_PORT" <<'PY'
import sys

def fail(m): print(f"FAIL  {m}")
def ok(m):   print(f"PASS  {m}")

try:
    import carla
except Exception as e:
    fail(f"cannot import carla — install the PythonAPI wheel for this interpreter ({e})")
    print("\nprerequisites BLOCKED — resolve FAIL lines above")
    sys.exit(1)
ok("carla module importable")

host, port = sys.argv[1], int(sys.argv[2])
try:
    client = carla.Client(host, port)
    client.set_timeout(4.0)  # short: a healthy local server answers in <1s
    ok(f"server reachable at {host}:{port} (server {client.get_server_version()})")
except Exception as e:
    fail(f"no CARLA server at {host}:{port} — start one first, or set CARLA_HOST/CARLA_PORT ({e})")
    print("\nprerequisites BLOCKED — resolve FAIL lines above")
    sys.exit(1)

print("\nprerequisites OK — hard blockers clear")
sys.exit(0)
PY
