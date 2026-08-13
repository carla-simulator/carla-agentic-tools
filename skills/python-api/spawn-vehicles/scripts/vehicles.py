#!/usr/bin/env python3
"""Spawn vehicles that drive themselves via autopilot, and destroy them cleanly.

Commands:

    spawn   --count 40 [--filter vehicle.*] [--safe] [--seed 42]
            [--tm-port 8000] [--no-autopilot]        spawn at map spawn points
    line    --at X,Y,Z --count 5 --gap 15 [--backward] [...]   a queue in one lane
    ego     [--at X,Y,Z] [--filter] [--autopilot] [--ros-name hero]
                                                     one hero vehicle, id printed
    destroy [--filter vehicle.*]                     remove all (or a subset)

`spawn` scatters vehicles across the map's predefined spawn points (one per
point). `line` places a row of vehicles in a SINGLE lane: it snaps --at to the
nearest driving lane and steps along it with the Waypoint API (`next(gap)`),
putting one vehicle every `--gap` metres — e.g. 5 cars 15 m apart in the same
lane. `--backward` lays them behind the start point instead of ahead.

By default vehicles are handed to the Traffic Manager autopilot at spawn time
(atomic SpawnActor.then(SetAutopilot)), so they drive off on their own;
`--no-autopilot` leaves them stationary (useful for a static queue). `--safe`
keeps only four-wheeled cars.

ROS 2 (only on a server started with --ros2, see run-carla-server): `ego` takes
--ros-name / --ros-frame-id / --no-ros-tf. Only a vehicle whose role_name is
"hero" is registered with the ROS 2 layer — the server checks that explicitly, so
`spawn`/`line` traffic never publishes and never accepts ROS control commands.
Registering a hero creates the two control subscribers (vehicle_control_cmd,
ackermann_control_cmd). It does NOT publish a vehicle transform: rt/tf carries
sensor->parent transforms only, so map->hero must be broadcast by something else.
"""
from __future__ import annotations

import argparse
import os
import random

import carla  # provided by the active interpreter; check_env.sh verifies this

SpawnActor = carla.command.SpawnActor
SetAutopilot = carla.command.SetAutopilot
DestroyActor = carla.command.DestroyActor
FutureActor = carla.command.FutureActor


def _client() -> carla.Client:
    client = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                          int(os.environ.get("CARLA_PORT", "2000")))
    client.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return client


def _tm_and_sync(client, world, tm_port):
    """Get the TM and, if the world is sync, put the TM in sync too (autopilot needs it)."""
    tm = client.get_trafficmanager(tm_port)
    if world.get_settings().synchronous_mode:
        tm.set_synchronous_mode(True)
    return tm


def _vehicle_bps(world, filt, safe):
    bps = list(world.get_blueprint_library().filter(filt))
    if safe:
        bps = [b for b in bps if b.has_attribute("number_of_wheels")
               and int(b.get_attribute("number_of_wheels")) == 4]
    if not bps:
        raise SystemExit(f"no blueprints match filter {filt!r}" + (" with --safe" if safe else ""))
    return bps


def _configure(bp, role="autopilot"):
    if bp.has_attribute("color"):
        bp.set_attribute("color", random.choice(bp.get_attribute("color").recommended_values))
    bp.set_attribute("role_name", role)
    return bp


def _spawn_at(client, transforms, bps, autopilot, tm_port):
    """Batch-spawn one vehicle per transform; return the spawned actor ids."""
    batch = []
    for tf in transforms:
        cmd = SpawnActor(_configure(random.choice(bps)), tf)
        if autopilot:
            cmd = cmd.then(SetAutopilot(FutureActor, True, tm_port))  # atomic hand-off
        batch.append(cmd)
    return [r.actor_id for r in client.apply_batch_sync(batch, True) if not r.error]


