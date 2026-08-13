---
name: debug-draw
description: Draws debug overlays in a running CARLA world via world.debug — points, lines, arrows, bounding boxes, and text strings, each with a colour and lifetime. Use when the user asks to "draw/mark/highlight a point or box in the world", "visualise a path/waypoints", "label a location", or "show something on the map for debugging". Shapes are an overlay, not actors.
license: MIT
compatibility: Any OS with the CARLA PythonAPI installed for the active interpreter and a reachable, already-running CARLA server. Shapes are visible only in a rendered view (windowed or packaged server), not in -nullrhi headless. Tested against CARLA 0.9.16.
metadata:
  group: python-api
  prerequisites: scripts/check_env.sh
  reference: references/debug.md
---

# Draw CARLA debug shapes

Overlay primitives on the running world for visual debugging: points, lines,
arrows, boxes, text. They are drawn by the server as a transient overlay — **not
actors** — so they cannot be selected or deleted individually; they expire after
their `--life`. Other skills (e.g. `map-waypoints`) draw through this same
`world.debug` API.

## Instructions

```
Progress:
- [ ] Step 1: Check prerequisites (bash scripts/check_env.sh), clear FAILs
- [ ] Step 2: Draw the primitive(s) with a colour and lifetime
- [ ] Step 3: Confirm in a rendered view; redraw if it must persist in sync mode
```

Commands need `CARLA_HOST`/`CARLA_PORT` from `scripts/env.sh`. Coordinates are
world metres `X,Y,Z`; colours are `r,g,b` (0-255). **Negative coordinates:** use
the `=` form (`--at=-10,-5,1`, `--from=-3,0,1`) so a leading minus isn't read as
a flag.

### Step 1: Check prerequisites

```bash
bash scripts/check_env.sh
```

### Step 2: Draw

```bash
source scripts/env.sh

python3 scripts/debug_draw.py point  --at 10,20,1 --size 0.2 --color 0,255,0 --life 60
python3 scripts/debug_draw.py line   --from 0,0,1 --to 50,0,1 --thickness 0.2 --life 60
python3 scripts/debug_draw.py arrow  --from 0,0,1 --to 10,0,1 --color 0,0,255 --life 60
python3 scripts/debug_draw.py box    --center 30,30,1 --extent 2,4,1.5 --yaw 45 --life 60
python3 scripts/debug_draw.py text   --at 30,30,3 --text "junction 12" --color 255,255,0 --life 60
```

### Step 3: Confirm / persistence

Shapes render on a world **tick**, in a **rendered** view. Two gotchas:

- **Headless `-nullrhi` servers show nothing** — there is no render thread. Use a
  windowed or packaged server to see overlays.
- **Sync mode**: nothing appears until the client ticks, and `--life` is in
  simulation time. For an overlay that stays up while stepping, redraw each frame
  (or set `--life` longer than your tick interval).

## Examples

**Example 1: mark a spot**

User says: "mark world position (10, 20)"

`point --at 10,20,1 --size 0.2 --color 0,255,0 --life 120`.

**Example 2: label and box an object**

User says: "put a box and a label around (30,30)"

`box --center 30,30,1 --extent 2,4,1.5` then `text --at 30,30,3 --text "target"`.

## Troubleshooting

**Problem: nothing shows up**
Cause: headless `-nullrhi` server (no rendering), or sync mode without a tick.
Solution: run a windowed/packaged server; in sync mode tick the world.

**Problem: shape vanishes immediately**
Cause: very small `--life`, or a single-frame draw in sync mode.
Solution: raise `--life`, or redraw each frame for a persistent overlay.

**Problem: I can't delete a shape**
Cause: debug shapes are not actors.
Solution: they expire on their own; use a short `--life`, or reload the world.

## Outputs

Transient visual overlay in the rendered world. No file, no persistent actor.

Detail (each primitive's parameters, colour/lifetime semantics, sync-mode
behaviour) in [references/debug.md](references/debug.md).
