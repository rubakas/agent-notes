#!/usr/bin/env bash
#
# uninstall.sh — Remove agent-notes components installed by install.sh.
#
# Usage: uninstall.sh <what> <where>
#
# What:   all | skills | agents | rules
# Where:  global | local
#
# Only removes symlinks pointing to the agent-notes repo.
# Non-symlink files are reported but not deleted.
#
set -e

AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

removed() { echo -e "  ${GREEN}REMOVED${NC}  $1"; }
skipped() { echo -e "  ${YELLOW}SKIP${NC}     $1 (not a symlink — remove manually)"; }
missing() { echo -e "  ${YELLOW}SKIP${NC}     $1 (not found)"; }

# --- Helpers ---

remove_symlink() {
  local target="$1"
  if [ -L "$target" ]; then
    rm "$target"
    removed "$target"
  elif [ -e "$target" ]; then
    skipped "$target"
  fi
}

remove_symlinks_in_dir() {
  local dir="$1" pattern="$2"
  [ -d "$dir" ] || return
  for f in "$dir"/$pattern; do
    [ -e "$f" ] || [ -L "$f" ] || continue
    remove_symlink "$f"
  done
}

# --- Uninstall functions ---

uninstall_skills_global() {
  local targets=("$HOME/.claude/skills" "$HOME/.config/opencode/skills" "$HOME/.agents/skills")
  for target_dir in "${targets[@]}"; do
    [ -d "$target_dir" ] || continue
    echo "Removing skills from $target_dir ..."
    for skill_dir in "$AGENT_NOTES_DIR"/*/; do
      [ -f "${skill_dir}SKILL.md" ] || continue
      local name
      name=$(basename "$skill_dir")
      remove_symlink "$target_dir/$name"
    done
  done
}

uninstall_skills_local() {
  local targets=(".claude/skills" ".opencode/skills")
  for target_dir in "${targets[@]}"; do
    [ -d "$target_dir" ] || continue
    echo "Removing skills from $target_dir ..."
    for skill_dir in "$AGENT_NOTES_DIR"/*/; do
      [ -f "${skill_dir}SKILL.md" ] || continue
      local name
      name=$(basename "$skill_dir")
      remove_symlink "$target_dir/$name"
    done
  done
}

uninstall_agents_global() {
  echo "Removing Claude Code agents from ~/.claude/agents/ ..."
  for f in "$AGENT_NOTES_DIR"/agents/*.md; do
    [ -f "$f" ] || continue
    remove_symlink "$HOME/.claude/agents/$(basename "$f")"
  done

  echo "Removing OpenCode agents from ~/.config/opencode/agents/ ..."
  for f in "$AGENT_NOTES_DIR"/agents-opencode/*.md; do
    [ -f "$f" ] || continue
    remove_symlink "$HOME/.config/opencode/agents/$(basename "$f")"
  done
}

uninstall_agents_local() {
  echo "Removing Claude Code agents from .claude/agents/ ..."
  for f in "$AGENT_NOTES_DIR"/agents/*.md; do
    [ -f "$f" ] || continue
    remove_symlink ".claude/agents/$(basename "$f")"
  done

  echo "Removing OpenCode agents from .opencode/agents/ ..."
  for f in "$AGENT_NOTES_DIR"/agents-opencode/*.md; do
    [ -f "$f" ] || continue
    remove_symlink ".opencode/agents/$(basename "$f")"
  done
}

uninstall_rules_global() {
  echo "Removing global config ..."
  remove_symlink "$HOME/.claude/CLAUDE.md"
  remove_symlink "$HOME/.config/opencode/AGENTS.md"
  remove_symlink "$HOME/.github/copilot-instructions.md"
  for f in "$AGENT_NOTES_DIR"/global/rules/*.md; do
    [ -f "$f" ] || continue
    remove_symlink "$HOME/.claude/rules/$(basename "$f")"
  done
}

uninstall_rules_local() {
  echo "Removing project rules ..."
  remove_symlink "./CLAUDE.md"
  remove_symlink "./AGENTS.md"
  for f in "$AGENT_NOTES_DIR"/global/rules/*.md; do
    [ -f "$f" ] || continue
    remove_symlink ".claude/rules/$(basename "$f")"
  done
}

# --- Help ---

do_help() {
  cat <<'EOF'
Usage: uninstall.sh <what> <where>

Remove agent-notes components installed by install.sh.

Arguments:
  <what>    What to remove:
              all      Everything (skills + agents + rules)
              skills   Skill directories only
              agents   Agent definitions only
              rules    Rules/instructions only

  <where>   Where to remove from:
              global   User home (~/.claude/, ~/.config/opencode/, ~/.github/)
              local    Current project directory

Notes:
  Only removes symlinks. Non-symlink files (e.g., from --copy installs)
  are reported but not deleted — remove them manually.

Examples:
  uninstall.sh all global        Remove all global installs
  uninstall.sh agents global     Remove only global agents
  uninstall.sh all local         Remove all project-level installs
EOF
}

# --- Main ---

WHAT=""
WHERE=""

for arg in "$@"; do
  case "$arg" in
    all|skills|agents|rules)
      [ -z "$WHAT" ] && WHAT="$arg" || WHERE="$arg"
      ;;
    global|local)
      WHERE="$arg"
      ;;
    --help|-h)
      do_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Run 'uninstall.sh --help' for usage."
      exit 1
      ;;
  esac
done

if [ -z "$WHAT" ] || [ -z "$WHERE" ]; then
  echo "Error: Both <what> and <where> are required."
  echo ""
  do_help
  exit 1
fi

echo "Uninstalling $WHAT ($WHERE) ..."
echo ""

case "$WHAT" in
  all)
    if [ "$WHERE" = "global" ]; then
      uninstall_skills_global
      uninstall_agents_global
      uninstall_rules_global
    else
      uninstall_skills_local
      uninstall_agents_local
      uninstall_rules_local
    fi
    ;;
  skills)
    [ "$WHERE" = "global" ] && uninstall_skills_global || uninstall_skills_local
    ;;
  agents)
    [ "$WHERE" = "global" ] && uninstall_agents_global || uninstall_agents_local
    ;;
  rules)
    [ "$WHERE" = "global" ] && uninstall_rules_global || uninstall_rules_local
    ;;
esac

echo ""
echo -e "${GREEN}Done.${NC}"
