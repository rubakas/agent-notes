#!/usr/bin/env bash
set -e
AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo "Updating agent-notes..."
echo ""

# Check if git repo
if [ ! -d "$AGENT_NOTES_DIR/.git" ]; then
  echo -e "${RED}Error:${NC} Not a git repository. Update requires a git-based install."
  echo "If installed via brew, use: brew upgrade agent-notes"
  exit 1
fi

# Pull latest
echo "Pulling latest changes..."
cd "$AGENT_NOTES_DIR"
BEFORE=$(git rev-parse HEAD)
git pull --ff-only 2>&1 || {
  echo -e "${RED}Error:${NC} Could not fast-forward. You may have local changes."
  echo "Resolve manually: cd $AGENT_NOTES_DIR && git status"
  exit 1
}
AFTER=$(git rev-parse HEAD)

if [ "$BEFORE" = "$AFTER" ]; then
  echo -e "${GREEN}Already up to date.${NC}"
else
  echo -e "${GREEN}Updated${NC} $(git log --oneline "$BEFORE..$AFTER" | wc -l | tr -d ' ') commits."
  git log --oneline "$BEFORE..$AFTER" | head -5
  echo ""
fi

# Rebuild and reinstall
echo ""
exec bash "$AGENT_NOTES_DIR/lib/install.sh"