def cmd_spawn(args):
    client = _client()
    world = client.get_world()
    if args.seed is not None:
        random.seed(args.seed)
        _tm_and_sync(client, world, args.tm_port).set_random_device_seed(args.seed)
    else:
        _tm_and_sync(client, world, args.tm_port)

    bps = _vehicle_bps(world, args.filter, args.safe)
    spawn_points = world.get_map().get_spawn_points()
    random.shuffle(spawn_points)
    want = min(args.count, len(spawn_points))
    if want < args.count:
        print(f"note: only {len(spawn_points)} spawn points; capping {args.count} -> {want} "
              "(one vehicle per point)")

    ids = _spawn_at(client, spawn_points[:want], bps, not args.no_autopilot, args.tm_port)
    mode = "parked (--no-autopilot)" if args.no_autopilot else f"on autopilot (TM :{args.tm_port})"
    print(f"spawned {len(ids)} vehicles at spawn points; {mode}")
    if len(ids) < want:
        print(f"  note: {want - len(ids)} failed (occupied points / collisions — normal)")


def cmd_line(args):
    client = _client()
    world = client.get_world()
    _tm_and_sync(client, world, args.tm_port)
    if args.seed is not None:
        random.seed(args.seed)

    x, y, z = (float(v) for v in args.at.split(","))
    start = world.get_map().get_waypoint(carla.Location(x, y, z),
                                         project_to_road=True, lane_type=carla.LaneType.Driving)
    if start is None:
        raise SystemExit(f"no driving lane near ({x},{y},{z})")

    # Walk the lane in gap-metre steps, collecting one waypoint per vehicle. next()/
    # previous() return a list (a fork gives several); take the first branch, and
    # stop early if the lane ends before we have enough.
    wps, wp = [start], start
    for _ in range(args.count - 1):
        nxt = wp.previous(args.gap) if args.backward else wp.next(args.gap)
        if not nxt:
            print(f"note: lane ended after {len(wps)} vehicle(s); "
                  f"{args.count - len(wps)} short of {args.count}")
            break
        wp = nxt[0]
        wps.append(wp)

    # Lift spawn z a little so the car drops onto the road rather than clipping it.
    transforms = [carla.Transform(
        carla.Location(w.transform.location.x, w.transform.location.y,
                       w.transform.location.z + args.z_offset),
        w.transform.rotation) for w in wps]

    bps = _vehicle_bps(world, args.filter, args.safe)
    ids = _spawn_at(client, transforms, bps, not args.no_autopilot, args.tm_port)
    mode = "parked" if args.no_autopilot else f"on autopilot (TM :{args.tm_port})"
    print(f"placed {len(ids)} vehicles in road {start.road_id} lane {start.lane_id}, "
          f"{args.gap} m apart {'behind' if args.backward else 'ahead of'} "
          f"({x:.0f},{y:.0f}); {mode}")
    if len(ids) < len(wps):
        print(f"  note: {len(wps) - len(ids)} failed to spawn (collision at a point — "
              "raise --gap or --z-offset)")


def cmd_ego(args):
    client = _client()
    world = client.get_world()
    bp = _configure(random.choice(_vehicle_bps(world, args.filter, safe=False)), role="hero")

    # ROS 2 naming: read once, at registration, so it must be set before spawn.
    # These attributes exist on every blueprint (ActorBlueprintFunctionLibrary).
    if args.ros_name:
        bp.set_attribute("ros_name", args.ros_name)
    if args.ros_frame_id:
        bp.set_attribute("ros_frame_id", args.ros_frame_id)
    if args.no_ros_tf:
        bp.set_attribute("ros_publish_tf", "false")

    if args.at:
        x, y, z = (float(v) for v in args.at.split(","))
        wp = world.get_map().get_waypoint(carla.Location(x, y, z),
                                          project_to_road=True, lane_type=carla.LaneType.Driving)
        if wp is None:
            raise SystemExit(f"no driving lane near ({x},{y},{z})")
        tf = carla.Transform(carla.Location(wp.transform.location.x, wp.transform.location.y,
                                            wp.transform.location.z + 0.3), wp.transform.rotation)
    else:
        tf = random.choice(world.get_map().get_spawn_points())

    ego = world.try_spawn_actor(bp, tf)
    if ego is None:
        raise SystemExit("spawn location occupied — pass a clear --at, or retry")
    if args.autopilot:
        _tm_and_sync(client, world, args.tm_port)
        ego.set_autopilot(True, args.tm_port)
    loc = ego.get_transform().location
    print(f"spawned ego id={ego.id} ({ego.type_id}) role=hero at "
          f"({loc.x:.0f},{loc.y:.0f},{loc.z:.0f}); autopilot={args.autopilot}")
    print(f"  reference it downstream with role 'hero' (spectator/sensors/telemetry) or id {ego.id}")

    # ROS 2 view of this vehicle. Registration happens server-side at spawn (only
    # for role_name == "hero"); these are the names it derived.
    ros_name = args.ros_name or f"actor{ego.id}"
    base = f"rt/carla/{ros_name}"
    # rt/tf carries sensor->parent transforms only: a vehicle alone publishes no
    # transform (verified). ros_publish_tf therefore affects sensors under it.
    print(f"  ros: name={ros_name} frame_id={args.ros_frame_id or ros_name} "
          f"ros_publish_tf={'false' if args.no_ros_tf else 'true'} "
          f"(no vehicle transform is published; rt/tf appears once a SENSOR does)")
    print(f"  ros: subscribes {base}/vehicle_control_cmd     [carla_msgs/CarlaEgoVehicleControl]")
    print(f"  ros: subscribes {base}/ackermann_control_cmd   [ackermann_msgs/AckermannDriveStamped]")
    print(f"  ros: sensors attached to it nest under {base}/<sensor ros_name>")


