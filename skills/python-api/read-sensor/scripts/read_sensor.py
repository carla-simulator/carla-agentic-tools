#!/usr/bin/env python3
"""Listen to a CARLA sensor and save its data, show it in a window, or summarise it.

Select an existing sensor (spawn one with the create-sensor skill first):
    --id N | --type sensor.camera.rgb | --attached-to hero

Commands:
    info   [--seconds 5]                    grab one reading and print a summary
    save   --out DIR [--seconds 10] [--frames N]   write frames to DIR
    show   [--seconds 20]                   live window (cameras + lidar)
    grid   --ids 12,13,14 [--seconds 20]    tile several sensors in one window
    ros-info                                the ROS 2 topics this sensor
                                            publishes, their QoS, and whether it
                                            is actually enabled for ROS

save writes cameras as PNG (depth→logarithmic, semantic→CityScapes palette),
lidar as .ply, and other sensors (imu/gnss/radar/…) as rows in data.jsonl.
show opens a pygame window: camera images directly, lidar as a top-down scatter;
non-visual sensors stream their readings to the console instead. It runs for
--seconds (0 = until the window is closed).

Listening is a callback in THIS process — the data only flows while the command
runs. See references/read-sensor.md for callbacks-vs-queue and sync alignment.
Connection from env.sh: CARLA_HOST/PORT/TIMEOUT.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import threading
import time

import carla  # provided by the active interpreter; check_env.sh verifies this
import numpy as np


def _client():
    c = carla.Client(os.environ.get("CARLA_HOST", "127.0.0.1"),
                     int(os.environ.get("CARLA_PORT", "2000")))
    c.set_timeout(float(os.environ.get("CARLA_TIMEOUT", "10.0")))
    return c


def _resolve(world, args) -> carla.Actor:
    actors = world.get_actors()
    if args.id is not None:
        s = actors.find(args.id)
        if s is None or not s.type_id.startswith("sensor."):
            raise SystemExit(f"no sensor with id {args.id}")
        return s
    sensors = list(actors.filter("sensor.*"))
    if args.attached_to:
        sensors = [s for s in sensors if s.parent is not None
                   and s.parent.attributes.get("role_name", "") == args.attached_to]
    if args.type:
        sensors = [s for s in sensors if s.type_id == (args.type if args.type.startswith("sensor.")
                                                       else f"sensor.{args.type}")]
    if not sensors:
        raise SystemExit("no matching sensor (create one with create-sensor, "
                         "or check --id/--type/--attached-to)")
    if len(sensors) > 1:
        print(f"note: {len(sensors)} sensors matched; using id={sensors[0].id} ({sensors[0].type_id})")
    return sensors[0]


def _cc(type_id):
    if "depth" in type_id:
        return carla.ColorConverter.LogarithmicDepth
    if "semantic_segmentation" in type_id:
        return carla.ColorConverter.CityScapesPalette
    return carla.ColorConverter.Raw


def _describe(data) -> dict:
    """Key fields per measurement type — for info and jsonl saving."""
    d = {"frame": data.frame, "t": round(data.timestamp, 4)}
    if isinstance(data, carla.Image):
        d.update(kind="image", w=data.width, h=data.height, fov=data.fov)
    elif isinstance(data, (carla.LidarMeasurement, carla.SemanticLidarMeasurement)):
        d.update(kind="lidar", points=len(data))
    elif isinstance(data, carla.RadarMeasurement):
        d.update(kind="radar", detections=len(data))
    elif isinstance(data, carla.IMUMeasurement):
        a, g = data.accelerometer, data.gyroscope
        d.update(kind="imu", accel=[round(a.x, 3), round(a.y, 3), round(a.z, 3)],
                 gyro=[round(g.x, 3), round(g.y, 3), round(g.z, 3)], compass=round(data.compass, 3))
    elif isinstance(data, carla.GnssMeasurement):
        d.update(kind="gnss", lat=data.latitude, lon=data.longitude, alt=data.altitude)
    elif isinstance(data, carla.ObstacleDetectionEvent):
        d.update(kind="obstacle", other=data.other_actor.type_id, distance=round(data.distance, 2))
    elif isinstance(data, carla.CollisionEvent):
        n = data.normal_impulse
        d.update(kind="collision", other=data.other_actor.type_id,
                 impulse=round((n.x**2 + n.y**2 + n.z**2) ** 0.5, 2))
    elif isinstance(data, carla.LaneInvasionEvent):
        d.update(kind="lane_invasion", markings=[str(m.type) for m in data.crossed_lane_markings])
    else:
        d.update(kind=data.__class__.__name__)
    return d


def _camera_rgb(image) -> np.ndarray:
    a = np.frombuffer(image.raw_data, dtype=np.uint8).reshape((image.height, image.width, 4))
    return a[:, :, :3][:, :, ::-1]  # BGRA -> RGB


def _lidar_topdown(measure, size=600, rng=50.0) -> np.ndarray:
    """Top-down scatter of a lidar sweep into an RGB image (rng metres half-extent)."""
    pts = np.frombuffer(measure.raw_data, dtype=np.float32).reshape(-1, 4)[:, :2]
    img = np.zeros((size, size, 3), np.uint8)
    px = ((pts / rng) * (size / 2) + (size / 2)).astype(np.int32)
    ok = (px[:, 0] >= 0) & (px[:, 0] < size) & (px[:, 1] >= 0) & (px[:, 1] < size)
    img[px[ok, 1], px[ok, 0]] = (255, 255, 255)
    return img


def _render_frame(data, type_id, cc):
    """Measurement -> RGB array for cameras (converted) and lidar; None otherwise."""
    if type_id.startswith("sensor.camera"):
        data.convert(cc)
        return _camera_rgb(data)
    if "lidar" in type_id:
        return _lidar_topdown(data)
    return None


# ---- commands --------------------------------------------------------------

def cmd_info(args):
    world = _client().get_world()
    sensor = _resolve(world, args)
    got = {"data": None}
    ev = threading.Event()

    def cb(data):
        got["data"] = data
        ev.set()

    sensor.listen(cb)
    ok = ev.wait(args.seconds)
    sensor.stop()
    if not ok:
        raise SystemExit(f"no data from id={sensor.id} within {args.seconds}s "
                         "(is the world ticking? sensor_tick too high?)")
    print(f"sensor id={sensor.id} ({sensor.type_id}):")
    print(f"  {_describe(got['data'])}")


def cmd_save(args):
    world = _client().get_world()
    sensor = _resolve(world, args)
    os.makedirs(args.out, exist_ok=True)
    cc = _cc(sensor.type_id)
    is_img = sensor.type_id.startswith("sensor.camera")
    is_lidar = "lidar" in sensor.type_id
    jsonl = None if (is_img or is_lidar) else open(os.path.join(args.out, "data.jsonl"), "w")
    count = {"n": 0}

    def cb(data):
        i = count["n"]
        if args.frames and i >= args.frames:
            return
        if is_img:
            data.save_to_disk(os.path.join(args.out, f"{data.frame:08d}.png"), cc)
        elif is_lidar:
            data.save_to_disk(os.path.join(args.out, f"{data.frame:08d}.ply"))
        else:
            jsonl.write(json.dumps(_describe(data)) + "\n"); jsonl.flush()
        count["n"] = i + 1

    sensor.listen(cb)
    # Collect until the frame cap or the time budget, whichever comes first.
    end = time.time() + args.seconds
    while time.time() < end and not (args.frames and count["n"] >= args.frames):
        time.sleep(0.05)
    sensor.stop()
    if jsonl:
        jsonl.close()
    print(f"saved {count['n']} frames from id={sensor.id} ({sensor.type_id}) to {args.out}")


def cmd_show(args):
    world = _client().get_world()
    sensor = _resolve(world, args)
    is_img = sensor.type_id.startswith("sensor.camera")
    is_lidar = "lidar" in sensor.type_id
    if not (is_img or is_lidar):
        # Non-visual sensor: stream readings to the console instead of a window.
        print(f"id={sensor.id} ({sensor.type_id}) has no image; streaming readings "
              f"for {args.seconds or 10}s (Ctrl-C to stop):")
        sensor.listen(lambda d: print("  ", _describe(d)))
        try:
            time.sleep(args.seconds or 10)
        except KeyboardInterrupt:
            pass
        sensor.stop()
        return

    import pygame  # only needed for the window
    cc = _cc(sensor.type_id)
    latest = {"frame": None}
    lock = threading.Lock()

    def cb(data):
        if is_img:
            data.convert(cc)
            frame = _camera_rgb(data)
        else:
            frame = _lidar_topdown(data)
        with lock:
            latest["frame"] = frame

    sensor.listen(cb)
    pygame.init()
    screen = None
    clock = pygame.time.Clock()
    end = (time.time() + args.seconds) if args.seconds else None
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
        with lock:
            frame = latest["frame"]
        if frame is not None:
            if screen is None:
                screen = pygame.display.set_mode((frame.shape[1], frame.shape[0]))
                pygame.display.set_caption(f"{sensor.type_id} id={sensor.id}")
            surf = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
            screen.blit(surf, (0, 0))
            pygame.display.flip()
        clock.tick(30)
        if end and time.time() > end:
            running = False
    sensor.stop()
    pygame.quit()
    print(f"closed window for id={sensor.id} ({sensor.type_id})")


def cmd_grid(args):
    import cv2
    import pygame
    world = _client().get_world()
    ids = [int(x) for x in args.ids.split(",")]
    sensors = []
    for i in ids:
        s = world.get_actors().find(i)
        if s is None or not s.type_id.startswith("sensor."):
            raise SystemExit(f"no sensor with id {i}")
        sensors.append(s)

    cw, ch = 400, 300                       # per-cell size
    cols = math.ceil(math.sqrt(len(sensors)))
    rows = math.ceil(len(sensors) / cols)
    latest = {s.id: None for s in sensors}
    lock = threading.Lock()

    def mk_cb(s):
        cc = _cc(s.type_id)
        def cb(data):
            f = _render_frame(data, s.type_id, cc)
            if f is not None:
                with lock:
                    latest[s.id] = cv2.resize(f, (cw, ch))
        return cb

    for s in sensors:
        s.listen(mk_cb(s))
    pygame.init()
    screen = pygame.display.set_mode((cols * cw, rows * ch))
    pygame.display.set_caption(f"{len(sensors)} sensors")
    clock = pygame.time.Clock()
    end = (time.time() + args.seconds) if args.seconds else None
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
        canvas = np.zeros((rows * ch, cols * cw, 3), np.uint8)
        with lock:
            for k, s in enumerate(sensors):
                f = latest[s.id]
                if f is not None:
                    r, c = divmod(k, cols)
                    canvas[r*ch:(r+1)*ch, c*cw:(c+1)*cw] = f
        screen.blit(pygame.surfarray.make_surface(canvas.swapaxes(0, 1)), (0, 0))
        pygame.display.flip()
        clock.tick(30)
        if end and time.time() > end:
            running = False
    for s in sensors:
        s.stop()
    pygame.quit()
    print(f"closed grid of {len(sensors)} sensors")


# --- ROS 2 ------------------------------------------------------------------
# Mirrors LibCarla/source/carla/ros2: the base topic is "rt/carla/<ros_name>",
# nested under the parent's when attached, and each publisher appends its suffix.
# Sensors absent from ROS2::GetOrCreateSensor's switch have no publisher at all.
_CAMERA_TOPICS = (("/image", "sensor_msgs/Image"),
                  ("/camera_info", "sensor_msgs/CameraInfo"))
_CLOUD_TOPICS = (("/point_cloud", "sensor_msgs/PointCloud2"),)
_ROS_UNSUPPORTED = ("other.lane_invasion", "other.obstacle", "other.rss")


def _ros_topics_for(type_id: str, base: str):
    short = type_id[len("sensor."):] if type_id.startswith("sensor.") else type_id
    if short in _ROS_UNSUPPORTED or "gbuffer" in short:
        return []
    if short == "camera.dvs":
        return [(base + s, m) for s, m in _CAMERA_TOPICS + _CLOUD_TOPICS]
    if short.startswith("camera."):
        return [(base + s, m) for s, m in _CAMERA_TOPICS]
    if short.startswith("lidar.") or short == "other.radar":
        return [(base + s, m) for s, m in _CLOUD_TOPICS]
    if short == "other.imu":
        return [(base, "sensor_msgs/Imu")]
    if short == "other.gnss":
        return [(base, "sensor_msgs/NavSatFix")]
    if short == "other.collision":
        return [(base, "carla_msgs/CarlaCollisionEvent")]
    return []


def cmd_ros_info(args):
    """What this sensor publishes natively, and whether it is publishing at all.

    Read-only, and answerable without ROS 2 installed: the names are derived from
    the actor's own attributes, exactly as the server derives them.
    """
    world = _client().get_world()
    sensor = _resolve(world, args)
    ros_name = sensor.attributes.get("ros_name", "") or f"actor{sensor.id}"
    frame_id = sensor.attributes.get("ros_frame_id", "") or ros_name
    publish_tf = sensor.attributes.get("ros_publish_tf", "true").lower() != "false"

    base = f"rt/carla/{ros_name}"
    parent = sensor.parent
    if parent is not None:
        parent_ros = parent.attributes.get("ros_name", "") or f"actor{parent.id}"
        base = f"rt/carla/{parent_ros}/{ros_name}"

    print(f"sensor id={sensor.id} ({sensor.type_id})")
    print(f"  ros_name={ros_name!r} frame_id={frame_id!r} "
          f"parent_frame={'map' if parent is None else (parent.attributes.get('ros_frame_id') or parent.attributes.get('ros_name') or f'actor{parent.id}')}")
    topics = _ros_topics_for(sensor.type_id, base)
    if not topics:
        print(f"  NO native publisher for {sensor.type_id} — it never appears on ROS")
    for t, m in topics:
        # Image/point-cloud publishers use the sensor-data profile (best effort);
        # everything else keeps the reliable default. Depth 1 in both cases.
        #
        # Durability is NOT volatile in practice: the middleware only ever RAISES
        # it, and Fast DDS's default writer QoS is already TRANSIENT_LOCAL, so
        # every topic reports transient_local there (verified against a live
        # server). Other RMWs may differ, hence the hedge in the label.
        qos = "best_effort" if t.endswith(("/image", "/camera_info", "/point_cloud")) else "reliable"
        print(f"  {t}  [{m}]  qos={qos}, depth=1, durability=transient_local on fastdds"
              f"   (ROS node sees /{t[3:]})")
    print(f"  rt/tf: {'yes' if publish_tf else 'no (ros_publish_tf=false)'}")

    # is_listening covers Python listeners only; enable_for_ros is a separate
    # server-side flag, and it is the one that makes a sensor tick for ROS.
    try:
        enabled = sensor.is_enabled_for_ros()
    except AttributeError:      # older client without the binding
        enabled = None
    if enabled is False:
        print("  enabled_for_ros=NO — this sensor is NOT publishing. Fix with:")
        print(f"    python3 -c \"import carla;a=carla.Client('127.0.0.1',2000)."
              f"get_world().get_actors().find({sensor.id});a.enable_for_ros()\"")
    elif enabled is True:
        print("  enabled_for_ros=yes")
    else:
        print("  enabled_for_ros=? (client too old for is_enabled_for_ros)")


def _sel(sp):
    sp.add_argument("--id", type=int); sp.add_argument("--type"); sp.add_argument("--attached-to")
    return sp


def main() -> None:
    p = argparse.ArgumentParser(description="Read/save/show a CARLA sensor.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = _sel(sub.add_parser("info", help="one reading + summary"))
    pi.add_argument("--seconds", type=float, default=5.0)
    pi.set_defaults(func=cmd_info)

    ps = _sel(sub.add_parser("save", help="write frames to a directory"))
    ps.add_argument("--out", required=True)
    ps.add_argument("--seconds", type=float, default=10.0)
    ps.add_argument("--frames", type=int, help="stop after this many frames")
    ps.set_defaults(func=cmd_save)

    psh = _sel(sub.add_parser("show", help="live window (camera/lidar) or console stream"))
    psh.add_argument("--seconds", type=float, default=20.0, help="0 = until window closed")
    psh.set_defaults(func=cmd_show)

    pgr = sub.add_parser("grid", help="tile several sensors in one window")
    pgr.add_argument("--ids", required=True, help="comma-separated sensor ids, e.g. 12,13,14")
    pgr.add_argument("--seconds", type=float, default=20.0, help="0 = until window closed")
    pgr.set_defaults(func=cmd_grid)

    _sel(sub.add_parser("ros-info", help="ROS 2 topics + QoS for this sensor")) \
        .set_defaults(func=cmd_ros_info)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
