#!/usr/bin/env bash
set -e
AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Building agent-notes from source/ ..."

if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required for build."
  exit 1
fi

python3 "$AGENT_NOTES_DIR/lib/generate.py" "$AGENT_NOTES_DIR"

echo "Done."