#!/usr/bin/env python3
"""Move the CARLA spectator camera, frame an actor, or follow one.

Commands:

    actors [--filter PATTERN]                 list actors (basis for "the ego" etc.)
    move   --at X,Y,Z [--pitch P --yaw Y --roll R]      set the spectator transform
    look   --view chase|first|top|front <selector>      one-shot: frame an actor
    follow --view chase|first|top|front <selector> [--seconds 20]   track it live

Actor <selector> (one of):
    --id N            actor id
    --role hero       match attributes['role_name'] (the ego is usually 'hero')
    --filter PATTERN  match type_id, wildcards ok (e.g. '*prius*', 'vehicle.*.*')

Views: chase = 3rd-person behind+above; first = driver/1st-person; top = bird's
eye; front = ahead looking back. Offsets are tunable (--distance/--height/--pitch).

IMPORTANT: the spectator cannot be *attached* to an actor (the API has no reparent
for it). `follow` emulates attachment by re-setting the spectator's transform on
every world tick via world.on_tick, for --seconds. In synchronous mode it updates
only while something ticks the world.

Connection comes from the environment (see env.sh): CARLA_HOST/PORT/TIMEOUT.
"""
from __future__ import annotations

import argparse
import math
import os
import time

import carla  # provided by the active interpreter; check_env.sh verifies this

# View offset defaults (metres / degrees), justified for a car-sized actor.
VIEWS = {
    "chase": dict(distance=6.0, height=2.5, pitch=-12.0),  # behind + above, angled down
    "first": dict(distance=0.5, height=1.2, pitch=0.0),    # driver eye, looking forward
    "top":   dict(distance=0.0, height=25.0, pitch=-90.0), # straight down
    "front": dict(distance=8.0, height=2.0, pitch=-8.0),   # ahead, looking back
}


def _client() -> carla.Client:
    client = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                          int(os.environ.get("CARLA_PORT", "2000")))
    client.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return client


def _resolve_actor(world, args) -> carla.Actor:
    """Pick one actor from --id / --role / --filter; nearest to the spectator on ties."""
    actors = world.get_actors()
    if args.id is not None:
        a = actors.find(args.id)
        if a is None:
            raise SystemExit(f"no actor with id {args.id}")
        return a
    if args.role:
        matches = [a for a in actors if a.attributes.get("role_name", "") == args.role]
        if not matches:
            raise SystemExit(f"no actor with role_name={args.role!r} (try `actors` to list)")
    elif args.filter:
        matches = list(actors.filter(args.filter))
        if not matches:
            raise SystemExit(f"no actor matching type_id {args.filter!r} (try `actors`)")
    else:
        raise SystemExit("need a selector: --id, --role, or --filter")
    if len(matches) == 1:
        return matches[0]
    # disambiguate by nearest to the current spectator position
    sp = world.get_spectator().get_transform().location
    matches.sort(key=lambda a: a.get_transform().location.distance(sp))
    print(f"note: {len(matches)} actors matched; using nearest id={matches[0].id} "
          f"({matches[0].type_id})")
    return matches[0]


def _view_transform(target: carla.Transform, view: str, distance, height, pitch) -> carla.Transform:
    """Compute a spectator transform for the given view relative to `target`."""
    loc, rot = target.location, target.rotation
    fwd = target.get_forward_vector()  # unit vector along the actor's yaw
    if view == "top":
        return carla.Transform(carla.Location(loc.x, loc.y, loc.z + height),
                               carla.Rotation(pitch=-90.0, yaw=rot.yaw))
    if view == "first":
        pos = carla.Location(loc.x + fwd.x * distance, loc.y + fwd.y * distance, loc.z + height)
        return carla.Transform(pos, carla.Rotation(pitch=pitch, yaw=rot.yaw))
    if view == "front":
        pos = carla.Location(loc.x + fwd.x * distance, loc.y + fwd.y * distance, loc.z + height)
        return carla.Transform(pos, carla.Rotation(pitch=pitch, yaw=rot.yaw + 180.0))
    # chase (default): behind and above, looking forward along the actor
    pos = carla.Location(loc.x - fwd.x * distance, loc.y - fwd.y * distance, loc.z + height)
    return carla.Transform(pos, carla.Rotation(pitch=pitch, yaw=rot.yaw))


