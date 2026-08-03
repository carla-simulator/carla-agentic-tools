---
name: spawn-vehicles
description: Spawns vehicles on a running CARLA server and destroys them — scattered across the map's spawn points on Traffic Manager autopilot, a row queued in a single lane at a fixed spacing, or a single hero/ego vehicle. Covers blueprint filtering, the atomic autopilot hand-off, and cleanup. Use when the user asks to "spawn vehicles/cars/traffic", "add N cars driving around", "put cars in a lane 15 m apart", "spawn the ego/hero vehicle", or "remove the vehicles".
license: MIT
compatibility: Any OS with the CARLA PythonAPI installed for the active interpreter and a reachable, already-running CARLA server. Does NOT need UE4_ROOT or sync mode. Tested against CARLA 0.9.16.
metadata:
  prerequisites: scripts/check_env.sh
  reference: references/vehicles.md
---

# Spawn autopilot vehicles

Populate the roads with self-driving traffic. Vehicles are placed at the map's
predefined **spawn points** and, by default, handed to the **Traffic Manager**
autopilot at spawn time so they drive the road network autonomously. `destroy`
removes them.

Works in async mode (the default); sync is optional and only needs the TM put in
sync too — which `spawn` does automatically when the world is synchronous.

## Instructions

```
Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: Spawn N vehicles (they start driving on autopilot immediately)
- [ ] Step 3: Verify visually / via the world-data skill; spawn reports its count
- [ ] Step 4: Destroy when done
```

Commands need `CARLA_HOST`/`CARLA_PORT`/`TM_PORT` from `scripts/env.sh`.
**Negative coordinates:** pass `--at` with an `=` (`--at=-24,-57,0.6`) so the
leading minus isn't parsed as a flag.

### Step 1: Check prerequisites

```bash
bash scripts/check_env.sh
```

### Step 2-4: Spawn / list / destroy

```bash
source scripts/env.sh

# 40 vehicles driving around on autopilot
python3 scripts/vehicles.py spawn --count 40

# four-wheeled cars only, reproducible
python3 scripts/vehicles.py spawn --count 30 --safe --seed 42

# only Teslas, parked (no autopilot)
python3 scripts/vehicles.py spawn --count 10 --filter 'vehicle.tesla.*' --no-autopilot

# 5 vehicles in one lane, 15 m apart, starting near (x,y,z)
python3 scripts/vehicles.py line --at 30,20,0 --count 5 --gap 15
# ...as a static queue (no autopilot), laid behind the point
python3 scripts/vehicles.py line --at 30,20,0 --count 5 --gap 15 --no-autopilot --backward

# one hero/ego vehicle (autopilot off) — the anchor for control/sensors/telemetry
python3 scripts/vehicles.py ego --at 30,20,0        # prints its actor id + role=hero

python3 scripts/vehicles.py destroy                 # remove all vehicles
python3 scripts/vehicles.py destroy --filter 'vehicle.tesla.*'   # a subset (keeps the ego)
```

### Verify

The `spawn` command reports how many vehicles it created. Count is capped at the
number of spawn points (one vehicle per point); it reports if it capped or if some
spawns failed (occupied points) — both normal. Count/inspect live actors with the
world-data skill.

## Examples

**Example 1: fill the roads**

User says: "spawn 50 cars driving around"

`spawn --count 50`. They immediately drive on autopilot; the command reports how
many spawned.

**Example 2: reproducible car-only traffic**

User says: "same 30 cars every run, no motorbikes"

`spawn --count 30 --safe --seed 42`.

**Example 3: a queue in one lane**

User says: "put 5 cars in the same lane on this road, 15 m apart"

Find a point on the road (map-waypoints, or a known location), then
`line --at <x,y,z> --count 5 --gap 15`. They spawn in-lane 15 m apart and drive
off on autopilot; add `--no-autopilot` for a stationary queue.

**Example 4: clean up**

User says: "clear the traffic"

`destroy`.

## Troubleshooting

**Problem: fewer vehicles than requested**
Cause: count exceeds spawn points, or points were occupied.
Solution: expected; the map has a fixed number of spawn points (one car each).

**Problem: vehicles spawn but don't move**
Cause: world is in sync mode but the TM is not ticking, or `--no-autopilot`.
Solution: `spawn` sets the TM sync when the world is sync — then tick the world
(set-world-settings). Without `--no-autopilot` they drive in async immediately.

**Problem: vehicles jitter / freeze in sync mode**
Cause: world sync but TM async (mismatch).
Solution: keep both in sync (set-world-settings couples them; `spawn` also sets
TM sync). Use the same `--tm-port` throughout.

## Outputs

Live autopilot traffic on the server. No file. `destroy` removes all vehicles.

Detail (blueprint filtering, spawn-point capping, the autopilot hand-off, TM/sync
interaction, determinism) in [references/vehicles.md](references/vehicles.md).
