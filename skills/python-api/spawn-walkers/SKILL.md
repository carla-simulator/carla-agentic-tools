---
name: spawn-walkers
description: Spawns pedestrians that wander autonomously via WalkerAIController, and destroys them in the correct order. Pairs each walker.pedestrian.* with a controller.ai.walker, places them on the navigation mesh, and sends them to random navmesh points at walking speed. Use when the user asks to "spawn pedestrians/walkers", "add people/crowds", "make pedestrians walk around", or "remove the walkers". Works in async mode; sync not required.
license: MIT
compatibility: Any OS with the CARLA PythonAPI installed for the active interpreter and a reachable, already-running CARLA server WITH a pedestrian navmesh for the loaded map. Does NOT need UE4_ROOT or sync mode. Tested against CARLA 0.9.16.
metadata:
  prerequisites: scripts/check_env.sh
  reference: references/walkers.md
---

# Spawn wandering pedestrians

Populate the map with pedestrians that walk around on their own. Each is a
`walker.pedestrian.*` body paired with a `controller.ai.walker` that steers it to
random points on the **navigation mesh**. The deliverable is a live, moving crowd;
`destroy` tears it down cleanly.

By default they wander **indefinitely**: on spawn every controller is `start()`ed,
given one random navmesh destination, and a random walking speed. That single
target is enough — CARLA's walker AI automatically picks a fresh random
destination each time a walker arrives (confirmed in LibCarla's nav code), so the
crowd roams forever with no re-targeting loop. Pass `--no-wander` for a stationary
crowd (controllers left unstarted).

This needs a navmesh — validate it first with the
[`debug-navmesh`](../debug-navmesh/SKILL.md) skill if walkers won't move. It works
in **async** mode (the default); sync is optional (for reproducible runs).

## Instructions

```
Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: (if walkers won't move) validate the navmesh — debug-navmesh
- [ ] Step 3: Spawn N walkers (they start wandering immediately, forever)
- [ ] Step 4: Verify visually / via the world-data skill; spawn reports its count
- [ ] Step 5: Destroy (controllers first, then walkers) when done
```

Commands need `CARLA_HOST`/`CARLA_PORT` from `scripts/env.sh`.

### Step 1: Check prerequisites

```bash
bash scripts/check_env.sh
```

### Step 3-5: Spawn / roam / destroy

```bash
source scripts/env.sh

# 30 pedestrians, wandering indefinitely at 1.0-1.8 m/s
python3 scripts/walkers.py spawn --count 30

# reproducible placement (still wanders forever)
python3 scripts/walkers.py spawn --count 50 --seed 42

# more road-crossing, faster walkers
python3 scripts/walkers.py spawn --count 20 --cross-factor 0.4 --speed-min 1.4 --speed-max 2.2

# a stationary crowd (no autonomous movement)
python3 scripts/walkers.py spawn --count 20 --no-wander

python3 scripts/walkers.py destroy        # correct-order teardown
```

### Verify

The `spawn` command reports how many walkers + controllers it created (they
should be equal). Watch them move on a rendered server; count/inspect live actors
with the world-data skill. Fewer than requested is normal at high counts (navmesh
points collide) — the spawn command reports the shortfall.

## Examples

**Example 1: add a crowd**

User says: "spawn 40 pedestrians walking around"

`spawn --count 40`. They immediately head to random navmesh points; the command
reports how many spawned.

**Example 2: a reproducible pedestrian scene**

User says: "same 25 pedestrians every run"

`spawn --count 25 --seed 7`. They wander indefinitely; the seed fixes placement.

**Example 3: clean up**

User says: "remove all the pedestrians"

`destroy` — stops and removes controllers first, then the walkers.

## Troubleshooting

**Problem: walkers spawn but stand still**
Cause: no navmesh, or controllers never started/targeted.
Solution: validate with debug-navmesh; this skill starts + targets them, so a
still crowd usually means a missing navmesh.

**Problem: far fewer spawned than requested**
Cause: random navmesh points collide at high counts.
Solution: expected; retry, lower the count, or spawn in batches.

**Problem: errors / ghost actors after cleanup**
Cause: walkers destroyed before their controllers (wrong order).
Solution: always use `destroy` here — it stops controllers and removes them
first, then the walkers.

**Problem: pedestrians constantly walk into the road**
Cause: high `--cross-factor`.
Solution: lower it (default 0.1); 0 keeps them on sidewalks.

## Outputs

A live crowd of wandering pedestrians (walker + controller pairs) on the server.
No file. `destroy` removes them in the safe order.

Detail (the two-phase batch spawn, controller API, navmesh dependency, sync
optionality, destroy order) in [references/walkers.md](references/walkers.md).
