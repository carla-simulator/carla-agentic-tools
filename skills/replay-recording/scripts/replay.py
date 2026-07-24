#!/usr/bin/env python3
"""Replay a recorded CARLA .log, control its speed, follow an actor, and stop.

Commands:

    play  --file run.log                     replay the whole log
    play  --file run.log --start 5 --duration 10 --follow 87
    play  --file run.log --time-factor 2.0   replay at 2x
    play  --file run.log --replay-sensors --replay-weather
    speed --factor 0.5                       change speed of the running replay
    stop  [--keep-actors]                    stop replaying

`play` re-creates the recorded scene on the server and prints the server's replay
summary. `--follow` moves the spectator with that actor id (0 = no follow).
`--start` seconds from the beginning (negative = from the end), `--duration` 0 =
to the end. `--replay-sensors` regenerates sensor data from re-attached sensors;
`--replay-weather` restores the recorded weather. `--map-override` replays onto a
different map (for OpenDRIVE-only logs).

Time factor is a replayer setting, so it is applied before `play` and can be
changed live with `speed`.

Connection comes from the environment (see env.sh): CARLA_HOST/PORT/TIMEOUT.
"""
from __future__ import annotations

import argparse
import os

import carla  # provided by the active interpreter; check_env.sh verifies this


def _client() -> carla.Client:
    client = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                          int(os.environ.get("CARLA_PORT", "2000")))
    client.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return client


def cmd_play(args: argparse.Namespace) -> None:
    client = _client()
    if args.ignore_hero:
        client.set_replayer_ignore_hero(True)
    if args.ignore_spectator:
        client.set_replayer_ignore_spectator(True)
    client.set_replayer_time_factor(args.time_factor)  # applied before replay starts
    ret = client.replay_file(
        args.file, args.start, args.duration, args.follow,
        args.replay_sensors, args.replay_weather,
        carla.Transform(), args.map_override,
    )
    print(f"replaying {args.file}  start={args.start}s duration="
          f"{'all' if args.duration == 0 else str(args.duration)+'s'} "
          f"follow={args.follow} time_factor={args.time_factor}")
    if ret:
        print(ret)  # server's summary (or an error string if the file is bad)


def cmd_speed(args: argparse.Namespace) -> None:
    _client().set_replayer_time_factor(args.factor)
    print(f"replay time_factor set to {args.factor} "
          f"({'faster' if args.factor > 1 else 'slower' if args.factor < 1 else 'real-time'})")


def cmd_stop(args: argparse.Namespace) -> None:
    _client().stop_replayer(args.keep_actors)
    print(f"replay stopped (keep_actors={args.keep_actors})")


def main() -> None:
    p = argparse.ArgumentParser(description="Replay a CARLA recording.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("play", help="replay a .log")
    pp.add_argument("--file", required=True, help="server-side .log path")
    pp.add_argument("--start", type=float, default=0.0, help="start time s (negative = from end)")
    pp.add_argument("--duration", type=float, default=0.0, help="seconds to replay (0 = all)")
    pp.add_argument("--follow", type=int, default=0, help="actor id for the spectator to follow (0 = none)")
    pp.add_argument("--time-factor", type=float, default=1.0, help="playback speed (1.0 = real time)")
    pp.add_argument("--replay-sensors", action="store_true", help="regenerate sensor data")
    pp.add_argument("--replay-weather", action="store_true", help="restore recorded weather")
    pp.add_argument("--map-override", default="", help="replay onto a different map")
    pp.add_argument("--ignore-hero", action="store_true", help="do not replay the hero actor")
    pp.add_argument("--ignore-spectator", action="store_true", help="do not move the spectator")
    pp.set_defaults(func=cmd_play)

    psp = sub.add_parser("speed", help="change the running replay's speed")
    psp.add_argument("--factor", type=float, required=True, help="time factor (2.0 = 2x, 0.5 = half)")
    psp.set_defaults(func=cmd_speed)

    pst = sub.add_parser("stop", help="stop replaying")
    pst.add_argument("--keep-actors", action="store_true", help="leave replayed actors in the world")
    pst.set_defaults(func=cmd_stop)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
