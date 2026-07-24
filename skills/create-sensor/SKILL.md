---
name: create-sensor
description: Spawns and attaches sensors on a running CARLA server — cameras (rgb/depth/semantic/instance/optical-flow/normals), lidar, radar, IMU, GNSS, collision/lane-invasion/obstacle — to the ego or any actor, with a mount transform and blueprint attributes (resolution, fov, sensor_tick, lidar range/points, …). Use when the user asks to "add a camera/lidar/sensor", "put a dashcam on the ego", "attach a depth camera", or "mount a sensor". Prints the sensor id; read its data with the read-sensor skill.
license: MIT
compatibility: Any OS with the CARLA PythonAPI installed for the active interpreter and a reachable, already-running CARLA server (and an actor to attach to, for attached sensors). Does NOT need UE4_ROOT. Tested against CARLA 0.9.16.
metadata:
  prerequisites: scripts/check_env.sh
  reference: references/sensors.md
---

# Create a sensor

Spawn a sensor and (usually) attach it to a vehicle so it moves with it. The
sensor persists as an actor; its **id** is printed so the
[`read-sensor`](../read-sensor/SKILL.md) skill can save or display its data. This
skill is placement/lifecycle only — reading is the other skill.

## Instructions

```
Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: Have a parent actor if attaching (spawn-vehicles ego)
- [ ] Step 3: Spawn the sensor with a type, mount transform, and attributes
- [ ] Step 4: Note the printed id; read it with read-sensor; destroy when done
```

Commands need `CARLA_HOST`/`CARLA_PORT` from `scripts/env.sh`.

### Step 1: Check prerequisites

```bash
bash scripts/check_env.sh
```

### Step 3: Spawn

```bash
source scripts/env.sh

python3 scripts/sensors.py types                     # list sensor blueprints

# an 800x600 dashcam on the ego (default mount x=1.5, z=2.4)
python3 scripts/sensors.py spawn --type camera.rgb --attach-to hero \
    --attr image_size_x=800 --attr image_size_y=600 --attr fov=90

# a lidar on the ego roof
python3 scripts/sensors.py spawn --type lidar.ray_cast --attach-to hero --z 2.5 \
    --attr range=50 --attr points_per_second=200000 --attr rotation_frequency=20

# a depth camera; a GNSS; a collision sensor
python3 scripts/sensors.py spawn --type camera.depth --attach-to hero
python3 scripts/sensors.py spawn --type other.gnss --attach-to hero
python3 scripts/sensors.py spawn --type other.collision --attach-to hero

python3 scripts/sensors.py destroy                   # remove all sensors
```

`--attach-to <role>` attaches to that vehicle (ego = `hero`); `--parent-id N`
attaches to any actor; omit both for a world-fixed sensor. `--attachment SpringArm`
gives a smooth chase mount. Repeat `--attr key=value` for blueprint attributes.

## Examples

**Example 1: dashcam on the ego**

User says: "put a camera on the ego"

Spawn an ego (spawn-vehicles `ego`), then `spawn --type camera.rgb --attach-to hero`.
Note the id, then `read-sensor show --id <id>`.

**Example 2: a lidar dataset rig**

User says: "add a lidar for capturing point clouds"

`spawn --type lidar.ray_cast --attach-to hero --attr range=100 --attr points_per_second=500000`,
then `read-sensor save --id <id> --out ./lidar`.

## Troubleshooting

**Problem: "no vehicle with role hero"**
Cause: nothing to attach to.
Solution: spawn an ego (spawn-vehicles), or use `--parent-id`, or omit to place a
world-fixed sensor.

**Problem: "<bp> has no attribute X"**
Cause: wrong attribute for that sensor type.
Solution: `types` then check the blueprint; cameras use image_size_x/y/fov,
lidar uses range/points_per_second/channels/rotation_frequency.

**Problem: attached camera clips through the car / bad angle**
Cause: mount transform is relative to the parent.
Solution: adjust `--x/--y/--z/--pitch`; a windshield cam is ~x=1.5, z=1.3.

## Outputs

A sensor actor on the server (id printed), attached or world-fixed. No data yet —
attach a listener with the read-sensor skill. `destroy` removes sensors.

Detail (sensor families, attributes, attachment types, sensor_tick) in
[references/sensors.md](references/sensors.md).