def _offsets(args) -> dict:
    o = dict(VIEWS[args.view])
    if args.distance is not None: o["distance"] = args.distance
    if args.height is not None:   o["height"] = args.height
    if args.pitch is not None:    o["pitch"] = args.pitch
    return o


def cmd_actors(args):
    world = _client().get_world()
    actors = world.get_actors().filter(args.filter) if args.filter else world.get_actors()
    rows = [a for a in actors if not a.type_id.startswith(("traffic.", "spectator"))] if not args.all else list(actors)
    print(f"{len(rows)} actor(s)" + (f" matching {args.filter!r}" if args.filter else "") + ":")
    for a in rows:
        l = a.get_transform().location
        role = a.attributes.get("role_name", "")
        print(f"  id={a.id:5d}  {a.type_id:32s}  role={role or '-':8s}  ({l.x:.0f},{l.y:.0f},{l.z:.0f})")


def cmd_move(args):
    world = _client().get_world()
    x, y, z = (float(v) for v in args.at.split(","))
    tf = carla.Transform(carla.Location(x, y, z),
                         carla.Rotation(pitch=args.pitch, yaw=args.yaw, roll=args.roll))
    world.get_spectator().set_transform(tf)
    print(f"spectator moved to ({x},{y},{z}) pitch={args.pitch} yaw={args.yaw}")


def cmd_look(args):
    world = _client().get_world()
    target = _resolve_actor(world, args)
    o = _offsets(args)
    world.get_spectator().set_transform(_view_transform(target.get_transform(), args.view, **o))
    print(f"spectator set to {args.view} view of id={target.id} ({target.type_id})")


def cmd_follow(args):
    world = _client().get_world()
    target = _resolve_actor(world, args)
    spectator = world.get_spectator()
    o = _offsets(args)
    print(f"following id={target.id} ({target.type_id}) in {args.view} view for {args.seconds}s "
          f"(Ctrl-C to stop early)")

    def _update(_snapshot):
        try:
            spectator.set_transform(_view_transform(target.get_transform(), args.view, **o))
        except RuntimeError:
            pass  # target gone this frame; next tick or timeout will end it

    cid = world.on_tick(_update)   # re-aim every world tick -> smooth follow
    try:
        time.sleep(args.seconds)
    except KeyboardInterrupt:
        pass
    finally:
        world.remove_on_tick(cid)
    print("stopped following")


def _add_selector(sp):
    sp.add_argument("--id", type=int)
    sp.add_argument("--role")
    sp.add_argument("--filter")


def _add_view(sp):
    sp.add_argument("--view", choices=tuple(VIEWS), default="chase")
    sp.add_argument("--distance", type=float, help="override view distance (m)")
    sp.add_argument("--height", type=float, help="override view height (m)")
    sp.add_argument("--pitch", type=float, help="override view pitch (deg)")


def main() -> None:
    p = argparse.ArgumentParser(description="Move/aim/follow the CARLA spectator.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("actors", help="list actors (for NL resolution)")
    pa.add_argument("--filter", help="type_id pattern, wildcards ok")
    pa.add_argument("--all", action="store_true", help="include traffic + spectator")
    pa.set_defaults(func=cmd_actors)

    pm = sub.add_parser("move", help="set the spectator transform directly")
    pm.add_argument("--at", required=True, help="X,Y,Z")
    pm.add_argument("--pitch", type=float, default=-15.0)
    pm.add_argument("--yaw", type=float, default=0.0)
    pm.add_argument("--roll", type=float, default=0.0)
    pm.set_defaults(func=cmd_move)

    pl = sub.add_parser("look", help="one-shot: frame an actor in a view")
    _add_selector(pl); _add_view(pl); pl.set_defaults(func=cmd_look)

    pf = sub.add_parser("follow", help="track an actor live for --seconds")
    _add_selector(pf); _add_view(pf)
    pf.add_argument("--seconds", type=float, default=20.0)
    pf.set_defaults(func=cmd_follow)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
