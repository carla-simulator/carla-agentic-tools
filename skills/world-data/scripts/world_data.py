#!/usr/bin/env python3
"""Query the live CARLA world: actors, level bounding boxes, raycast, snapshot.

This is the RESOLVER skill — use it to turn an ambiguous description ("a prius",
"the nearest walker", "the 3rd one") into a concrete actor id that the action
skills (telemetry, bounding-boxes, control-vehicle, control-spectator) take.

Commands:
    actors [--filter vehicle.*] [--role hero] [--color 255,0,0]
           [--near X,Y,Z | --near-id N] [--nearest] [--full] [--limit N]
                                           find actors by attribute / nearest
    snapshot                               frame/timestamp/actor count
    level-bbox --label Buildings [--limit]  static level bounding boxes by label
    raycast --from X,Y,Z --to X,Y,Z        semantic points a ray crosses
    ground  --at X,Y,Z [--search 1000]     drop a point to the ground below it

Identify by STABLE attributes (id, type, role, color) or the spatial predicate
--nearest (closest to --near/--near-id). There is NO rank/order among peer actors,
so no "Nth". E.g. the prius nearest the ego:
`actors --filter '*prius*' --near-id <ego> --nearest` prints exactly one id;
"the red prius": `actors --filter '*prius*' --color 255,0,0`.

Connection from env.sh: CARLA_HOST/PORT/TIMEOUT.
"""
from __future__ import annotations

import argparse
import math
import os

import carla  # provided by the active interpreter; check_env.sh verifies this


def _world():
    c = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                     int(os.environ.get("CARLA_PORT", "2000")))
    c.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return c.get_world()


def _speed(a):  # m/s magnitude
    v = a.get_velocity()
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def cmd_actors(args):
    world = _world()
    actors = world.get_actors()
    rows = list(actors.filter(args.filter)) if args.filter else list(actors)
    if args.role:
        rows = [a for a in rows if a.attributes.get("role_name", "") == args.role]
    if args.color:
        rows = [a for a in rows if a.attributes.get("color", "") == args.color]
    if not args.all:
        rows = [a for a in rows if not a.type_id.startswith(("traffic.", "spectator", "sensor.other.v2x"))]

    # Optional spatial reference — a distance is shown for context and lets
    # --nearest pick the single closest. This is a predicate ("the closest one"),
    # NOT an ordering to index into: there is no meaningful rank among peers.
    ref = None
    if args.near:
        x, y, z = (float(v) for v in args.near.split(","))
        ref = carla.Location(x, y, z)
    elif args.near_id is not None:
        r = actors.find(args.near_id)
        if r is None:
            raise SystemExit(f"no actor id {args.near_id}")
        ref = r.get_transform().location

    def dist(a):
        return a.get_transform().location.distance(ref)

    if args.nearest:
        if ref is None:
            raise SystemExit("--nearest needs --near X,Y,Z or --near-id N")
        rows = [min(rows, key=dist)] if rows else []

    shown = rows[:args.limit] if args.limit else rows
    cap = f" (showing {len(shown)} of {len(rows)})" if len(shown) < len(rows) else ""
    print(f"{len(rows)} actor(s) match{cap}:")
    for a in shown:
        loc = a.get_transform().location
        role = a.attributes.get("role_name", "")
        color = a.attributes.get("color", "")
        d = f" dist={dist(a):.0f}m" if ref else ""
        cstr = f" color={color}" if color else ""
        print(f"  id={a.id:6d}  {a.type_id:34s} role={role or '-':8s}{cstr} "
              f"({loc.x:.0f},{loc.y:.0f},{loc.z:.0f}) speed={_speed(a)*3.6:.0f}km/h{d}")
        if args.full:
            bb = a.bounding_box
            attrs = ", ".join(f"{k}={v}" for k, v in sorted(a.attributes.items()))
            print(f"        size(LxWxH)={bb.extent.x*2:.1f}x{bb.extent.y*2:.1f}x{bb.extent.z*2:.1f}m"
                  f"  yaw={a.get_transform().rotation.yaw:.0f}")
            print(f"        attrs: {attrs}")
    print("  → identify by id (stable) or a distinguishing attr (color/role/type); "
          "positions move, so re-query for a fresh distance.")


