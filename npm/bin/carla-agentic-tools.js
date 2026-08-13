#!/usr/bin/env node
/**
 * npx front door for the Python MCP server `carla-agentic-tools`.
 *
 *   npx -y @carla-simulator/agentic-tools
 *
 * The server itself is Python (PyPI is the source of truth); this wrapper only
 * finds a Python runner and execs it, pinning the SAME version as this npm
 * package so `npx @carla-simulator/agentic-tools@0.2.0` is reproducible.
 *
 * Two rules matter for an MCP stdio server:
 *   1. stdout carries the JSON-RPC stream — every diagnostic here goes to
 *      stderr, or the client sees corrupt frames.
 *   2. stdio is inherited, never piped, so the client talks to Python directly
 *      and this process adds no buffering.
 *
 * Runner preference: uvx (ephemeral, no install) -> uv tool run -> pipx run.
 * We deliberately do NOT fall back to `pip install`: silently mutating a user's
 * global environment is worse than a clear error.
 */
"use strict";

const { spawnSync } = require("child_process");
const sh = spawnSync;
const { version } = require("../package.json");

const PYPI_NAME = "carla-agentic-tools";
// CARLA_AGENTIC_TOOLS_SPEC overrides what gets resolved: a local wheel, a git
// ref, or an unreleased version. Used to test this wrapper before a release and
// to pin a fork; unset, it tracks this package's own version exactly.
const OVERRIDE = process.env.CARLA_AGENTIC_TOOLS_SPEC;
const SPEC_UVX = OVERRIDE || `${PYPI_NAME}@${version}`;
const SPEC_PIP = OVERRIDE || `${PYPI_NAME}==${version}`;

function have(cmd) {
  const probe = sh(cmd, ["--version"], { stdio: "ignore" });
  return !probe.error && probe.status === 0;
}

function pick() {
  if (have("uvx")) return { cmd: "uvx", args: [SPEC_UVX] };
  if (have("uv")) return { cmd: "uv", args: ["tool", "run", SPEC_UVX] };
  if (have("pipx")) return { cmd: "pipx", args: ["run", "--spec", SPEC_PIP, PYPI_NAME] };
  return null;
}

const runner = pick();
if (!runner) {
  process.stderr.write(
    [
      "carla-agentic-tools: no Python runner found (need uvx, uv, or pipx).",
      "",
      "Install uv (recommended, one line, no sudo):",
      "  curl -LsSf https://astral.sh/uv/install.sh | sh",
      "",
      `Or install the server directly:  pipx install ${SPEC_PIP}`,
      "",
    ].join("\n")
  );
  process.exit(1);
}

// Forward any extra CLI args (e.g. a future --transport) untouched.
const extra = process.argv.slice(2);
const child = spawnSync(runner.cmd, [...runner.args, ...extra], {
  stdio: "inherit",
  env: process.env,
});

if (child.error) {
  process.stderr.write(`carla-agentic-tools: failed to start ${runner.cmd}: ${child.error.message}\n`);
  process.exit(1);
}
// Mirror the child's exit so supervisors see the real status; a signal death
// becomes 128+signo, the shell convention.
process.exit(child.status === null ? 128 + (child.signal ? 1 : 0) : child.status);