def cmd_destroy(args):
    client = _client()
    vehicles = list(client.get_world().get_actors().filter(args.filter))
    # Autopilot detaches automatically when the actor is destroyed; no stop needed.
    client.apply_batch_sync([DestroyActor(v) for v in vehicles], True)
    print(f"destroyed {len(vehicles)} vehicles matching {args.filter!r}")


def main() -> None:
    p = argparse.ArgumentParser(description="Spawn/destroy autopilot vehicles.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("spawn", help="spawn vehicles at spawn points, autopilot by default")
    ps.add_argument("--count", type=int, default=30)
    ps.add_argument("--filter", default="vehicle.*", help="blueprint filter (default all vehicles)")
    ps.add_argument("--safe", action="store_true", help="four-wheeled cars only (no bikes/oddities)")
    ps.add_argument("--seed", type=int, help="reproducible blueprint/point/TM choices")
    ps.add_argument("--tm-port", type=int, default=int(os.environ.get("TM_PORT", "8000")))
    ps.add_argument("--no-autopilot", action="store_true", help="spawn parked (no TM autopilot)")
    ps.set_defaults(func=cmd_spawn)

    pl = sub.add_parser("line", help="place a row of vehicles in one lane, gap metres apart")
    pl.add_argument("--at", required=True, help="X,Y,Z near the target lane")
    pl.add_argument("--count", type=int, default=5)
    pl.add_argument("--gap", type=float, default=15.0, help="spacing between vehicles in m")
    pl.add_argument("--backward", action="store_true", help="lay the row behind --at instead of ahead")
    pl.add_argument("--z-offset", type=float, default=0.3, help="height above the road to spawn (m)")
    pl.add_argument("--filter", default="vehicle.*")
    pl.add_argument("--safe", action="store_true")
    pl.add_argument("--seed", type=int)
    pl.add_argument("--tm-port", type=int, default=int(os.environ.get("TM_PORT", "8000")))
    pl.add_argument("--no-autopilot", action="store_true", help="static queue (no autopilot)")
    pl.set_defaults(func=cmd_line)

    pe = sub.add_parser("ego", help="spawn one hero vehicle (autopilot off by default)")
    pe.add_argument("--at", help="X,Y,Z near a lane (default: a random spawn point)")
    pe.add_argument("--filter", default="vehicle.*")
    pe.add_argument("--autopilot", action="store_true", help="also enrol the ego in autopilot")
    pe.add_argument("--ros-name", help="ROS topic segment for this vehicle (default actor<id>)")
    pe.add_argument("--ros-frame-id", help="TF frame id (default: the ros name)")
    pe.add_argument("--no-ros-tf", action="store_true", help="do not publish its transform on rt/tf")
    pe.add_argument("--tm-port", type=int, default=int(os.environ.get("TM_PORT", "8000")))
    pe.set_defaults(func=cmd_ego)

    pd = sub.add_parser("destroy", help="remove vehicles (all, or a --filter subset)")
    pd.add_argument("--filter", default="vehicle.*",
                    help="which to remove (e.g. 'vehicle.tesla.*'; default all vehicles)")
    pd.set_defaults(func=cmd_destroy)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
