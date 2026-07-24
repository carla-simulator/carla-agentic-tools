# Vehicle control — detail

Detail layer for the `control-vehicle` skill.

## Manual vs autopilot

A vehicle is driven by **either** manual control **or** the Traffic Manager, never
both: applying control while autopilot is on does nothing useful. `control` and
`ackermann` call `set_autopilot(False)` first. To hand the car back to traffic,
use the control-traffic skill (or `set_autopilot(True, tm_port)`).

## VehicleControl (raw) vs Ackermann

- `apply_control(VehicleControl(throttle, steer, brake, hand_brake, reverse,
  manual_gear_shift, gear))` — direct actuator input. `throttle`/`brake` are
  0..1, `steer` is -1..1. It **persists**: the vehicle holds the last control
  every tick until you change it. Use `--hold` for a timed action.
- `apply_ackermann_control(VehicleAckermannControl(steer, steer_speed, speed,
  acceleration, jerk))` — a target-*speed* controller: you give a desired `speed`
  (m/s) and it works out throttle/brake to reach and hold it. Better for "drive at
  8 m/s" than hand-tuning throttle. `apply_ackermann_controller_settings(...)`
  tunes that controller's PID if needed.

## Lights

`set_light_state(VehicleLightState(bitmask))` / `get_light_state()`. Flags OR
together: `Position`, `LowBeam`, `HighBeam`, `Brake`, `LeftBlinker`,
`RightBlinker`, `Reverse`, `Fog`, `Interior`, `Special1`, `Special2` (plus `All`,
`NONE`). Hazards = both blinkers. The skill reads the current state and adds
(`--on`) / clears (`--off`) flags so other lights are preserved. Note: under
autopilot, `control-traffic`'s `update_vehicle_lights` can let the TM manage
lights automatically instead.

## Doors

`open_door(VehicleDoor)` / `close_door(VehicleDoor)`. 0.9.16 exposes `FL`, `FR`,
`RL`, `RR`, `All` — no hood/trunk. Not every vehicle model has animated doors;
some are no-ops.

## Physics control

`get_physics_control()` → `VehiclePhysicsControl`; mutate and `apply_physics_control(pc)`.
Common scalar fields (this skill exposes mass/drag/max_rpm; the rest are editable
in code):

- `mass` (kg), `drag_coefficient`, `max_rpm`, `moi`, `center_of_mass`,
- `clutch_strength`, `gear_switch_time`, `final_ratio`, `forward_gears`,
  `use_gear_autobox`, `use_sweep_wheel_collision`,
- `torque_curve`, `steering_curve` (lists of `Vector2D`),
- `wheels` (list of `WheelPhysicsControl`: tyre friction, damping, steer angle,
  radius, suspension...).

Tuning wheels/curves is the `vehicle_physics.py` use case — read the current
control, edit specific entries, re-apply. `show_debug_telemetry(True)` overlays
live physics on a rendered server, handy while tuning.

## Sync mode

Under synchronous mode the vehicle only moves when the world is ticked, and
`--hold` counts wall-clock seconds — drive the tick loop (set-world-settings)
alongside, or control in async mode.
