#!/usr/bin/env bash
# Self-contained environment for the run-carla-server skill.
# Source this before the skill's scripts:  source env.sh
#
# carla-agentic-tools is a STANDALONE repo — it does not live inside a CARLA
# checkout — so the target instance is chosen at runtime. Both roots below are
# overridable and must point at a real, built CARLA + UE4:
#
#   CARLA_UE4_ROOT  the carla source checkout (branch ue4-dev) to serve
#   UE4_ROOT        the built CarlaUnreal UE 4.26 fork (uncooked modes launch it)
#
# No environment-manager assumption is made: the verify client uses whatever
# `python3` your active CARLA client env provides.

# Sets no shell options on purpose: this file is sourced, and `set -e` here
# would change its callers' error semantics. Each script sets its own.

# --- Optional environment hook ----------------------------------------------
# CARLA_ENV_ACTIVATE, when set, names an activation script to source into this
# (possibly non-interactive) shell — the one hook for driving this skill without
# an already-active environment. Unset, it is a silent no-op. Nothing else is
# detected: no environment-manager binary is probed, no dotfile is searched for.
# Roots the caller exported explicitly outrank anything that script sets.
_KEEP_CARLA_ROOT="${CARLA_UE4_ROOT:-}" _KEEP_UE4_ROOT="${UE4_ROOT:-}"
if [ -n "${CARLA_ENV_ACTIVATE:-}" ] && [ -f "${CARLA_ENV_ACTIVATE}" ]; then
  # shellcheck disable=SC1090
  source "${CARLA_ENV_ACTIVATE}"
fi
[ -n "${_KEEP_CARLA_ROOT}" ] && CARLA_UE4_ROOT="${_KEEP_CARLA_ROOT}"
[ -n "${_KEEP_UE4_ROOT}" ] && UE4_ROOT="${_KEEP_UE4_ROOT}"

# --- Resolve the target CARLA checkout --------------------------------------
# Precedence: explicit CARLA_UE4_ROOT  >  $PWD if it is a checkout  >  the
# path-derived guess (only meaningful when this repo was dropped INTO a checkout).
_SKILL_SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_DERIVED_ROOT="$(cd "${_SKILL_SCRIPTS_DIR}/../../../.." && pwd)"
_UPROJECT_REL="Unreal/CarlaUE4/CarlaUE4.uproject"

if [ -z "${CARLA_UE4_ROOT:-}" ]; then
  if [ -f "${PWD}/${_UPROJECT_REL}" ]; then
    CARLA_UE4_ROOT="${PWD}"
  elif [ -f "${_DERIVED_ROOT}/${_UPROJECT_REL}" ]; then
    CARLA_UE4_ROOT="${_DERIVED_ROOT}"
  fi
fi
export CARLA_UE4_ROOT="${CARLA_UE4_ROOT:-}"

# UE4_ROOT has no derivable default from a standalone repo — export it, or let
# check_env.sh fail loudly with the path it looked for. Only the uncooked modes
# (default / WINDOW=1) need it; PACKAGED=1 runs from Dist/ without it.
export UE4_ROOT="${UE4_ROOT:-}"

# --- ROS 2 native interface (opt-in, runtime) -------------------------------
# ROS2=1 starts the server with `--ros2`, so it publishes DDS topics itself (no
# carla-ros-bridge). This only WORKS on a binary that was BUILT with ROS 2
# ([[build-carla-ue4]] / [[package-carla-ue4]] ROS2=1) — a plain binary accepts
# the flag and ignores it, with no error.
#
#   RMW             fastdds (server default) | cyclonedds | zenoh -> --rmw=
#                   zenoh additionally needs a router process (references/ros2.md)
#   ROS_DOMAIN_ID   0..232 -> --ros-domain-id=; unset lets the server resolve it
#                   from the ROS_DOMAIN_ID env var, then the default domain 0.
#                   Subscribers must be on the SAME domain or see no topics.
export ROS2="${ROS2:-0}"
export RMW="${RMW:-}"

# Build-time ROS 2 state of the checkout (source builds only; a Dist/ package
# carries whatever it was cooked with and this file no longer applies to it).
# BuildCarlaUE4.sh writes all module flags on ONE space-separated line.
# Echoes: on | off | absent.
carla_ros2_ini_state() {
  local ini="${CARLA_UE4_ROOT}/Unreal/CarlaUE4/Config/OptionalModules.ini"
  [ -f "${ini}" ] || { echo absent; return 0; }
  grep -q 'Ros2 ON' "${ini}" && echo on || echo off
}

# The ROS 2 runtime flags, as the server's own CarlaSettings parser expects them:
# FParse::Param(TEXT("-ros2")) matches the token "--ros2" (double dash), and
# FParse::Value(TEXT("-rmw=")) / TEXT("-ros-domain-id=") match "--rmw=<v>" /
# "--ros-domain-id=<n>". Echoes nothing when ROS2 != 1.
carla_ros2_flags() {
  [ "${ROS2}" = "1" ] || return 0
  printf '%s' "--ros2"
  [ -n "${RMW}" ] && printf ' --rmw=%s' "${RMW}"
  [ -n "${ROS_DOMAIN_ID:-}" ] && printf ' --ros-domain-id=%s' "${ROS_DOMAIN_ID}"
  return 0
}

unset _KEEP_CARLA_ROOT _KEEP_UE4_ROOT _SKILL_SCRIPTS_DIR _DERIVED_ROOT _UPROJECT_REL

echo "[env] CARLA_UE4_ROOT  = ${CARLA_UE4_ROOT:-<unset — export it>}"
echo "[env] UE4_ROOT        = ${UE4_ROOT:-<unset — needed for uncooked modes>}"
if [ "${ROS2}" = "1" ]; then
  echo "[env] ROS2            = 1  (server flags: $(carla_ros2_flags))"
else
  echo "[env] ROS2            = 0  (set ROS2=1 for the native ROS 2 interface)"
fi
