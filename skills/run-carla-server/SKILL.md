---
name: run-carla-server
description: Launches a CARLA RPC server (ue4-dev) a carla.Client can connect to — headless -nullrhi from uncooked content, windowed with real rendering, or a cooked Dist package — and shuts it down cleanly. Use when the user asks to "run/start the CARLA server", "boot CARLA headless", "launch CARLA with a window", or "serve a packaged CARLA build".
license: MIT
compatibility: Linux. Requires a build produced by build-carla-ue4 — UE4Editor + fetched content for the uncooked modes, or a Dist/ package for PACKAGED=1. WINDOW=1 needs an X display + NVIDIA GPU. The verify client needs an active CARLA client env (venv, conda, or system — no manager assumed).
metadata:
  requires: build-carla-ue4
  prerequisites: scripts/check_env.sh
  reference: references/lessons.md
---

# Run a CARLA server

Starts a CARLA server a `carla.Client` can connect to. Use it to verify authored
content ([[add-carla-vehicle]]), run traffic scenarios, or feed the MCP's
live-simulator tools. It is NOT for asset editing — that is [[ue4-editor-python]]
(editor commandlet, no RPC).

The central trade-off (build-carla-ue4 L17): **uncooked** content has no mesh
distance fields, so the real renderer crashes headless — hence three modes:

| Mode | Command | Rendering | Sensors | Cook needed |
|------|---------|-----------|---------|-------------|
| default | `bash scripts/run_server.sh` | none (`-nullrhi`) | NO images | no |
| `WINDOW=1` | `WINDOW=1 bash scripts/run_server.sh` | real, windowed, DF off | on-screen only | no |
| `PACKAGED=1` | `PACKAGED=1 bash scripts/run_server.sh` | real (`-RenderOffScreen`) | camera/lidar work | yes (build step 06) |

**Boot time is tens of seconds, not a fixed number** — measured here on Town02
headless: ~38 s cold (32 s of it `LoadMap`), less when warm; heavy maps and a
cold shader cache are slower. Always poll the port (S4), never sleep a guess.

RPC + physics + Traffic Manager work in **all** modes; pick the cheapest one that
covers what you're testing. (PACKAGED mode is encoded from build docs + L17; the
uncooked modes are live-verified.)

> Gotchas live in [`references/lessons.md`](references/lessons.md) — read before
> debugging. `S#` citations below point at it.

## Instructions

```
Run Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: Pick a mode and launch (backgrounded), poll the RPC port
- [ ] Step 3: Verify a client round-trips
- [ ] Step 4: Stop the server cleanly (see S3 — never pkill -f the uproject)
```

## Prerequisites

- Roots resolve via `scripts/env.sh` (both overridable): `UE4_ROOT` (uncooked
  modes launch the editor) and `CARLA_UE4_ROOT` (the checkout to serve). Export
  them, or run from inside the checkout.
- Uncooked modes: UE4 built + content fetched ([[build-carla-ue4]] steps 03, 05).
- `PACKAGED=1`: a `Dist/CARLA_*` package ([[build-carla-ue4]] step 06, `make package`).
- Verify client: any active CARLA client env (the wheel installed by build step
  04); no manager is assumed.

## Quick start

```bash
cd skills/run-carla-server
bash scripts/check_env.sh

# headless smoke-test server, backgrounded
bash scripts/run_server.sh >/tmp/carla_server.log 2>&1 &
until nc -z 127.0.0.1 2000; do sleep 1; done     # poll, don't sleep blindly

# ... use it (spawn_test.py, MCP tools, any carla.Client) ...

pkill -x UE4Editor                                # clean stop (see S3!)
```

## Reference

- **Map choice:** light maps (Town01/Town02) minimise first-load time. Uncooked
  modes take the map as arg 1; the packaged build boots its cooked default —
  switch with `client.load_world("Town02")` instead.
- **Ports:** `scripts/run_server.sh [MAP] [RPC_PORT]`; streaming port is always
  RPC+1. Run parallel servers on 2000/2002/2004...
- **Readiness:** the RPC port opening is the signal; log line
  `LogCarlaServer: Initialized CarlaServer` appears at the same time.
- **Shutdown:** `pkill -x UE4Editor` (uncooked) /
  `pkill -x CarlaUE4-Linux-Shipping` (packaged). **Never**
  `pkill -f CarlaUE4.uproject` — it kills your own shell (S3).

## Verify

A server is up when a client round-trips (run with your CARLA client env active —
venv/conda/system, whichever holds the wheel from build step 04):

```bash
python -c "import carla; print(carla.Client('127.0.0.1', 2000).get_server_version())"
```

Artifacts to check on failure: the server log's first `Signal 11` (not the last —
the trailing CrashReportClient crash is a red herring, S1) and whether the port
ever opened.

## Troubleshooting

**Error: server SIGSEGVs seconds after opening the RPC port (uncooked)**
Cause: the real renderer dereferences a null mesh distance field — uncooked
content has none (S1).
Solution: use the default `-nullrhi` mode (no render thread), or `WINDOW=1`
(disables DF generation via `-ini:` override). For sensor images, cook and run
`PACKAGED=1`.

**Error: stopping the server killed the calling shell (exit 144)**
Cause: `pkill -f CarlaUE4.uproject` matches the launching shell's own args (S3).
Solution: `pkill -x UE4Editor` (uncooked) or `pkill -x CarlaUE4-Linux-Shipping`
(packaged) — exact process names.

**Error: client connects after a fixed sleep but times out**
Cause: it raced first-load shader compilation; boot time varies (S4).
Solution: poll the port — `until nc -z 127.0.0.1 <port>; do sleep 1; done`. Use
`nc -z` / `ss -ltn`, not the bash `/dev/tcp` idiom (fails under zsh, S4).

**Error: `no Dist/ package` with `PACKAGED=1`**
Cause: no cooked package exists.
Solution: run [[build-carla-ue4]] step 06 (`make package`), or use an uncooked
mode.

## Outputs

None persisted — a running process serving RPC on the chosen port.
