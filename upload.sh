#!/usr/bin/env bash
# Publish carla-agentic-tools to PyPI and npm. Production only.
#
#   bash upload.sh            # preflight, build, then confirm each publish
#   bash upload.sh --check    # preflight and build, publish nothing
#   bash upload.sh --pypi     # PyPI only
#   bash upload.sh --npm      # npm only
#
# Both indexes are permanent: a version can never be replaced, and npm allows
# unpublish only within 72 hours. So each publish is confirmed separately by
# typing "yes", and --check exists to rehearse the whole thing.
#
# Tokens are read once without echo. Nothing reaches a shell history, and the
# temporary npm credential file is removed on every exit path.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${REPO}"

DO_PYPI=1
DO_NPM=1
CHECK_ONLY=0
for arg in "$@"; do
  case "${arg}" in
    --check) CHECK_ONLY=1 ;;
    --pypi)  DO_NPM=0 ;;
    --npm)   DO_PYPI=0 ;;
    -h|--help) sed -n '2,${ /^[^#]/q; s/^# \{0,1\}//p; }' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option ${arg} (try --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '  PASS %s\n' "$*"; }
bad()  { printf '  FAIL %s\n' "$*" >&2; exit 1; }
note() { printf '  %s\n' "$*"; }

confirm() {
  local answer
  printf '\n  %s\n  Type "yes" to publish: ' "$1"
  read -r answer
  [ "${answer}" = "yes" ] || { echo "  not published"; return 1; }
  return 0
}

PYTHON="${PYTHON:-python3}"

# --- preflight --------------------------------------------------------------

say "Preflight"

for tool in "${PYTHON}" node npm curl; do
  command -v "${tool}" >/dev/null 2>&1 || bad "no ${tool} on PATH"
done
"${PYTHON}" -c 'import build' 2>/dev/null || bad "no 'build' module — ${PYTHON} -m pip install build"
"${PYTHON}" -c 'import twine' 2>/dev/null || bad "no 'twine' module — ${PYTHON} -m pip install twine"
ok "tooling present (node $(node --version))"

VERSION="$("${PYTHON}" - <<'PY'
import re
proj = open("pyproject.toml").read().split("[project]", 1)[1].split("\n[", 1)[0]
print(re.search(r'^version\s*=\s*"([^"]+)"', proj, re.M).group(1))
PY
)"
[ -n "${VERSION}" ] || bad "could not read the version from pyproject.toml"
NPM_VERSION="$("${PYTHON}" -c 'import json;print(json.load(open("package.json"))["version"])')"
[ "${VERSION}" = "${NPM_VERSION}" ] \
  || bad "version drift: pyproject ${VERSION}, package.json ${NPM_VERSION}"
ok "version ${VERSION} in pyproject and package.json"

# Both suites. The Python one covers the server and the skill library; the Node
# one covers the npm half; test_node_parity.py is what stops the two answering
# differently to the same question.
if "${PYTHON}" -m pytest -q -p no:anyio tests/ >/tmp/cat-py.$$ 2>&1; then
  ok "python tests: $(tail -1 /tmp/cat-py.$$ | tr -s ' ')"
  rm -f /tmp/cat-py.$$
else
  tail -25 /tmp/cat-py.$$ >&2; rm -f /tmp/cat-py.$$; bad "python tests fail"
fi
if node test/node_smoke.js >/tmp/cat-node.$$ 2>&1; then
  ok "$(tail -1 /tmp/cat-node.$$)"
  rm -f /tmp/cat-node.$$
else
  tail -25 /tmp/cat-node.$$ >&2; rm -f /tmp/cat-node.$$; bad "node tests fail"
fi

if git rev-parse --git-dir >/dev/null 2>&1 && [ -n "$(git status --porcelain)" ]; then
  note "WARN working tree is dirty; artifacts are built from what is on disk,"
  note "     so this release may not match any commit"
else
  ok "working tree clean"
fi

# Neither index replaces a version. Finding out now costs nothing; finding out
# after a partial release costs a version number.
if [ "${DO_PYPI}" -eq 1 ] && curl -sfI "https://pypi.org/pypi/carla-agentic-tools/${VERSION}/json" >/dev/null 2>&1; then
  bad "PyPI already has ${VERSION} — bump pyproject.toml and package.json, then re-run"
fi
[ "${DO_PYPI}" -eq 1 ] && ok "PyPI does not have ${VERSION}"
if [ "${DO_NPM}" -eq 1 ] && npm view "@carla-simulator/agentic-tools@${VERSION}" version >/dev/null 2>&1; then
  bad "npm already has ${VERSION} — bump both versions, then re-run"
fi
[ "${DO_NPM}" -eq 1 ] && ok "npm does not have ${VERSION}"

# --- build ------------------------------------------------------------------

