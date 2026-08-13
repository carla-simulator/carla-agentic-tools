#!/usr/bin/env bash
# Prerequisite checks for navigate-to. Read-only, no sudo. Fast probe.
# Hard blockers: no `carla` module, no `agents` package (needs CARLA_ROOT), or no
# reachable server.
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
    fail(f"cannot import carla ({e})"); print("\nprerequisites BLOCKED"); sys.exit(1)
ok("carla module importable")

try:
    import agents.navigation.basic_agent  # noqa: F401
    ok("agents package importable (CARLA_ROOT/PythonAPI/carla on PYTHONPATH)")
except Exception as e:
    fail(f"cannot import agents — set CARLA_ROOT to a carla checkout ({e})")
    print("\nprerequisites BLOCKED — resolve FAIL lines above"); sys.exit(1)

host, port = sys.argv[1], int(sys.argv[2])
try:
    client = carla.Client(host, port); client.set_timeout(4.0)
    ok(f"server reachable at {host}:{port} (server {client.get_server_version()})")
except Exception as e:
    fail(f"no CARLA server at {host}:{port} ({e})")
    print("\nprerequisites BLOCKED — resolve FAIL lines above"); sys.exit(1)

print("\nprerequisites OK — hard blockers clear")
sys.exit(0)
PY
