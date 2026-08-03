#!/usr/bin/env python3
"""Record a CARLA simulation to a .log for later replay, then verify it captured.

Commands:

    start --file run.log            begin recording (server-side file)
    start --file run.log --extra    also record velocities/controls (bigger file)
    stop                            stop recording
    clip  --file run.log --seconds 20   start, wait N seconds, stop, verify

The recorder captures WORLD STATE frame by frame — actor spawns/destroys,
transforms, traffic-light states, vehicle/walker animation — NOT sensor output
(camera images, lidar). Those are re-simulated only on replay. `--extra`
(additional_data) adds velocities, accelerations and control inputs.

The .log is written on the SERVER. A relative --file lands under the server's
CarlaUE4/Saved/; pass an absolute path to place it precisely. After stopping,
this verifies by asking the server to parse the file back (frame count/duration),
because start/stop themselves don't confirm anything was captured.

Connection comes from the environment (see env.sh): CARLA_HOST/PORT/TIMEOUT.
"""
from __future__ import annotations

import argparse
import os
import time

import carla  # provided by the active interpreter; check_env.sh verifies this


def _client() -> carla.Client:
    client = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                          int(os.environ.get("CARLA_PORT", "2000")))
    client.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return client


def _verify(client: carla.Client, name: str) -> None:
    """Parse the just-written file back and show its header, as proof of capture."""
    info = client.show_recorder_file_info(name, False)
    head = "\n".join(info.splitlines()[:6]) if info else "(empty)"
    print(f"\nVERIFY (parsed {name} back from the server):\n{head}")
    if "Frames" not in info and "frames" not in info:
        print("  WARNING: no frame section — the file may be empty or unreadable")


def cmd_start(args: argparse.Namespace) -> None:
    client = _client()
    ret = client.start_recorder(args.file, args.extra)
    print(f"recording -> {args.file}  (additional_data={args.extra})")
    if ret:
        print(ret)


def cmd_stop(_: argparse.Namespace) -> None:
    _client().stop_recorder()
    print("recording stopped")


def cmd_clip(args: argparse.Namespace) -> None:
    client = _client()
    client.start_recorder(args.file, args.extra)
    print(f"recording -> {args.file} for {args.seconds}s (additional_data={args.extra})")
    time.sleep(args.seconds)
    client.stop_recorder()
    print("recording stopped")
    _verify(client, args.file)


def main() -> None:
    p = argparse.ArgumentParser(description="Record a CARLA simulation and verify.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("start", help="start recording")
    ps.add_argument("--file", required=True, help="server-side .log path (abs recommended)")
    ps.add_argument("--extra", action="store_true", help="record additional_data (velocities/controls)")
    ps.set_defaults(func=cmd_start)

    sub.add_parser("stop", help="stop recording").set_defaults(func=cmd_stop)

    pc = sub.add_parser("clip", help="record for a fixed number of seconds, then verify")
    pc.add_argument("--file", required=True, help="server-side .log path (abs recommended)")
    pc.add_argument("--seconds", type=float, required=True, help="how long to record")
    pc.add_argument("--extra", action="store_true", help="record additional_data")
    pc.set_defaults(func=cmd_clip)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
