---
name: telemetry
description: Reads a specific actor's live telemetry from a running CARLA server — location and rotation, velocity and speed, acceleration, angular velocity, and for vehicles the control input (throttle/steer/brake), front-wheel steer angle and mass. All kinematics come from one world snapshot so they are frame-consistent. Use when the user asks "how fast is it going", "where/what heading is the car", "show the ego's telemetry", or "stream a vehicle's state". Resolve ambiguous targets with the world-data skill.
license: MIT
compatibility: Any OS with the CARLA PythonAPI installed for the active interpreter and a reachable, already-running CARLA server. Does NOT need UE4_ROOT. Tested against CARLA 0.9.16.
metadata:
  prerequisites: scripts/check_env.sh
  reference: references/telemetry.md
---

# Read actor telemetry

Report one actor's live state. Kinematics (transform, velocity, acceleration,
angular velocity) are read from a single `world.get_snapshot()` so they belong to
the **same frame** — calling the per-actor getters separately can straddle two
frames and give inconsistent numbers.

Target the actor by `--id` (the reliable way), `--role hero`, `--filter`,
`--color`, or `--nearest --near-id N`. If several still match, it stops and tells
you to narrow by a distinguishing attribute or resolve the id with the
[`world-data`](../world-data/SKILL.md) skill, then pass `--id`.

## Instructions

```
Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: Resolve the target id (world-data) if the description is ambiguous
- [ ] Step 3: show a snapshot, or watch to stream it
```

Commands need `CARLA_HOST`/`CARLA_PORT` from `scripts/env.sh`.

### Step 1: Check prerequisites

```bash
bash scripts/check_env.sh
```

### Step 3: Read

```bash
source scripts/env.sh

python3 scripts/telemetry.py show --role hero            # the ego
python3 scripts/telemetry.py show --id 137               # a specific actor
python3 scripts/telemetry.py watch --id 137 --seconds 10 --hz 5    # stream

# resolve first, then read (ambiguous case)
# world-data actors --filter '*prius*' --near-id 100 --nearest   -> id=137
python3 scripts/telemetry.py show --id 137
# or directly by a distinguishing attribute
python3 scripts/telemetry.py show --filter '*prius*' --color 255,0,0
```

## Examples

**Example 1: how fast is the ego**

User says: "how fast is the ego going?"

`show --role hero` → speed in km/h (+ full state).

**Example 2: one prius among several**

User says: "telemetry of the prius near me"

`world-data actors --filter '*prius*' --near-id <ego> --nearest` → id, then
`telemetry show --id <id>`.

**Example 3: watch a vehicle accelerate**

User says: "stream the ego's speed for 10 s"

`watch --role hero --seconds 10 --hz 5`.

## Troubleshooting

**Problem: "N actors match — disambiguate"**
Cause: `--filter` is ambiguous.
Solution: use world-data to pick one, then pass `--id`.

**Problem: speed/accel are zero or jumpy**
Cause: the world isn't advancing (sync mode without ticks), or the actor is idle.
Solution: tick the world (set-world-settings) or run async; the snapshot keeps the
reads frame-consistent regardless.

**Problem: no wheel/control info**
Cause: the actor isn't a vehicle (walkers/sensors have no VehicleControl).
Solution: expected; those show only transform/velocity/acceleration.

## Outputs

Text telemetry (one snapshot, or a stream). No world change.

Detail (frame-consistent snapshot reads, the fields, vehicle-specific state) in
[references/telemetry.md](references/telemetry.md).
