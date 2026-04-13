#!/usr/bin/env bash
#
# validate.sh — Lint all agent-notes configs.
#
# Checks:
#   - Agent frontmatter (Claude + OpenCode formats)
#   - Skill frontmatter and naming
#   - Global config files exist
#   - Line count limits
#   - No duplicate names
#
# Exit 0 = clean, 1 = errors found.
#
set -e

AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

err()  { echo -e "  ${RED}FAIL${NC}  $1"; ERRORS=$((ERRORS + 1)); }
warn() { echo -e "  ${YELLOW}WARN${NC}  $1"; WARNINGS=$((WARNINGS + 1)); }
ok()   { echo -e "  ${GREEN}OK${NC}    $1"; }

# Check if file has frontmatter and contains a required field
has_field() {
  local file="$1" field="$2"
  grep -q "^${field}:" "$file" 2>/dev/null
}

# Extract frontmatter field value
get_field() {
  local file="$1" field="$2"
  sed -n '/^---$/,/^---$/p' "$file" | grep "^${field}:" | head -1 | sed "s/^${field}:[[:space:]]*//" | tr -d '"' | tr -d "'"
}

# Count lines in file
line_count() {
  wc -l < "$1" | tr -d ' '
}

# --- Validate Claude agents ---

echo "Validating Claude Code agents (agents/*.md) ..."
NAMES=()

for f in "$AGENT_NOTES_DIR"/agents/*.md; do
  [ -f "$f" ] || continue
  local_name=$(basename "$f" .md)
  lines=$(line_count "$f")
  label="agents/$local_name.md ($lines lines)"

  # Frontmatter exists
  if ! head -1 "$f" | grep -q "^---$"; then
    err "$label — missing frontmatter"
    continue
  fi

  # Required fields
  for field in name description model; do
    if ! has_field "$f" "$field"; then
      err "$label — missing required field: $field"
    fi
  done

  # Name matches filename
  fm_name=$(get_field "$f" "name")
  if [ -n "$fm_name" ] && [ "$fm_name" != "$local_name" ]; then
    err "$label — name '$fm_name' does not match filename '$local_name'"
  fi

  # Line count
  if [ "$lines" -gt 200 ]; then
    err "$label — exceeds 200 line limit"
  elif [ "$lines" -gt 80 ]; then
    warn "$label — over 80 lines (consider trimming)"
  else
    ok "$label"
  fi

  NAMES+=("agent:$fm_name")
done

# --- Validate OpenCode agents ---

echo ""
echo "Validating OpenCode agents (agents-opencode/*.md) ..."

for f in "$AGENT_NOTES_DIR"/agents-opencode/*.md; do
  [ -f "$f" ] || continue
  local_name=$(basename "$f" .md)
  lines=$(line_count "$f")
  label="agents-opencode/$local_name.md ($lines lines)"

  if ! head -1 "$f" | grep -q "^---$"; then
    err "$label — missing frontmatter"
    continue
  fi

  for field in description mode model; do
    if ! has_field "$f" "$field"; then
      err "$label — missing required field: $field"
    fi
  done

  if [ "$lines" -gt 200 ]; then
    err "$label — exceeds 200 line limit"
  elif [ "$lines" -gt 80 ]; then
    warn "$label — over 80 lines (consider trimming)"
  else
    ok "$label"
  fi
done

# --- Validate Skills ---

echo ""
echo "Validating skills (*/SKILL.md) ..."

SKILL_NAMES=()
SKILL_NAME_REGEX='^[a-z0-9]+(-[a-z0-9]+)*$'

for skill_dir in "$AGENT_NOTES_DIR"/*/; do
  [ -f "${skill_dir}SKILL.md" ] || continue
  skill_name=$(basename "$skill_dir")
  f="${skill_dir}SKILL.md"
  lines=$(line_count "$f")
  label="$skill_name/SKILL.md ($lines lines)"

  if ! head -1 "$f" | grep -q "^---$"; then
    err "$label — missing frontmatter"
    continue
  fi

  for field in name description; do
    if ! has_field "$f" "$field"; then
      err "$label — missing required field: $field"
    fi
  done

  # Name matches directory
  fm_name=$(get_field "$f" "name")
  if [ -n "$fm_name" ] && [ "$fm_name" != "$skill_name" ]; then
    err "$label — name '$fm_name' does not match directory '$skill_name'"
  fi

  # Name format (OpenCode requirement)
  if [ -n "$fm_name" ] && ! echo "$fm_name" | grep -qE "$SKILL_NAME_REGEX"; then
    err "$label — name '$fm_name' does not match required pattern (lowercase alphanumeric + hyphens)"
  fi

  ok "$label"
  SKILL_NAMES+=("skill:$fm_name")
done

# --- Check for duplicate names ---

echo ""
echo "Checking for duplicates ..."

ALL_NAMES=("${NAMES[@]}" "${SKILL_NAMES[@]}")
SEEN=()
for entry in "${ALL_NAMES[@]}"; do
  for seen in "${SEEN[@]}"; do
    if [ "$entry" = "$seen" ]; then
      err "Duplicate name: $entry"
    fi
  done
  SEEN+=("$entry")
done

if [ ${#ALL_NAMES[@]} -gt 0 ] && [ "$ERRORS" -eq 0 ]; then
  ok "No duplicate names (${#ALL_NAMES[@]} total)"
fi

# --- Global config files ---

echo ""
echo "Checking global config files ..."

REQUIRED_GLOBAL=(
  "global/CLAUDE.md"
  "global/AGENTS.md"
  "global/copilot-instructions.md"
  "global/rules/code-quality.md"
  "global/rules/safety.md"
)

for rel in "${REQUIRED_GLOBAL[@]}"; do
  if [ -f "$AGENT_NOTES_DIR/$rel" ]; then
    ok "$rel"
  else
    err "$rel — file not found"
  fi
done

# --- Unclosed code blocks ---

echo ""
echo "Checking for unclosed code blocks ..."

for f in $(find "$AGENT_NOTES_DIR" -name "*.md" -not -path "*/.git/*" -not -path "*/node_modules/*"); do
  fence_count=$(grep -c '^\`\`\`' "$f" 2>/dev/null || true)
  fence_count=${fence_count:-0}
  fence_count=$(echo "$fence_count" | tr -d '[:space:]')
  if [ "$fence_count" -gt 0 ] && [ $((fence_count % 2)) -ne 0 ]; then
    rel="${f#$AGENT_NOTES_DIR/}"
    err "$rel — unclosed code block ($fence_count fence markers)"
  fi
done

ok "Code blocks valid"

# --- Summary ---

echo ""
echo "==============================="
if [ "$ERRORS" -gt 0 ]; then
  echo -e "${RED}$ERRORS error(s)${NC}, $WARNINGS warning(s)"
  exit 1
elif [ "$WARNINGS" -gt 0 ]; then
  echo -e "${GREEN}0 errors${NC}, ${YELLOW}$WARNINGS warning(s)${NC}"
  exit 0
else
  echo -e "${GREEN}All checks passed.${NC}"
  exit 0
fi
