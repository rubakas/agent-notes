#!/usr/bin/env bash
#
# install.sh — Install agent-notes components (skills, agents, rules).
#
# Usage:
#   install.sh <what> <where> [--copy]
#   install.sh --check | --info | --help
#
# What:   all | skills | agents | rules
# Where:  global | local
# Flags:  --copy  Copy files instead of symlink (only with 'local')
#
set -e

AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ok()   { echo -e "  ${GREEN}OK${NC}      $1"; }
warn() { echo -e "  ${YELLOW}WARN${NC}    $1"; }
fail() { echo -e "  ${RED}FAIL${NC}    $1"; }
info() { echo -e "  ${CYAN}INFO${NC}    $1"; }
link() { echo -e "  ${GREEN}LINKED${NC}  $1"; }
copy() { echo -e "  ${GREEN}COPIED${NC}  $1"; }
skip() { echo -e "  ${YELLOW}SKIP${NC}    $1"; }

# --- Helpers ---

place_file() {
  local src="$1" dst="$2" mode="$3"
  local dst_dir
  dst_dir="$(dirname "$dst")"
  mkdir -p "$dst_dir"

  if [ "$mode" = "copy" ]; then
    if [ -e "$dst" ] && [ ! -L "$dst" ]; then
      skip "$dst (exists, not a symlink)"
      return
    fi
    [ -L "$dst" ] && rm "$dst"
    cp -r "$src" "$dst"
    copy "$dst"
  else
    if [ -e "$dst" ] && [ ! -L "$dst" ]; then
      skip "$dst (exists, not a symlink)"
      return
    fi
    ln -sf "$src" "$dst"
    link "$dst"
  fi
}

place_dir_contents() {
  local src_dir="$1" dst_dir="$2" pattern="$3" mode="$4"
  mkdir -p "$dst_dir"
  for src_file in "$src_dir"/$pattern; do
    [ -e "$src_file" ] || continue
    local name
    name=$(basename "$src_file")
    place_file "$src_file" "$dst_dir/$name" "$mode"
  done
}

count_skills() {
  local count=0
  for d in "$AGENT_NOTES_DIR"/*/; do
    [ -f "${d}SKILL.md" ] && count=$((count + 1))
  done
  echo "$count"
}

count_agents_claude() {
  local count=0
  for f in "$AGENT_NOTES_DIR"/agents/*.md; do
    [ -f "$f" ] && count=$((count + 1))
  done
  echo "$count"
}

count_agents_opencode() {
  local count=0
  for f in "$AGENT_NOTES_DIR"/agents-opencode/*.md; do
    [ -f "$f" ] && count=$((count + 1))
  done
  echo "$count"
}

count_global() {
  local count=0
  [ -f "$AGENT_NOTES_DIR/global/CLAUDE.md" ] && count=$((count + 1))
  [ -f "$AGENT_NOTES_DIR/global/AGENTS.md" ] && count=$((count + 1))
  [ -f "$AGENT_NOTES_DIR/global/copilot-instructions.md" ] && count=$((count + 1))
  for f in "$AGENT_NOTES_DIR"/global/rules/*.md; do
    [ -f "$f" ] && count=$((count + 1))
  done
  echo "$count"
}

# --- Install functions ---

install_skills_global() {
  local mode="$1"
  local targets=("$HOME/.claude/skills" "$HOME/.config/opencode/skills" "$HOME/.agents/skills")
  for target_dir in "${targets[@]}"; do
    echo "Installing skills to $target_dir ..."
    mkdir -p "$target_dir"
    for skill_dir in "$AGENT_NOTES_DIR"/*/; do
      [ -f "${skill_dir}SKILL.md" ] || continue
      local skill_name
      skill_name=$(basename "$skill_dir")
      place_file "$skill_dir" "$target_dir/$skill_name" "$mode"
    done
  done
}

