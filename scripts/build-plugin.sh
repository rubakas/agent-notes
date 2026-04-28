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

for skill_dir in .claude-plugin/skills/*/; do
  skill=$(basename "$skill_dir")
  src="agent_notes/dist/skills/$skill/SKILL.md"
  if [ -f "$src" ]; then
    cp "$src" ".claude-plugin/skills/$skill/SKILL.md"
  fi
done
echo "Plugin skills synced."

VERSION=$(cat agent_notes/VERSION)
python3 - <<EOF
import json, pathlib
p = pathlib.Path('.claude-plugin/plugin.json')
m = json.loads(p.read_text())
m['version'] = '${VERSION}'
p.write_text(json.dumps(m, indent=2) + '\n')
EOF
echo "Plugin version set to ${VERSION}."
