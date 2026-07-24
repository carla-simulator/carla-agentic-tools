---
name: read-sensor
description: Listens to a CARLA sensor and either saves its data to files, shows it live in a window, or prints a one-shot summary. Cameras save as PNG (depth/semantic auto-colourised) and display in a pygame window; lidar saves as .ply and shows as a top-down scatter; IMU/GNSS/radar/collision stream to JSONL or the console. Use when the user asks to "show/view the camera", "display the lidar", "save the sensor data / capture a dataset", or "what is this sensor reading". Select the sensor by id, type, or the actor it's attached to.
license: MIT
compatibility: Any OS with the CARLA PythonAPI, numpy, and (for windows) pygame installed for the active interpreter, and a reachable running CARLA server with a sensor. A window needs a display; saving/summary work headless. Tested against CARLA 0.9.16.
metadata:
  requires: create-sensor
  prerequisites: scripts/check_env.sh
  reference: references/read-sensor.md
---

# Read a sensor

Point this at an existing sensor (make one with [`create-sensor`](../create-sensor/SKILL.md))
and either **show** it in a window, **save** its stream to disk, or get a one-shot
**info** summary. The goal is: select a sensor → see it.

Selector (any one): `--id N` · `--type sensor.camera.rgb` · `--attached-to hero`.

## Instructions

```
Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: Make sure the sensor exists (create-sensor) and the world is ticking
- [ ] Step 3: info (sanity) → show (window) or save (dataset)
```

Commands need `CARLA_HOST`/`CARLA_PORT` from `scripts/env.sh`.

### Step 1: Check prerequisites

```bash
bash scripts/check_env.sh
```

### Step 3: Read

```bash
source scripts/env.sh

# quick sanity: one reading + summary
python3 scripts/read_sensor.py info --id 123
# or by the actor it's on / by type
python3 scripts/read_sensor.py info --attached-to hero --type camera.rgb

# LIVE WINDOW (cameras + lidar); 0 = until you close it
python3 scripts/read_sensor.py show --id 123 --seconds 30

# SAVE a dataset: PNGs for cameras, .ply for lidar, JSONL for imu/gnss/…
python3 scripts/read_sensor.py save --id 123 --out ./capture --seconds 10
python3 scripts/read_sensor.py save --id 123 --out ./capture --frames 50

# MULTI-SENSOR: tile several cameras/lidars in one window
python3 scripts/read_sensor.py grid --ids 123,124,125 --seconds 30
```

## Examples

**Example 1: see the ego's camera**

User says: "show me the ego's camera"

`create-sensor spawn --type camera.rgb --attach-to hero` (note the id), then
`read_sensor.py show --id <id>`. A window opens with the live feed.

**Example 2: capture a short dataset**

User says: "save 5 seconds from the front camera"

`save --id <id> --out ./front --seconds 5` → numbered PNGs in ./front.

**Example 3: what is the GNSS reading?**

User says: "what's the GPS saying?"

`info --type other.gnss --attached-to hero` → one line with lat/lon/alt.

## Troubleshooting

**Problem: `info` times out / no data**
Cause: the world isn't advancing (sync mode, no ticks) or `sensor_tick` is large.
Solution: tick the world (set-world-settings) or run async; lower `sensor_tick`.

**Problem: `show` errors about display / no window**
Cause: no display (headless), or pygame missing.
Solution: run where there's a display; on a headless box use `save` instead. The
window is client-side (independent of the server's own rendering).

**Problem: depth/semantic image looks wrong when saved raw**
Cause: those need a colour converter.
Solution: this skill auto-applies LogarithmicDepth / CityScapes for save and show.

**Problem: data stops when the command ends**
Cause: listening is a callback in this process; it ends with the command.
Solution: keep `show`/`save` running for the capture; the sensor itself persists.

## Outputs

- `save`: PNGs (cameras), `.ply` (lidar), or `data.jsonl` (imu/gnss/radar/events)
  under `--out`.
- `show`: a live window (no files).
- `info`: one summary line.

Detail (callbacks vs queues, sync-mode alignment, save formats, converters) in
[references/read-sensor.md](references/read-sensor.md).
