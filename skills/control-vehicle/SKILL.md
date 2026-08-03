---
name: control-vehicle
description: Directly drives a specific vehicle on a running CARLA server — raw VehicleControl (throttle/steer/brake/reverse/hand-brake), Ackermann speed control, vehicle lights, opening/closing doors, and physics-control tuning. Targets the ego by default. Use when the user asks to "drive/steer the car", "accelerate/brake/reverse", "set a target speed", "turn on the headlights/blinkers/brake lights", "open a door", or "change the vehicle's mass/drag/physics". This is manual control (autopilot off) — for TM-driven traffic use control-traffic.
license: MIT
compatibility: Any OS with the CARLA PythonAPI installed for the active interpreter and a reachable, already-running CARLA server with at least one vehicle. Does NOT need UE4_ROOT. Tested against CARLA 0.9.16.
metadata:
  prerequisites: scripts/check_env.sh
  reference: references/vehicle-control.md
---

# Control a vehicle directly

Drive one vehicle yourself: control input, Ackermann speed target, lights, doors,
physics. It targets **the ego** (`role_name = hero`) by default, or any vehicle by
`--id` / `--role` / `--filter`. This is **manual** control — `control` and
`ackermann` turn autopilot off first; for autonomous traffic use the
[`control-traffic`](../control-traffic/SKILL.md) skill instead.

## Instructions

```
Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: Ensure a target vehicle exists (spawn-vehicles ego)
- [ ] Step 3: Apply the command (control / ackermann / lights / door / physics)
- [ ] Step 4: Confirm on a rendered server; `stop` to halt manual driving
```

Commands need `CARLA_HOST`/`CARLA_PORT`/`TM_PORT` from `scripts/env.sh`.

### Step 1: Check prerequisites

```bash
bash scripts/check_env.sh
```

### Step 3: Control

```bash
source scripts/env.sh

# drive the ego forward for 3 s, then it brakes
python3 scripts/vehicle_control.py control --throttle 0.5 --hold 3

# turn while creeping forward
python3 scripts/vehicle_control.py control --throttle 0.3 --steer -0.4 --hold 2

# hold a target speed (built-in controller does throttle/brake for you)
python3 scripts/vehicle_control.py ackermann --speed 8

# lights: headlights + brake on; position off
python3 scripts/vehicle_control.py lights --on LowBeam,Brake --off Position
# left blinker on a specific car
python3 scripts/vehicle_control.py lights --filter '*prius*' --on LeftBlinker

# doors
python3 scripts/vehicle_control.py door --open FL,FR
python3 scripts/vehicle_control.py door --close All

# physics: read, then make it heavier / draggier
python3 scripts/vehicle_control.py physics --show
python3 scripts/vehicle_control.py physics --mass 2200 --drag 0.4

# emergency stop
python3 scripts/vehicle_control.py stop
```

### Step 4: Verify

Watch on a rendered server. A `VehicleControl` **persists** — the car keeps the
last input until you change it, so use `--hold` for a timed action or `stop` to
halt. `physics --show` reads back the applied values; `telemetry` overlays live
physics on screen.

## Examples

**Example 1: nudge the ego forward**

User says: "drive the car forward a bit"

`control --throttle 0.4 --hold 2` — it accelerates for 2 s then brakes.

**Example 2: hazard lights**

User says: "put the hazards on"

`lights --on LeftBlinker,RightBlinker` (both blinkers = hazards).

**Example 3: a heavier truck feel**

User says: "make the ego handle like it's loaded"

`physics --mass 2500 --drag 0.45`, then drive and compare.

## Troubleshooting

**Problem: the car won't respond to control**
Cause: autopilot is still on (TM overrides manual input).
Solution: `control`/`ackermann` disable autopilot automatically; if you set it via
another tool, ensure autopilot is off. Sync mode also needs a world tick to move.

**Problem: it drives off and won't stop**
Cause: `VehicleControl` persists (throttle stays applied).
Solution: `stop`, or use `--hold` for timed inputs.

**Problem: "no vehicle with role hero"**
Cause: no ego spawned.
Solution: spawn one with the spawn-vehicles `ego` command, or target `--id`/`--filter`.

**Problem: no door named Hood/Trunk**
Cause: 0.9.16 exposes only FL, FR, RL, RR, All.
Solution: use those; not all vehicle models animate every door.

## Outputs

Vehicle state on the server (motion, lights, doors, physics). No file. Verify on a
rendered view; `physics --show` reads values back.

Detail (VehicleControl vs Ackermann, light flags, door set, the physics fields) in
[references/vehicle-control.md](references/vehicle-control.md).
