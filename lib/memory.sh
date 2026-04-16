#!/usr/bin/env bash
#
# memory.sh — Manage agent memory stored in ~/.claude/agent-memory/.
#
# Usage:
#   memory.sh                     List all agent memories with sizes
#   memory.sh --list              Same as above
#   memory.sh --size              Total disk usage
#   memory.sh --show <name>       Show memory contents for one agent
#   memory.sh --reset             Clear ALL memories (requires confirmation)
#   memory.sh --reset <name>      Clear one agent's memory
#   memory.sh --export            Copy memories to agent-notes/memory-backup/
#   memory.sh --import            Restore from agent-notes/memory-backup/
#
set -e

AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MEMORY_DIR="$HOME/.claude/agent-memory"
BACKUP_DIR="$AGENT_NOTES_DIR/memory-backup"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# --- Functions ---

do_list() {
  if [ ! -d "$MEMORY_DIR" ] || [ -z "$(ls -A "$MEMORY_DIR" 2>/dev/null)" ]; then
    echo "No agent memories found in $MEMORY_DIR"
    exit 0
  fi

  echo "Agent memories ($MEMORY_DIR):"
  echo ""
  printf "  %-25s %s\n" "AGENT" "SIZE"
  printf "  %-25s %s\n" "-----" "----"
  for d in "$MEMORY_DIR"/*/; do
    [ -d "$d" ] || continue
    name=$(basename "$d")
    size=$(du -sh "$d" 2>/dev/null | cut -f1)
    printf "  %-25s %s\n" "$name" "$size"
  done
}

do_size() {
  if [ ! -d "$MEMORY_DIR" ]; then
    echo "No agent memories found."
    exit 0
  fi
  echo "Total memory usage:"
  du -sh "$MEMORY_DIR" 2>/dev/null | awk '{print "  " $1}'
}

do_show() {
  local name="$1"
  local dir="$MEMORY_DIR/$name"
  if [ ! -d "$dir" ]; then
    echo "No memory found for agent '$name'"
    echo "Available: $(ls "$MEMORY_DIR" 2>/dev/null | tr '\n' ' ')"
    exit 1
  fi

  echo "Memory for agent '$name' ($dir):"
  echo ""
  for f in "$dir"/*; do
    [ -f "$f" ] || continue
    echo -e "${CYAN}--- $(basename "$f") ---${NC}"
    cat "$f"
    echo ""
  done
}

do_reset() {
  local name="$1"

  if [ -n "$name" ]; then
    local dir="$MEMORY_DIR/$name"
    if [ ! -d "$dir" ]; then
      echo "No memory found for agent '$name'"
      exit 1
    fi
    echo -e "${YELLOW}This will delete all memory for agent '$name'.${NC}"
    read -r -p "Continue? [y/N] " confirm
    if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
      rm -rf "$dir"
      echo -e "${GREEN}Memory for '$name' cleared.${NC}"
    else
      echo "Cancelled."
    fi
  else
    if [ ! -d "$MEMORY_DIR" ] || [ -z "$(ls -A "$MEMORY_DIR" 2>/dev/null)" ]; then
      echo "No agent memories to clear."
      exit 0
    fi
    echo -e "${RED}This will delete ALL agent memories.${NC}"
    echo "Contents of $MEMORY_DIR:"
    ls -1 "$MEMORY_DIR" 2>/dev/null | sed 's/^/  /'
    echo ""
    read -r -p "Type 'yes' to confirm: " confirm
    if [ "$confirm" = "yes" ]; then
      rm -rf "$MEMORY_DIR"/*
      echo -e "${GREEN}All agent memories cleared.${NC}"
    else
      echo "Cancelled."
    fi
  fi
}

do_export() {
  if [ ! -d "$MEMORY_DIR" ] || [ -z "$(ls -A "$MEMORY_DIR" 2>/dev/null)" ]; then
    echo "No agent memories to export."
    exit 0
  fi
  mkdir -p "$BACKUP_DIR"
  cp -r "$MEMORY_DIR"/* "$BACKUP_DIR/"
  echo -e "${GREEN}Exported to $BACKUP_DIR${NC}"
  echo "Contents:"
  ls -1 "$BACKUP_DIR" | sed 's/^/  /'
  echo ""
  echo -e "${YELLOW}Note: memory-backup/ is in .gitignore — these are personal learnings.${NC}"
}

do_import() {
  if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR" 2>/dev/null)" ]; then
    echo "No backup found in $BACKUP_DIR"
    exit 1
  fi
  mkdir -p "$MEMORY_DIR"
  cp -r "$BACKUP_DIR"/* "$MEMORY_DIR/"
  echo -e "${GREEN}Imported from $BACKUP_DIR to $MEMORY_DIR${NC}"
  echo "Restored agents:"
  ls -1 "$MEMORY_DIR" | sed 's/^/  /'
}

do_help() {
  cat <<'EOF'
Usage: memory.sh [command] [agent-name]

Manage agent memory stored in ~/.claude/agent-memory/.

Commands:
  (none)           List all agent memories with sizes
  --list           Same as above
  --size           Total disk usage
  --show <name>    Show memory contents for one agent
  --reset          Clear ALL memories (requires confirmation)
  --reset <name>   Clear one agent's memory
  --export         Back up memories to agent-notes/memory-backup/
  --import         Restore from agent-notes/memory-backup/
  --help           Show this help

Examples:
  memory.sh                    List all memories
  memory.sh --show coder       View coder agent's memory
  memory.sh --reset reviewer   Clear reviewer's memory
  memory.sh --export           Back up before cleanup
EOF
}

# --- Main ---

case "${1:-}" in
  ""|--list)
    do_list
    ;;
  --size)
    do_size
    ;;
  --show)
    [ -z "${2:-}" ] && { echo "Error: --show requires an agent name."; exit 1; }
    do_show "$2"
    ;;
  --reset)
    do_reset "${2:-}"
    ;;
  --export)
    do_export
    ;;
  --import)
    do_import
    ;;
  --help|-h)
    do_help
    ;;
  *)
    echo "Unknown command: $1"
    do_help
    exit 1
    ;;
esac
