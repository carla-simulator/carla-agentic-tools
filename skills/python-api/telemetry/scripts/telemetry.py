#!/usr/bin/env python3
"""Read an actor's live telemetry: transform, velocity, acceleration, control.

Select the actor (resolve ambiguity with the world-data skill first):
    --id N | --role hero | --filter '*prius*' | --color 255,0,0
    | --nearest --near-id N | --nearest --near X,Y,Z

Commands:
    show                       one frame-consistent telemetry snapshot
    watch --seconds 10 [--hz 5]   stream telemetry over time

Reads are taken from a single `world.get_snapshot()` so transform, velocity,
acceleration and angular velocity all come from the SAME frame (calling the
per-actor getters separately can straddle two frames). For vehicles it also shows
control (throttle/steer/brake), front-wheel steer angle, and mass.

When several actors match and none is singled out, it errors and tells you to
narrow by a distinguishing attribute or use world-data. Connection from env.sh.
"""
from __future__ import annotations

import argparse
import math
import os
import time

import carla  # provided by the active interpreter; check_env.sh verifies this


def _world():
    c = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                     int(os.environ.get("CARLA_PORT", "2000")))
    c.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return c.get_world()


def _resolve(world, args) -> carla.Actor:
    actors = world.get_actors()
    if args.id is not None:
        a = actors.find(args.id)
        if a is None:
            raise SystemExit(f"no actor id {args.id}")
        return a
    matches = list(actors.filter(args.filter)) if args.filter else list(actors.filter("vehicle.*"))
    if args.role:
        matches = [a for a in matches if a.attributes.get("role_name", "") == args.role]
    if args.color:
        matches = [a for a in matches if a.attributes.get("color", "") == args.color]
    if args.nearest:
        ref = None
        if args.near:
            x, y, z = (float(v) for v in args.near.split(","))
            ref = carla.Location(x, y, z)
        elif args.near_id is not None:
            r = actors.find(args.near_id)
            ref = r.get_transform().location if r else None
        if ref is None:
            raise SystemExit("--nearest needs --near X,Y,Z or --near-id N")
        matches = [min(matches, key=lambda a: a.get_transform().location.distance(ref))] if matches else []
    if not matches:
        raise SystemExit("no matching actor")
    if len(matches) > 1:
        raise SystemExit(f"{len(matches)} actors match — narrow by a distinguishing attribute "
                         "(--color/--role/--filter) or --nearest --near-id N, or resolve the id "
                         "with the world-data skill and pass --id")
    return matches[0]


def _mag(v):
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)


def _print(world, actor):
    # One snapshot -> all kinematics from the same frame.
    snap = world.get_snapshot()
    a = snap.find(actor.id)
    if a is None:
        print("  (actor not in snapshot — destroyed?)"); return
    t = a.get_transform(); v = a.get_velocity(); ac = a.get_acceleration(); w = a.get_angular_velocity()
    print(f"  frame={snap.frame}")
    print(f"  location=({t.location.x:.2f},{t.location.y:.2f},{t.location.z:.2f}) "
          f"rotation=(pitch={t.rotation.pitch:.1f},yaw={t.rotation.yaw:.1f},roll={t.rotation.roll:.1f})")
    print(f"  velocity=({v.x:.2f},{v.y:.2f},{v.z:.2f}) speed={_mag(v)*3.6:.1f} km/h")
    print(f"  acceleration={_mag(ac):.2f} m/s^2  angular_velocity={_mag(w):.2f} rad/s")
    if actor.type_id.startswith("vehicle."):
        c = actor.get_control()
        print(f"  control: throttle={c.throttle:.2f} steer={c.steer:.2f} brake={c.brake:.2f} "
              f"gear={c.gear} reverse={c.reverse}")
        try:
            fl = actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FL_Wheel)
            fr = actor.get_wheel_steer_angle(carla.VehicleWheelLocation.FR_Wheel)
            print(f"  wheel steer: FL={fl:.1f} deg FR={fr:.1f} deg   mass={actor.get_physics_control().mass:.0f} kg")
        except RuntimeError:
            pass


def cmd_show(args):
    world = _world()
    actor = _resolve(world, args)
    print(f"telemetry id={actor.id} ({actor.type_id}):")
    _print(world, actor)


def cmd_watch(args):
    world = _world()
    actor = _resolve(world, args)
    period = 1.0 / args.hz
    end = time.time() + args.seconds
    print(f"watching id={actor.id} ({actor.type_id}) for {args.seconds}s at {args.hz} Hz:")
    while time.time() < end:
        _print(world, actor)
        print("  ---")
        time.sleep(period)


def _sel(sp):
    sp.add_argument("--id", type=int); sp.add_argument("--role"); sp.add_argument("--filter")
    sp.add_argument("--color", help="vehicle color attribute, e.g. 255,0,0")
    sp.add_argument("--near"); sp.add_argument("--near-id", type=int)
    sp.add_argument("--nearest", action="store_true", help="pick the closest to --near/--near-id")
    return sp


def main() -> None:
    p = argparse.ArgumentParser(description="Read a CARLA actor's telemetry.")
    sub = p.add_subparsers(dest="cmd", required=True)
    _sel(sub.add_parser("show", help="one telemetry snapshot")).set_defaults(func=cmd_show)
    pw = _sel(sub.add_parser("watch", help="stream telemetry"))
    pw.add_argument("--seconds", type=float, default=10.0); pw.add_argument("--hz", type=float, default=5.0)
    pw.set_defaults(func=cmd_watch)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