def cmd_snapshot(args):
    world = _world()
    snap = world.get_snapshot()
    ts = snap.timestamp
    print(f"frame={snap.frame} elapsed={ts.elapsed_seconds:.2f}s delta={ts.delta_seconds:.4f}s "
          f"actors={len(world.get_actors())}")


def cmd_level_bbox(args):
    world = _world()
    label = getattr(carla.CityObjectLabel, args.label, None)
    if label is None:
        raise SystemExit(f"unknown label {args.label!r} (see toggle-env-objects `labels`)")
    bbs = world.get_level_bbs(label)
    print(f"{len(bbs)} level bounding box(es) for {args.label}:")
    for bb in bbs[:args.limit or 15]:
        print(f"  center=({bb.location.x:.0f},{bb.location.y:.0f},{bb.location.z:.0f}) "
              f"extent=({bb.extent.x:.1f},{bb.extent.y:.1f},{bb.extent.z:.1f})")
    if len(bbs) > (args.limit or 15):
        print(f"  ... and {len(bbs) - (args.limit or 15)} more")


def cmd_raycast(args):
    world = _world()
    a = carla.Location(*[float(v) for v in getattr(args, "from").split(",")])
    b = carla.Location(*[float(v) for v in args.to.split(",")])
    pts = world.cast_ray(a, b)
    print(f"{len(pts)} labelled point(s) along the ray:")
    for p in pts[:30]:
        print(f"  ({p.location.x:.1f},{p.location.y:.1f},{p.location.z:.1f})  {p.label}")


def cmd_ground(args):
    world = _world()
    x, y, z = (float(v) for v in args.at.split(","))
    p = world.project_point(carla.Location(x, y, z), carla.Vector3D(0, 0, -1), args.search)
    if p is None:
        print(f"no ground within {args.search} m below ({x},{y},{z})")
        return
    print(f"ground under ({x},{y},{z}): ({p.location.x:.2f},{p.location.y:.2f},"
          f"{p.location.z:.2f})  label={p.label}")


def main() -> None:
    p = argparse.ArgumentParser(description="Query the live CARLA world.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("actors", help="find actors by attribute / nearest (the resolver)")
    pa.add_argument("--filter", help="type_id pattern, e.g. '*prius*'")
    pa.add_argument("--role", help="match attributes['role_name'] (e.g. hero)")
    pa.add_argument("--color", help="match a vehicle's color attribute, e.g. 255,0,0")
    pa.add_argument("--near", help="reference point X,Y,Z (shows distance)")
    pa.add_argument("--near-id", type=int, help="reference actor id (shows distance)")
    pa.add_argument("--nearest", action="store_true", help="return only the single closest to --near/--near-id")
    pa.add_argument("--limit", type=int, help="display cap only (truncates, not a selection)")
    pa.add_argument("--all", action="store_true", help="include traffic/spectator/etc")
    pa.add_argument("--full", action="store_true",
                    help="show every identifying field (all attrs, size, yaw)")
    pa.set_defaults(func=cmd_actors)

    sub.add_parser("snapshot", help="frame/time/actor count").set_defaults(func=cmd_snapshot)

    pb = sub.add_parser("level-bbox", help="static level bounding boxes by label")
    pb.add_argument("--label", required=True); pb.add_argument("--limit", type=int)
    pb.set_defaults(func=cmd_level_bbox)

    pr = sub.add_parser("raycast", help="semantic points a ray crosses")
    pr.add_argument("--from", required=True); pr.add_argument("--to", required=True)
    pr.set_defaults(func=cmd_raycast)

    pg = sub.add_parser("ground", help="project a point to the ground")
    pg.add_argument("--at", required=True); pg.add_argument("--search", type=float, default=1000.0)
    pg.set_defaults(func=cmd_ground)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
