#!/usr/bin/env python3
"""Spawn and attach sensors to a CARLA actor, and destroy them.

Commands:
    types                                  list sensor blueprints
    spawn --type camera.rgb [--attach-to hero | --parent-id N]
          [--x 1.5 --y 0 --z 2.4 --pitch 0 --yaw 0 --roll 0]
          [--attachment Rigid|SpringArm] [--attr image_size_x=800 --attr fov=90]
                                           spawn one sensor; prints its id
    destroy [--filter sensor.*]            remove sensors

`--type` accepts a short name (camera.rgb, lidar.ray_cast, other.gnss) or the full
`sensor.*` id. The transform is RELATIVE to the parent when attached (a dashcam
default of x=1.5, z=2.4). Attach to the ego with `--attach-to hero`, or any actor
with `--parent-id`. `SpringArm` gives a smooth (spring-damped) mount for chase
cams; `Rigid` is fixed.

Repeat `--attr key=value` for blueprint attributes: cameras take image_size_x,
image_size_y, fov, sensor_tick; lidar takes range, points_per_second, channels,
rotation_frequency; etc.

The spawned sensor persists as an actor (its id is printed) — feed that id to the
read-sensor skill to save or view its data. Connection from env.sh.
"""
from __future__ import annotations

import argparse
import os

import carla  # provided by the active interpreter; check_env.sh verifies this


def _client():
    c = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                     int(os.environ.get("CARLA_PORT", "2000")))
    c.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return c


def _full_type(t: str) -> str:
    return t if t.startswith("sensor.") else f"sensor.{t}"


def cmd_types(_):
    bl = _client().get_world().get_blueprint_library().filter("sensor.*")
    print("sensor blueprints:")
    for b in bl:
        print(f"  {b.id}")


def cmd_spawn(args):
    world = _client().get_world()
    bp = world.get_blueprint_library().find(_full_type(args.type))
    for kv in args.attr or []:
        k, _, v = kv.partition("=")
        if not bp.has_attribute(k):
            raise SystemExit(f"{bp.id} has no attribute {k!r}")
        bp.set_attribute(k, v)

    parent = None
    if args.parent_id is not None:
        parent = world.get_actors().find(args.parent_id)
        if parent is None:
            raise SystemExit(f"no actor id {args.parent_id}")
    elif args.attach_to:
        matches = [a for a in world.get_actors().filter("vehicle.*")
                   if a.attributes.get("role_name", "") == args.attach_to]
        if not matches:
            raise SystemExit(f"no vehicle with role_name={args.attach_to!r} "
                             "(spawn an ego with spawn-vehicles, or use --parent-id)")
        parent = matches[0]

    tf = carla.Transform(carla.Location(args.x, args.y, args.z),
                         carla.Rotation(pitch=args.pitch, yaw=args.yaw, roll=args.roll))
    attach = getattr(carla.AttachmentType, args.attachment)
    if parent is not None:
        sensor = world.spawn_actor(bp, tf, attach_to=parent, attachment_type=attach)
        where = f"attached to id={parent.id} ({parent.type_id}) at rel ({args.x},{args.y},{args.z})"
    else:
        sensor = world.spawn_actor(bp, tf)   # world-fixed sensor
        where = f"world-fixed at ({args.x},{args.y},{args.z})"
    print(f"spawned {sensor.type_id} id={sensor.id} {where}")
    print(f"  view/save it with: read-sensor --id {sensor.id}")


def cmd_destroy(args):
    client = _client()
    sensors = list(client.get_world().get_actors().filter(args.filter))
    for s in sensors:
        if s.is_listening:
            s.stop()
        s.destroy()
    print(f"destroyed {len(sensors)} sensors matching {args.filter!r}")


def main() -> None:
    p = argparse.ArgumentParser(description="Spawn/attach/destroy CARLA sensors.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("types", help="list sensor blueprints").set_defaults(func=cmd_types)

    ps = sub.add_parser("spawn", help="spawn a sensor")
    ps.add_argument("--type", required=True, help="e.g. camera.rgb, lidar.ray_cast, other.imu")
    ps.add_argument("--attach-to", help="parent vehicle role_name (e.g. hero)")
    ps.add_argument("--parent-id", type=int, help="parent actor id (alternative to --attach-to)")
    ps.add_argument("--x", type=float, default=1.5); ps.add_argument("--y", type=float, default=0.0)
    ps.add_argument("--z", type=float, default=2.4)
    ps.add_argument("--pitch", type=float, default=0.0); ps.add_argument("--yaw", type=float, default=0.0)
    ps.add_argument("--roll", type=float, default=0.0)
    ps.add_argument("--attachment", choices=("Rigid", "SpringArm", "SpringArmGhost"), default="Rigid")
    ps.add_argument("--attr", action="append", help="blueprint attribute key=value (repeatable)")
    ps.set_defaults(func=cmd_spawn)

    pd = sub.add_parser("destroy", help="destroy sensors")
    pd.add_argument("--filter", default="sensor.*")
    pd.set_defaults(func=cmd_destroy)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
