#!/usr/bin/env bash
#
# Install agent-notes skills for Claude Code, OpenCode, and other compatible agents.
#
# Symlinks all skill directories (those containing SKILL.md) into:
#   ~/.claude/skills/       (Claude Code)
#   ~/.config/opencode/skills/  (OpenCode)
#   ~/.agents/skills/       (universal convention)
#
# Safe to re-run — existing symlinks are updated, non-symlink entries are skipped.
#
# Usage:
#   bash agent-notes/scripts/install-skills.sh            # install to all targets
#   bash agent-notes/scripts/install-skills.sh --claude    # Claude Code only
#   bash agent-notes/scripts/install-skills.sh --opencode  # OpenCode only
#   bash agent-notes/scripts/install-skills.sh --agents    # ~/.agents only
#
set -e

AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

TARGETS=()

if [ $# -eq 0 ]; then
  TARGETS=("$HOME/.claude/skills" "$HOME/.config/opencode/skills" "$HOME/.agents/skills")
else
  for arg in "$@"; do
    case "$arg" in
      --claude)   TARGETS+=("$HOME/.claude/skills") ;;
      --opencode) TARGETS+=("$HOME/.config/opencode/skills") ;;
      --agents)   TARGETS+=("$HOME/.agents/skills") ;;
      --help|-h)
        echo "Usage: $(basename "$0") [--claude] [--opencode] [--agents]"
        echo ""
        echo "Install agent-notes skills as symlinks."
        echo ""
        echo "Targets (all enabled by default):"
        echo "  --claude    ~/.claude/skills/           (Claude Code)"
        echo "  --opencode  ~/.config/opencode/skills/  (OpenCode)"
        echo "  --agents    ~/.agents/skills/            (universal)"
        echo ""
        echo "Run without flags to install to all targets."
        exit 0
        ;;
      *)
        echo "Unknown option: $arg (use --help for usage)"
        exit 1
        ;;
    esac
  done
fi

for target_dir in "${TARGETS[@]}"; do
  mkdir -p "$target_dir"
  echo "Installing to $target_dir ..."

  for skill_dir in "$AGENT_NOTES_DIR"/*/; do
    [ -f "${skill_dir}SKILL.md" ] || continue
    skill_name=$(basename "$skill_dir")
    target="$target_dir/$skill_name"

    if [ -e "$target" ] && [ ! -L "$target" ]; then
      echo "  WARNING: $skill_name exists and is not a symlink — skipping."
      continue
    fi

    ln -sf "$skill_dir" "$target"
    echo "  Linked: $skill_name"
  done
done

echo ""
echo "Done. Reload Claude Code / OpenCode to pick up skills."
