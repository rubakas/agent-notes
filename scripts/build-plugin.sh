#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m agent_notes.commands.build
rm -rf .claude-plugin/agents
mkdir -p .claude-plugin/agents
for f in agent_notes/dist/claude/agents/*.md; do
  name=$(basename "$f")
  if [ "$name" != "lead.md" ]; then
    cp "$f" ".claude-plugin/agents/$name"
  fi
done
echo "Plugin agents rebuilt."
