#!/usr/bin/env bash
# Read-only prerequisite checks for open-carla-pr.
# Exits non-zero only on hard blockers: no git, no gh, or no carla checkout.
set -uo pipefail
# A CARLA_ROOT recorded with set_config is honoured; otherwise the checkout is $PWD.
. "$(dirname "${BASH_SOURCE[0]}")/../../../_common/env_common.sh"

fails=0
pass() { echo "PASS  $*"; }
warn() { echo "WARN  $*"; }
fail() { echo "FAIL  $*"; fails=$((fails + 1)); }

root="${CARLA_ROOT:-$PWD}"
command -v git >/dev/null 2>&1 && pass "git available" || fail "git not found"
if command -v gh >/dev/null 2>&1; then
  gh auth status >/dev/null 2>&1 && pass "gh authenticated" || warn "gh not authenticated — run: gh auth login"
else
  fail "gh (GitHub CLI) not found"
fi
command -v python3 >/dev/null 2>&1 && pass "python3 available" || fail "python3 not found"

if [ -f "${root}/CHANGELOG.md" ] && [ -f "${root}/.github/pull_request_template.md" ]; then
  pass "carla checkout at ${root}"
  branch="$(git -C "${root}" branch --show-current 2>/dev/null || true)"
  [ -n "${branch}" ] && pass "on branch ${branch}" || warn "detached HEAD"
else
  fail "no carla checkout at ${root} — cd into one or export CARLA_ROOT"
fi

echo
if [ "${fails}" -gt 0 ]; then
  echo "prerequisites FAILED (${fails} hard blocker(s))"
  exit 1
fi
echo "prerequisites OK"