install_skills_local() {
  local mode="$1"
  local targets=(".claude/skills" ".opencode/skills")
  for target_dir in "${targets[@]}"; do
    echo "Installing skills to $target_dir ..."
    mkdir -p "$target_dir"
    for skill_dir in "$AGENT_NOTES_DIR"/*/; do
      [ -f "${skill_dir}SKILL.md" ] || continue
      local skill_name
      skill_name=$(basename "$skill_dir")
      place_file "$skill_dir" "$target_dir/$skill_name" "$mode"
    done
  done
}

install_agents_global() {
  local mode="$1"
  echo "Installing Claude Code agents to ~/.claude/agents/ ..."
  place_dir_contents "$AGENT_NOTES_DIR/agents" "$HOME/.claude/agents" "*.md" "$mode"

  echo "Installing OpenCode agents to ~/.config/opencode/agents/ ..."
  place_dir_contents "$AGENT_NOTES_DIR/agents-opencode" "$HOME/.config/opencode/agents" "*.md" "$mode"
}

install_agents_local() {
  local mode="$1"
  echo "Installing Claude Code agents to .claude/agents/ ..."
  place_dir_contents "$AGENT_NOTES_DIR/agents" ".claude/agents" "*.md" "$mode"

  echo "Installing OpenCode agents to .opencode/agents/ ..."
  place_dir_contents "$AGENT_NOTES_DIR/agents-opencode" ".opencode/agents" "*.md" "$mode"
}

install_rules_global() {
  local mode="$1"
  echo "Installing global config ..."

  # CLAUDE.md → ~/.claude/CLAUDE.md
  [ -f "$AGENT_NOTES_DIR/global/CLAUDE.md" ] && \
    place_file "$AGENT_NOTES_DIR/global/CLAUDE.md" "$HOME/.claude/CLAUDE.md" "$mode"

  # AGENTS.md → ~/.config/opencode/AGENTS.md
  [ -f "$AGENT_NOTES_DIR/global/AGENTS.md" ] && \
    place_file "$AGENT_NOTES_DIR/global/AGENTS.md" "$HOME/.config/opencode/AGENTS.md" "$mode"

  # Rules → ~/.claude/rules/
  place_dir_contents "$AGENT_NOTES_DIR/global/rules" "$HOME/.claude/rules" "*.md" "$mode"

  # Copilot → ~/.github/copilot-instructions.md
  [ -f "$AGENT_NOTES_DIR/global/copilot-instructions.md" ] && \
    place_file "$AGENT_NOTES_DIR/global/copilot-instructions.md" "$HOME/.github/copilot-instructions.md" "$mode"
}

install_rules_local() {
  local mode="$1"
  echo "Installing project rules ..."

  # CLAUDE.md → ./CLAUDE.md
  [ -f "$AGENT_NOTES_DIR/global/CLAUDE.md" ] && \
    place_file "$AGENT_NOTES_DIR/global/CLAUDE.md" "./CLAUDE.md" "$mode"

  # AGENTS.md → ./AGENTS.md
  [ -f "$AGENT_NOTES_DIR/global/AGENTS.md" ] && \
    place_file "$AGENT_NOTES_DIR/global/AGENTS.md" "./AGENTS.md" "$mode"

  # Rules → .claude/rules/
  place_dir_contents "$AGENT_NOTES_DIR/global/rules" ".claude/rules" "*.md" "$mode"
}

# --- --check ---

do_check() {
  local issues=0

  echo "Checking global installation ..."

  # Claude agents
  for f in "$AGENT_NOTES_DIR"/agents/*.md; do
    [ -f "$f" ] || continue
    local name target
    name=$(basename "$f")
    target="$HOME/.claude/agents/$name"
    if [ ! -e "$target" ]; then
      fail "$target  MISSING"
      issues=$((issues + 1))
    elif [ ! -L "$target" ]; then
      warn "$target  SHADOWED (not a symlink)"
      issues=$((issues + 1))
    elif [ ! -e "$(readlink "$target")" ]; then
      fail "$target  BROKEN (target does not exist)"
      issues=$((issues + 1))
    else
      ok "$target"
    fi
  done

  # OpenCode agents
  for f in "$AGENT_NOTES_DIR"/agents-opencode/*.md; do
    [ -f "$f" ] || continue
    local name target
    name=$(basename "$f")
    target="$HOME/.config/opencode/agents/$name"
    if [ ! -e "$target" ]; then
      fail "$target  MISSING"
      issues=$((issues + 1))
    elif [ ! -L "$target" ]; then
      warn "$target  SHADOWED (not a symlink)"
      issues=$((issues + 1))
    elif [ ! -e "$(readlink "$target")" ]; then
      fail "$target  BROKEN (target does not exist)"
      issues=$((issues + 1))
    else
      ok "$target"
    fi
  done

  # Skills (check ~/.claude/skills only for brevity)
  for skill_dir in "$AGENT_NOTES_DIR"/*/; do
    [ -f "${skill_dir}SKILL.md" ] || continue
    local skill_name target
    skill_name=$(basename "$skill_dir")
    target="$HOME/.claude/skills/$skill_name"
    if [ ! -e "$target" ]; then
      fail "$target  MISSING"
      issues=$((issues + 1))
    elif [ ! -L "$target" ]; then
      warn "$target  SHADOWED (not a symlink)"
      issues=$((issues + 1))
    elif [ ! -e "$(readlink "$target")" ]; then
      fail "$target  BROKEN"
      issues=$((issues + 1))
    else
      ok "$target"
    fi
  done

  # Global config files
  local global_targets=(
    "$HOME/.claude/CLAUDE.md"
    "$HOME/.config/opencode/AGENTS.md"
    "$HOME/.github/copilot-instructions.md"
  )
  for target in "${global_targets[@]}"; do
    if [ ! -e "$target" ]; then
      fail "$target  MISSING"
      issues=$((issues + 1))
    elif [ ! -L "$target" ]; then
      warn "$target  SHADOWED (not a symlink)"
      issues=$((issues + 1))
    else
      ok "$target"
    fi
  done

  # Rules
  for f in "$AGENT_NOTES_DIR"/global/rules/*.md; do
    [ -f "$f" ] || continue
    local name target
    name=$(basename "$f")
    target="$HOME/.claude/rules/$name"
    if [ ! -e "$target" ]; then
      fail "$target  MISSING"
      issues=$((issues + 1))
    elif [ ! -L "$target" ]; then
      warn "$target  SHADOWED (not a symlink)"
      issues=$((issues + 1))
    else
      ok "$target"
    fi
  done

  echo ""
  if [ "$issues" -gt 0 ]; then
    echo -e "${RED}$issues issue(s) found.${NC} Run 'install.sh all global' to fix."
    exit 1
  else
    echo -e "${GREEN}All checks passed.${NC}"
    exit 0
  fi
}

# --- --info ---

do_info() {
  echo "agent-notes"
  echo ""
  echo "Components:"
  echo "  Skills:              $(count_skills)"
  echo "  Agents (Claude):     $(count_agents_claude)"
  echo "  Agents (OpenCode):   $(count_agents_opencode)"
  echo "  Global config:       $(count_global) files"
  echo ""
  echo "Install targets:"
  echo "  Claude Code:   ~/.claude/"
  echo "  OpenCode:      ~/.config/opencode/"
  echo "  Copilot:       ~/.github/"
  echo "  Universal:     ~/.agents/"
  echo ""

  # Check install status
  local global_ok=true local_ok=true
  [ -d "$HOME/.claude/agents" ] && [ "$(ls -A "$HOME/.claude/agents" 2>/dev/null)" ] || global_ok=false
  [ -d ".claude/agents" ] && [ "$(ls -A .claude/agents 2>/dev/null)" ] && local_ok=true || local_ok=false

  echo "Status:"
  if [ "$global_ok" = true ]; then
    echo -e "  Global:  ${GREEN}installed${NC} (use --check for details)"
  else
    echo -e "  Global:  ${YELLOW}not installed${NC}"
  fi
  if [ "$local_ok" = true ]; then
    echo -e "  Local:   ${GREEN}detected${NC}"
  else
    echo -e "  Local:   ${CYAN}not detected${NC}"
  fi
}

# --- Help ---

do_help() {
  cat <<'EOF'
Usage: install.sh <what> <where> [--copy]
       install.sh --check | --info | --help

Install agent-notes components as symlinks or copies.

Arguments:
  <what>    What to install:
              all      Everything (skills + agents + rules)
              skills   Skill directories only (SKILL.md)
              agents   Agent definitions only (Claude + OpenCode)
              rules    Rules/instructions only (CLAUDE.md, AGENTS.md, rules/, copilot)

  <where>   Where to install:
              global   User home (~/.claude/, ~/.config/opencode/, ~/.github/)
              local    Current project directory (.claude/, .opencode/)

Flags:
  --copy    Copy files instead of symlink (only valid with 'local')

Management:
  --check   Validate existing global symlinks
  --info    Show component counts and install status
  --help    Show this help

Examples:
  install.sh all global              Install everything globally (symlinks)
  install.sh skills global           Only skills, globally
  install.sh agents local            Symlink agents into current project
  install.sh agents local --copy     Copy agents into project (editable)
  install.sh rules local --copy      Copy rules into project for customization
  install.sh all local --copy        Full standalone project setup
EOF
}

# --- Main ---

WHAT=""
WHERE=""
MODE="symlink"

for arg in "$@"; do
  case "$arg" in
    all|skills|agents|rules)
      [ -z "$WHAT" ] && WHAT="$arg" || WHERE="$arg"
      ;;
    global|local)
      WHERE="$arg"
      ;;
    --copy)
      MODE="copy"
      ;;
    --check)
      do_check
      exit $?
      ;;
    --info)
      do_info
      exit 0
      ;;
    --help|-h)
      do_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg"
      echo "Run 'install.sh --help' for usage."
      exit 1
      ;;
  esac
done

# Validate args
if [ -z "$WHAT" ] || [ -z "$WHERE" ]; then
  echo "Error: Both <what> and <where> are required."
  echo ""
  do_help
  exit 1
fi

if [ "$MODE" = "copy" ] && [ "$WHERE" = "global" ]; then
  echo "Error: --copy is only valid with 'local' installs."
  echo "Global installs always use symlinks."
  exit 1
fi

# Execute
echo "Installing $WHAT ($WHERE, $MODE) ..."
echo ""

case "$WHAT" in
  all)
    if [ "$WHERE" = "global" ]; then
      install_skills_global "$MODE"
      install_agents_global "$MODE"
      install_rules_global "$MODE"
    else
      install_skills_local "$MODE"
      install_agents_local "$MODE"
      install_rules_local "$MODE"
    fi
    ;;
  skills)
    if [ "$WHERE" = "global" ]; then
      install_skills_global "$MODE"
    else
      install_skills_local "$MODE"
    fi
    ;;
  agents)
    if [ "$WHERE" = "global" ]; then
      install_agents_global "$MODE"
    else
      install_agents_local "$MODE"
    fi
    ;;
  rules)
    if [ "$WHERE" = "global" ]; then
      install_rules_global "$MODE"
    else
      install_rules_local "$MODE"
    fi
    ;;
esac

echo ""
echo -e "${GREEN}Done.${NC} Restart Claude Code / OpenCode to pick up changes."