say "Build"
rm -rf dist/
"${PYTHON}" -m build >/tmp/cat-build.$$ 2>&1 || { tail -25 /tmp/cat-build.$$ >&2; bad "build failed"; }
rm -f /tmp/cat-build.$$
ok "$(ls dist/ | tr '\n' ' ')"
"${PYTHON}" -m twine check dist/* >/dev/null || bad "twine check failed"
ok "twine check"

# The skills are the product. A wheel or a tarball without them installs a
# server with an empty registry, which is silent until someone calls list_skills.
WHEEL_SKILLS="$("${PYTHON}" - <<'PY'
import glob, zipfile
w = glob.glob("dist/*.whl")[0]
print(sum(1 for n in zipfile.ZipFile(w).namelist() if n.endswith("/SKILL.md")))
PY
)"
[ "${WHEEL_SKILLS}" -gt 0 ] || bad "the wheel carries no SKILL.md"
ok "wheel carries ${WHEEL_SKILLS} skills"

npm pack --dry-run >/tmp/cat-npm.$$ 2>&1 || { cat /tmp/cat-npm.$$ >&2; bad "npm pack failed"; }
NPM_SKILLS="$(grep -c 'SKILL\.md' /tmp/cat-npm.$$ || true)"
[ "${NPM_SKILLS}" = "${WHEEL_SKILLS}" ] \
  || bad "npm tarball has ${NPM_SKILLS} skills, wheel has ${WHEEL_SKILLS} — they must match"
grep -q 'README.md' /tmp/cat-npm.$$ || bad "npm tarball has no README"
ok "npm tarball carries the same ${NPM_SKILLS} skills"
rm -f /tmp/cat-npm.$$ ./*.tgz

if [ "${CHECK_ONLY}" -eq 1 ]; then
  say "Check only — nothing published"
  note "run without --check to publish"
  exit 0
fi

PUBLISHED_PYPI=0

# --- PyPI -------------------------------------------------------------------

if [ "${DO_PYPI}" -eq 1 ]; then
  say "PyPI"
  note "The username is always __token__; the password is an API token from"
  note "https://pypi.org/manage/account/token/"
  export TWINE_USERNAME="__token__"
  if [ -n "${TWINE_PASSWORD:-}" ]; then
    note "using TWINE_PASSWORD from the environment"
  else
    printf '  PyPI API token (not echoed): '
    read -rs TWINE_PASSWORD
    printf '\n'
    export TWINE_PASSWORD
  fi
  [ -n "${TWINE_PASSWORD}" ] || bad "no token given"
  case "${TWINE_PASSWORD}" in
    pypi-*) ok "token looks well-formed" ;;
    *) note "WARN the token does not start with 'pypi-'; the upload will likely 403" ;;
  esac

  if confirm "Publish carla-agentic-tools ${VERSION} to PyPI? This cannot be undone."; then
    "${PYTHON}" -m twine upload dist/* || bad "upload failed"
    ok "published carla-agentic-tools ${VERSION} to PyPI"
    PUBLISHED_PYPI=1
  fi
  unset TWINE_PASSWORD
fi

# --- npm --------------------------------------------------------------------

if [ "${DO_NPM}" -eq 1 ]; then
  say "npm"
  note "Needs an automation token from https://www.npmjs.com/settings/~/tokens"
  note "and publish rights on the @carla-simulator org."
  if [ -n "${NPM_TOKEN:-}" ]; then
    note "using NPM_TOKEN from the environment"
  else
    printf '  npm token (not echoed): '
    read -rs NPM_TOKEN
    printf '\n'
  fi
  [ -n "${NPM_TOKEN}" ] || bad "no token given"

  # A token in a file is a credential on disk: keep it out of the repo, make it
  # unreadable to anyone else, and delete it however this script exits.
  NPMRC="$(mktemp)"
  chmod 600 "${NPMRC}"
  trap 'rm -f "${NPMRC}"' EXIT INT TERM
  printf '//registry.npmjs.org/:_authToken=%s\n' "${NPM_TOKEN}" > "${NPMRC}"

  # Scoped packages default to restricted; without this the package publishes
  # private and every `npx` gets a 404.
  if confirm "Publish @carla-simulator/agentic-tools ${VERSION} to npm? Unpublishable after 72h."; then
    NPM_CONFIG_USERCONFIG="${NPMRC}" npm publish --access public || bad "npm publish failed"
    ok "published @carla-simulator/agentic-tools ${VERSION} to npm"
  fi
fi

# --- verify -----------------------------------------------------------------

say "Verify"
note "The two packages are independent — the npm one carries the skills and a"
note "Node server, so it needs no Python. Both should answer identically:"
note ""
note "  npx -y @carla-simulator/agentic-tools@${VERSION}"
note "  uvx carla-agentic-tools@${VERSION}"
note ""
note "An index can take a minute to serve a new version."
if [ "${PUBLISHED_PYPI}" -eq 1 ]; then
  note "Register it with a client, with no paths — the skills record what they need:"
  note "  claude mcp add carla -s user -- npx -y @carla-simulator/agentic-tools"
fi
