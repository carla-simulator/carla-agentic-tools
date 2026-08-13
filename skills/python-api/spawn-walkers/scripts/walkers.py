#!/usr/bin/env python3
"""Spawn pedestrians that wander via WalkerAIController, and destroy them cleanly.

Commands:

    spawn   --count 30 [--speed-min 1.0 --speed-max 1.8] [--cross-factor 0.1]
            [--seed 42] [--no-wander]            spawn walkers + AI controllers
    destroy                                      stop + destroy, in the right order

Each pedestrian is a `walker.pedestrian.*` actor paired with a
`controller.ai.walker`. By default `spawn` starts every controller and gives it
one random destination — and that is enough to wander FOREVER: CARLA's walker AI
automatically picks a fresh random target each time a walker arrives (verified in
LibCarla nav: WalkerManager::SetWalkerRoute). So no re-targeting loop is needed.
Pass `--no-wander` to spawn a stationary crowd (controllers left unstarted).

Works in ASYNCHRONOUS mode (the default) — sync mode is not required. The script
just advances a frame between spawn phases (`tick` if the world is already sync,
else `wait_for_tick`), so it is correct either way.

DESTROY ORDER MATTERS: stop() and destroy the controllers BEFORE the walkers.
`destroy` does this; do not destroy walkers first or you strand live controllers.

Needs a navmesh (see the debug-navmesh skill to validate one). Connection from
env.sh: CARLA_HOST/PORT/TIMEOUT.
"""
from __future__ import annotations

import argparse
import os
import random

import carla  # provided by the active interpreter; check_env.sh verifies this

SpawnActor = carla.command.SpawnActor
DestroyActor = carla.command.DestroyActor
FutureActor = carla.command.FutureActor


def _client() -> carla.Client:
    client = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                          int(os.environ.get("CARLA_PORT", "2000")))
    client.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return client


def _advance(world: carla.World) -> None:
    """Advance one frame so freshly spawned actors register — sync or async."""
    if world.get_settings().synchronous_mode:
        world.tick()
    else:
        world.wait_for_tick()


def cmd_spawn(args):
    client = _client()
    world = client.get_world()
    if args.seed is not None:
        world.set_pedestrians_seed(args.seed)
        random.seed(args.seed)
    # How often pedestrians cross roads (0 = never, 1 = always). Low by default so
    # they mostly use sidewalks rather than constantly jaywalking.
    world.set_pedestrians_cross_factor(args.cross_factor)

    bp_lib = world.get_blueprint_library()
    walker_bps = bp_lib.filter("walker.pedestrian.*")
    controller_bp = bp_lib.find("controller.ai.walker")

    # Phase 1: pick navmesh points and batch-spawn the walker bodies.
    spawn_batch = []
    for _ in range(args.count):
        loc = world.get_random_location_from_navigation()
        if loc is None:
            continue  # no navmesh point available this draw
        bp = random.choice(walker_bps)
        if bp.has_attribute("is_invincible"):
            bp.set_attribute("is_invincible", "false")  # so they can be hit/collide
        spawn_batch.append(SpawnActor(bp, carla.Transform(loc)))
    if not spawn_batch:
        raise SystemExit("no navmesh spawn points — is the navmesh present? (debug-navmesh)")

    walker_ids = []
    for r in client.apply_batch_sync(spawn_batch, True):
        if not r.error:
            walker_ids.append(r.actor_id)
    _advance(world)  # let the walkers register before attaching controllers

    # Phase 2: batch-spawn one AI controller parented to each walker.
    ctrl_batch = [SpawnActor(controller_bp, carla.Transform(), wid) for wid in walker_ids]
    controller_ids = []
    for r in client.apply_batch_sync(ctrl_batch, True):
        if not r.error:
            controller_ids.append(r.actor_id)
    _advance(world)  # controllers must exist before start()

    # Phase 3: start each controller with ONE random destination. The walker AI
    # then re-targets on its own forever, so this single call = infinite wander.
    # --no-wander skips it: controllers stay unstarted and the crowd is stationary.
    controllers = world.get_actors(controller_ids)
    if not args.no_wander:
        for c in controllers:
            c.start()
            dest = world.get_random_location_from_navigation()
            if dest is not None:
                c.go_to_location(dest)
            c.set_max_speed(random.uniform(args.speed_min, args.speed_max))
        _advance(world)

    mode = ("stationary (--no-wander; controllers unstarted)" if args.no_wander
            else f"wandering indefinitely at {args.speed_min}-{args.speed_max} m/s "
                 f"(cross_factor={args.cross_factor})")
    print(f"spawned {len(walker_ids)} walkers + {len(controller_ids)} controllers; {mode}")
    if len(controller_ids) < args.count:
        print(f"  note: {args.count - len(controller_ids)} fewer than requested "
              f"(nav-point collisions / spawn failures — normal at high counts)")


def cmd_destroy(args):
    client = _client()
    world = client.get_world()
    controllers = list(world.get_actors().filter("controller.ai.walker"))
    # Correct order: stop controllers, destroy controllers, THEN destroy walkers.
    # stop() can throw on a controller that is not/no-longer attached to a walker
    # (e.g. one left by a replay) — tolerate it so one bad controller cannot abort
    # the whole cleanup; it gets destroyed regardless below.
    for c in controllers:
        try:
            c.stop()
        except RuntimeError:
            pass
    client.apply_batch_sync([DestroyActor(c) for c in controllers], True)
    walkers = list(world.get_actors().filter("walker.pedestrian.*"))
    client.apply_batch_sync([DestroyActor(w) for w in walkers], True)
    print(f"stopped + destroyed {len(controllers)} controllers, then {len(walkers)} walkers")


def main() -> None:
    p = argparse.ArgumentParser(description="Spawn/steer/destroy CARLA pedestrians.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("spawn", help="spawn walkers + AI controllers, set them wandering")
    ps.add_argument("--count", type=int, default=30)
    ps.add_argument("--speed-min", type=float, default=1.0, help="m/s (≈ slow walk)")
    ps.add_argument("--speed-max", type=float, default=1.8, help="m/s (≈ brisk walk)")
    ps.add_argument("--cross-factor", type=float, default=0.1, help="0-1 road-crossing probability")
    ps.add_argument("--seed", type=int, help="reproducible pedestrian placement")
    ps.add_argument("--no-wander", action="store_true",
                    help="spawn a stationary crowd (leave controllers unstarted)")
    ps.set_defaults(func=cmd_spawn)

    sub.add_parser("destroy", help="stop + destroy controllers then walkers").set_defaults(func=cmd_destroy)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
