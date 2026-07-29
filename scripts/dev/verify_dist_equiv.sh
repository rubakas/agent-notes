#!/usr/bin/env bash
# Real byte-identical dist gate.
#
# WHY THIS EXISTS: `agent_notes/dist/` is gitignored, so `git diff`/`git status`
# on it is ALWAYS empty and reports "byte-identical" even when build output
# changed — a gate with no teeth. This script instead builds dist from HEAD and
# from a baseline ref, then sha256-compares the built trees.
#
# Usage:  scripts/dev/verify_dist_equiv.sh [BASE_REF]
#   BASE_REF defaults to the merge-base of HEAD and origin/develop (the branch
#   point). Pass an explicit ref to compare against something else.
set -euo pipefail

# Locate the repo from this script's own path (works from any cwd).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY="$(command -v python3)"

BASE_REF="${1:-$(git -C "$REPO" merge-base HEAD origin/develop 2>/dev/null || echo "")}"
if [ -z "$BASE_REF" ]; then
  echo "Could not determine BASE_REF (pass one explicitly)."; exit 2
fi

# Pin state so the developer's live ~/.config state.json can't perturb the build.
XDG="$(mktemp -d)"
WT="$(mktemp -d)/wt-base"

# Portable sha256 (Linux CI has sha256sum; macOS has shasum).
if command -v sha256sum >/dev/null 2>&1; then SHA() { sha256sum "$@"; }
else SHA() { shasum -a 256 "$@"; }; fi

checksum_dist() {
  # Exclude *.bak* backup artifacts (created by install, not build).
  local dir="$1"
  ( cd "$dir" && find agent_notes/dist -type f ! -name '*.bak*' | LC_ALL=C sort | while read -r f; do
      printf '%s  ' "$f"; SHA "$f" | awk '{print $1}'
    done ) | SHA | awk '{print $1}'
}

build_in() {
  local dir="$1"
  rm -rf "$dir/agent_notes/dist"
  ( cd "$dir" && PYTHONPATH="$dir" XDG_CONFIG_HOME="$XDG" "$PY" -c \
      "import agent_notes; print('  using:', agent_notes.__file__); \
from agent_notes.commands.build import build; build()" ) >/dev/null
}

echo "== build HEAD dist =="
build_in "$REPO"
HEAD_SUM="$(checksum_dist "$REPO")"
echo "HEAD dist checksum: $HEAD_SUM  ($(cd "$REPO" && find agent_notes/dist -type f ! -name '*.bak*' | wc -l | tr -d ' ') files)"

echo "== build baseline dist ($BASE_REF) =="
rm -rf "$WT"; git -C "$REPO" worktree add --detach "$WT" "$BASE_REF" >/dev/null 2>&1
build_in "$WT"
BASE_SUM="$(checksum_dist "$WT")"
echo "BASE dist checksum: $BASE_SUM  ($(cd "$WT" && find agent_notes/dist -type f ! -name '*.bak*' | wc -l | tr -d ' ') files)"

RC=0
if [ "$HEAD_SUM" = "$BASE_SUM" ]; then
  echo "RESULT: BYTE-IDENTICAL ✓"
else
  echo "RESULT: DRIFT ✗"
  diff <(cd "$WT"   && find agent_notes/dist -type f ! -name '*.bak*' | LC_ALL=C sort | while read -r f; do echo "$f $(SHA "$f"|awk '{print $1}')"; done) \
       <(cd "$REPO" && find agent_notes/dist -type f ! -name '*.bak*' | LC_ALL=C sort | while read -r f; do echo "$f $(SHA "$f"|awk '{print $1}')"; done) | head -60 || true
  RC=1
fi

# Rebuild HEAD dist so the working tree reflects current source, and clean up.
( cd "$REPO" && PYTHONPATH="$REPO" XDG_CONFIG_HOME="$XDG" "$PY" -c "from agent_notes.commands.build import build; build()" ) >/dev/null 2>&1 || true
git -C "$REPO" worktree remove --force "$WT" >/dev/null 2>&1 || true
rm -rf "$XDG" "$(dirname "$WT")"
exit "$RC"
