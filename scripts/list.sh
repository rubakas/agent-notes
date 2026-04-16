#!/usr/bin/env bash
set -e
AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
DIM='\033[2m'
NC='\033[0m'

FILTER="${1:-all}"

list_agents() {
  echo -e "${CYAN}Agents:${NC}"
  for f in "$AGENT_NOTES_DIR"/source/agents/*.md; do
    [ -f "$f" ] || continue
    local name=$(basename "$f" .md)
    # Get tier and description from agents.yaml
    if [ -f "$AGENT_NOTES_DIR/source/agents.yaml" ]; then
      local tier=$(grep -A10 "^  ${name}:" "$AGENT_NOTES_DIR/source/agents.yaml" 2>/dev/null | grep "tier:" | head -1 | sed 's/.*tier: *//' || echo "")
      local desc=$(grep -A10 "^  ${name}:" "$AGENT_NOTES_DIR/source/agents.yaml" 2>/dev/null | grep "description:" | head -1 | sed 's/.*description: *"//' | sed 's/".*//' || echo "")
      printf "  %-22s ${DIM}%-8s${NC} %s\n" "$name" "($tier)" "$desc"
    else
      printf "  %s\n" "$name"
    fi
  done
  echo ""
}

list_skills() {
  echo -e "${CYAN}Skills:${NC}"
  for d in "$AGENT_NOTES_DIR"/*/; do
    [ -f "${d}SKILL.md" ] || continue
    local name=$(basename "$d")
    printf "  %s\n" "$name"
  done
  echo ""
}

list_rules() {
  echo -e "${CYAN}Rules:${NC}"
  for f in "$AGENT_NOTES_DIR"/source/rules/*.md; do
    [ -f "$f" ] || continue
    printf "  %s\n" "$(basename "$f" .md)"
  done
  echo ""
  echo -e "${CYAN}Global configs:${NC}"
  echo "  global.md"
  echo "  global-copilot.md"
  echo ""
}

case "$FILTER" in
  agents) list_agents ;;
  skills) list_skills ;;
  rules)  list_rules ;;
  all)    list_agents; list_skills; list_rules ;;
  --help|-h)
    echo "Usage: list [agents|skills|rules]"
    echo "Lists installed components. Shows all if no filter given."
    ;;
  *)
    echo "Unknown filter: $FILTER"
    echo "Usage: list [agents|skills|rules]"
    exit 1
    ;;
esac