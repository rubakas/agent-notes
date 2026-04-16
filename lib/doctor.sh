#!/usr/bin/env bash
#
# doctor.sh — Health check script inspired by `brew doctor`
#
# Usage:
#   doctor.sh                    # Check global + local, report issues
#   doctor.sh --fix              # Fix found issues (with confirmation)
#   doctor.sh --global           # Check only global installation
#   doctor.sh --local            # Check only local installation
#
set -e

AGENT_NOTES_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BLUE='\033[0;34m'
NC='\033[0m'

# --- Status symbols ---
CHECK_MARK="✓"
CROSS_MARK="✗"

# --- Helpers ---

# macOS-compatible readlink function
resolve_symlink() {
  local file="$1"
  if [ -L "$file" ]; then
    stat -f "%Y" "$file" 2>/dev/null || echo ""
  fi
}

# Get file modification time in seconds since epoch (macOS compatible)
get_mtime() {
  stat -f "%m" "$1" 2>/dev/null || echo "0"
}

# Check if path exists and is a regular file (not symlink)
is_regular_file() {
  [ -f "$1" ] && [ ! -L "$1" ]
}

# Check if path exists and is a symlink
is_symlink() {
  [ -L "$1" ]
}

# Check if symlink target exists
symlink_target_exists() {
  local target
  target=$(resolve_symlink "$1")
  [ -n "$target" ] && [ -e "$target" ]
}

# Compare file contents (for checking content drift)
files_differ() {
  ! cmp -s "$1" "$2" 2>/dev/null
}

# --- Issue tracking ---

ISSUES=()
FIX_ACTIONS=()

add_issue() {
  local type="$1" file="$2" message="$3"
  ISSUES+=("$type:$file:$message")
}

add_fix_action() {
  local action="$1" file="$2" details="$3"
  FIX_ACTIONS+=("$action:$file:$details")
}

# --- Check functions ---

check_stale_files() {
  local scope="$1"  # "global" or "local"
  local base_dirs targets
  
  if [ "$scope" = "global" ]; then
    base_dirs=("$HOME/.claude" "$HOME/.config/opencode" "$HOME/.github")
  else
    base_dirs=(".claude" ".opencode" ".")
  fi
  
  for base_dir in "${base_dirs[@]}"; do
    [ -d "$base_dir" ] || continue
    
    # Check agents
    if [ -d "$base_dir/agents" ]; then
      for installed_file in "$base_dir/agents"/*.md; do
        [ -f "$installed_file" ] || continue
        local name source_file
        name=$(basename "$installed_file")
        
        if [[ "$base_dir" == *"opencode"* ]]; then
          source_file="$AGENT_NOTES_DIR/dist/cli/opencode/agents/$name"
        else
          source_file="$AGENT_NOTES_DIR/dist/cli/claude/agents/$name"
        fi
        
        if [ ! -f "$source_file" ]; then
          add_issue "stale" "$installed_file" "Not found in source. Likely left over from a previous version."
          add_fix_action "DELETE" "$installed_file" "stale, no matching source"
        fi
      done
    fi
    
    # Check skills
    if [ -d "$base_dir/skills" ]; then
      for installed_skill in "$base_dir/skills"/*; do
        [ -d "$installed_skill" ] || continue
        local skill_name source_skill
        skill_name=$(basename "$installed_skill")
        source_skill="$AGENT_NOTES_DIR/$skill_name"
        
        if [ ! -f "$source_skill/SKILL.md" ]; then
          add_issue "stale" "$installed_skill" "Not found in source. Likely left over from a previous version."
          add_fix_action "DELETE" "$installed_skill" "stale, no matching source"
        fi
      done
    fi
    
    # Check rules (only for Claude directory)
    if [ -d "$base_dir/rules" ] && [[ "$base_dir" == *"claude"* ]]; then
      for installed_rule in "$base_dir/rules"/*.md; do
        [ -f "$installed_rule" ] || continue
        local name source_rule
        name=$(basename "$installed_rule")
        source_rule="$AGENT_NOTES_DIR/dist/rules/$name"
        
        if [ ! -f "$source_rule" ]; then
          add_issue "stale" "$installed_rule" "Not found in source. Likely left over from a previous version."
          add_fix_action "DELETE" "$installed_rule" "stale, no matching source"
        fi
      done
    fi
  done
}

check_broken_symlinks() {
  local scope="$1"
  local base_dirs
  
  if [ "$scope" = "global" ]; then
    base_dirs=("$HOME/.claude" "$HOME/.config/opencode" "$HOME/.github")
  else
    base_dirs=(".claude" ".opencode" ".")
  fi
  
  for base_dir in "${base_dirs[@]}"; do
    [ -d "$base_dir" ] || continue
    
    # Find all symlinks and check if their targets exist
    find "$base_dir" -type l 2>/dev/null | while read -r symlink; do
      if ! symlink_target_exists "$symlink"; then
        add_issue "broken" "$symlink" "Symlink target does not exist"
        add_fix_action "DELETE" "$symlink" "broken symlink"
      fi
    done
  done
}

check_shadowed_files() {
  local scope="$1"
  local files_to_check=()
  
  if [ "$scope" = "global" ]; then
    # Global config files that should be symlinks
    files_to_check=(
      "$HOME/.claude/CLAUDE.md"
      "$HOME/.config/opencode/AGENTS.md"
      "$HOME/.github/copilot-instructions.md"
    )
    
    # Agents
    for f in "$AGENT_NOTES_DIR"/dist/cli/claude/agents/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      files_to_check+=("$HOME/.claude/agents/$name")
    done
    
    for f in "$AGENT_NOTES_DIR"/dist/cli/opencode/agents/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      files_to_check+=("$HOME/.config/opencode/agents/$name")
    done
    
    # Skills
    for skill_dir in "$AGENT_NOTES_DIR"/*/; do
      [ -f "${skill_dir}SKILL.md" ] || continue
      local skill_name="$(basename "$skill_dir")"
      files_to_check+=("$HOME/.claude/skills/$skill_name")
      files_to_check+=("$HOME/.config/opencode/skills/$skill_name")
    done
    
    # Rules
    for f in "$AGENT_NOTES_DIR"/dist/rules/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      files_to_check+=("$HOME/.claude/rules/$name")
    done
  else
    # Local files that should be symlinks (in copy mode they might be regular files)
    files_to_check=(
      "./CLAUDE.md"
      "./AGENTS.md"
    )
    
    # Local agents
    for f in "$AGENT_NOTES_DIR"/dist/cli/claude/agents/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      files_to_check+=(".claude/agents/$name")
    done
    
    for f in "$AGENT_NOTES_DIR"/dist/cli/opencode/agents/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      files_to_check+=(".opencode/agents/$name")
    done
  fi
  
  for file in "${files_to_check[@]}"; do
    if is_regular_file "$file"; then
      local source_file=""
      # Determine source file
      if [[ "$file" == *"/agents/"* ]]; then
        local name="$(basename "$file")"
        if [[ "$file" == *"opencode"* ]]; then
          source_file="$AGENT_NOTES_DIR/dist/cli/opencode/agents/$name"
        else
          source_file="$AGENT_NOTES_DIR/dist/cli/claude/agents/$name"
        fi
      elif [[ "$file" == *"/skills/"* ]]; then
        local skill_name="$(basename "$file")"
        source_file="$AGENT_NOTES_DIR/$skill_name"
      elif [[ "$file" == *"/rules/"* ]]; then
        local name="$(basename "$file")"
        source_file="$AGENT_NOTES_DIR/dist/rules/$name"
      elif [[ "$file" == *"CLAUDE.md" ]]; then
        source_file="$AGENT_NOTES_DIR/dist/cli/claude/CLAUDE.md"
      elif [[ "$file" == *"AGENTS.md" ]]; then
        source_file="$AGENT_NOTES_DIR/dist/cli/opencode/AGENTS.md"
      elif [[ "$file" == *"copilot-instructions.md" ]]; then
        source_file="$AGENT_NOTES_DIR/dist/cli/github/copilot-instructions.md"
      fi
      
      add_issue "shadowed" "$file" "Regular file instead of symlink. Won't receive updates."
      add_fix_action "RELINK" "$file" "replace copy with symlink to $source_file"
    fi
  done
}

check_missing_files() {
  local scope="$1"
  
  if [ "$scope" = "global" ]; then
    # Check global config files
    local global_files=(
      "$HOME/.claude/CLAUDE.md:$AGENT_NOTES_DIR/dist/cli/claude/CLAUDE.md"
      "$HOME/.config/opencode/AGENTS.md:$AGENT_NOTES_DIR/dist/cli/opencode/AGENTS.md"
      "$HOME/.github/copilot-instructions.md:$AGENT_NOTES_DIR/dist/cli/github/copilot-instructions.md"
    )
    
    for entry in "${global_files[@]}"; do
      local target="${entry%:*}"
      local source="${entry#*:}"
      if [ -f "$source" ] && [ ! -e "$target" ]; then
        add_issue "missing" "$target" "Source exists but not installed"
        add_fix_action "INSTALL" "$target" "install from $source"
      fi
    done
    
    # Check agents
    for f in "$AGENT_NOTES_DIR"/dist/cli/claude/agents/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      local target="$HOME/.claude/agents/$name"
      if [ ! -e "$target" ]; then
        add_issue "missing" "$target" "Source exists but not installed"
        add_fix_action "INSTALL" "$target" "install Claude agent"
      fi
    done
    
    for f in "$AGENT_NOTES_DIR"/dist/cli/opencode/agents/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      local target="$HOME/.config/opencode/agents/$name"
      if [ ! -e "$target" ]; then
        add_issue "missing" "$target" "Source exists but not installed"
        add_fix_action "INSTALL" "$target" "install OpenCode agent"
      fi
    done
    
    # Check skills
    for skill_dir in "$AGENT_NOTES_DIR"/*/; do
      [ -f "${skill_dir}SKILL.md" ] || continue
      local skill_name="$(basename "$skill_dir")"
      local claude_target="$HOME/.claude/skills/$skill_name"
      local opencode_target="$HOME/.config/opencode/skills/$skill_name"
      
      if [ ! -e "$claude_target" ]; then
        add_issue "missing" "$claude_target" "Source exists but not installed"
        add_fix_action "INSTALL" "$claude_target" "install skill"
      fi
      if [ ! -e "$opencode_target" ]; then
        add_issue "missing" "$opencode_target" "Source exists but not installed"  
        add_fix_action "INSTALL" "$opencode_target" "install skill"
      fi
    done
    
    # Check rules
    for f in "$AGENT_NOTES_DIR"/dist/rules/*.md; do
      [ -f "$f" ] || continue
      local name="$(basename "$f")"
      local target="$HOME/.claude/rules/$name"
      if [ ! -e "$target" ]; then
        add_issue "missing" "$target" "Source exists but not installed"
        add_fix_action "INSTALL" "$target" "install rule"
      fi
    done
  fi
}

check_content_drift() {
  local scope="$1"
  local base_dirs
  
  if [ "$scope" = "global" ]; then
    base_dirs=("$HOME/.claude" "$HOME/.config/opencode" "$HOME/.github")
  else
    base_dirs=(".claude" ".opencode" ".")
  fi
  
  for base_dir in "${base_dirs[@]}"; do
    [ -d "$base_dir" ] || continue
    
    # Check regular files (copies) against source
    find "$base_dir" -type f -name "*.md" 2>/dev/null | while read -r file; do
      local source_file=""
      
      # Determine source file
      if [[ "$file" == *"/agents/"* ]]; then
        local name="$(basename "$file")"
        if [[ "$file" == *"opencode"* ]]; then
          source_file="$AGENT_NOTES_DIR/dist/cli/opencode/agents/$name"
        else
          source_file="$AGENT_NOTES_DIR/dist/cli/claude/agents/$name"
        fi
      elif [[ "$file" == *"/rules/"* ]]; then
        local name="$(basename "$file")"
        source_file="$AGENT_NOTES_DIR/dist/rules/$name"
      elif [[ "$file" == *"CLAUDE.md" ]]; then
        source_file="$AGENT_NOTES_DIR/dist/cli/claude/CLAUDE.md"
      elif [[ "$file" == *"AGENTS.md" ]]; then
        source_file="$AGENT_NOTES_DIR/dist/cli/opencode/AGENTS.md"
      elif [[ "$file" == *"copilot-instructions.md" ]]; then
        source_file="$AGENT_NOTES_DIR/dist/cli/github/copilot-instructions.md"
      fi
      
      if [ -n "$source_file" ] && [ -f "$source_file" ] && files_differ "$file" "$source_file"; then
        add_issue "drift" "$file" "Content differs from source. Local changes will be lost on update."
      fi
    done
  done
}

check_build_freshness() {
  # Check if source files are newer than generated files
  local source_dir="$AGENT_NOTES_DIR/source"
  
  # Check if source directory exists
  [ -d "$source_dir" ] || return 0
  
  # Check agents.yaml vs generated agents
  if [ -f "$source_dir/agents.yaml" ]; then
    local source_time="$(get_mtime "$source_dir/agents.yaml")"
    
    # Check generated agents directories
    if [ -d "$AGENT_NOTES_DIR/dist/cli/claude/agents" ]; then
      for f in "$AGENT_NOTES_DIR"/dist/cli/claude/agents/*.md; do
        [ -f "$f" ] || continue
        local gen_time="$(get_mtime "$f")"
        if [ "$source_time" -gt "$gen_time" ]; then
          add_issue "build_stale" "$f" "agents.yaml is newer than generated files"
          add_fix_action "BUILD" "agents/" "regenerate from source"
          break
        fi
      done
    fi
    
    if [ -d "$AGENT_NOTES_DIR/dist/cli/opencode/agents" ]; then
      for f in "$AGENT_NOTES_DIR"/dist/cli/opencode/agents/*.md; do
        [ -f "$f" ] || continue
        local gen_time="$(get_mtime "$f")"
        if [ "$source_time" -gt "$gen_time" ]; then
          add_issue "build_stale" "$f" "agents.yaml is newer than generated files"
          add_fix_action "BUILD" "agents-opencode/" "regenerate from source"
          break
        fi
      done
    fi
  fi
  
  # Check individual source agents
  if [ -d "$source_dir/agents" ]; then
    for src_file in "$source_dir/agents"/*.md; do
      [ -f "$src_file" ] || continue
      local name="$(basename "$src_file")"
      local source_time="$(get_mtime "$src_file")"
      
      # Check corresponding generated files
      local claude_gen="$AGENT_NOTES_DIR/dist/cli/claude/agents/$name"
      local opencode_gen="$AGENT_NOTES_DIR/dist/cli/opencode/agents/$name"
      
      if [ -f "$claude_gen" ]; then
        local gen_time="$(get_mtime "$claude_gen")"
        if [ "$source_time" -gt "$gen_time" ]; then
          add_issue "build_stale" "$claude_gen" "$src_file is newer than generated file"
          add_fix_action "BUILD" "$claude_gen" "regenerate from source"
        fi
      fi
      
      if [ -f "$opencode_gen" ]; then
        local gen_time="$(get_mtime "$opencode_gen")"
        if [ "$source_time" -gt "$gen_time" ]; then
          add_issue "build_stale" "$opencode_gen" "$src_file is newer than generated file"
          add_fix_action "BUILD" "$opencode_gen" "regenerate from source"
        fi
      fi
    done
  fi
  
  # Check global source files
  local global_sources=(
    "$source_dir/global.md:$AGENT_NOTES_DIR/dist/cli/claude/CLAUDE.md"
    "$source_dir/global.md:$AGENT_NOTES_DIR/dist/cli/opencode/AGENTS.md"
    "$source_dir/global-copilot.md:$AGENT_NOTES_DIR/dist/cli/github/copilot-instructions.md"
  )
  
  for entry in "${global_sources[@]}"; do
    local src="${entry%:*}"
    local gen="${entry#*:}"
    
    if [ -f "$src" ] && [ -f "$gen" ]; then
      local src_time="$(get_mtime "$src")"
      local gen_time="$(get_mtime "$gen")"
      
      if [ "$src_time" -gt "$gen_time" ]; then
        add_issue "build_stale" "$gen" "$src is newer than generated file"
        add_fix_action "BUILD" "$gen" "regenerate from source"
      fi
    fi
  done
}

# --- Report functions ---

count_installed() {
  local what="$1" scope="$2"
  local count=0 base_dirs
  
  if [ "$scope" = "global" ]; then
    base_dirs=("$HOME/.claude" "$HOME/.config/opencode")
  else
    base_dirs=(".claude" ".opencode")
  fi
  
  case "$what" in
    agents)
      for base_dir in "${base_dirs[@]}"; do
        [ -d "$base_dir/agents" ] || continue
        for f in "$base_dir/agents"/*.md; do
          [ -f "$f" ] && count=$((count + 1))
        done
      done
      ;;
    skills)
      for base_dir in "${base_dirs[@]}"; do
        [ -d "$base_dir/skills" ] || continue
        for d in "$base_dir/skills"/*; do
          [ -d "$d" ] && count=$((count + 1))
        done
      done
      ;;
    rules)
      if [ "$scope" = "global" ]; then
        [ -d "$HOME/.claude/rules" ] || return
        for f in "$HOME/.claude/rules"/*.md; do
          [ -f "$f" ] && count=$((count + 1))
        done
      else
        [ -d ".claude/rules" ] || return
        for f in ".claude/rules"/*.md; do
          [ -f "$f" ] && count=$((count + 1))
        done
      fi
      ;;
  esac
  
  echo "$count"
}

count_stale() {
  local type="$1"
  local count=0
  for issue in "${ISSUES[@]}"; do
    if [[ "$issue" == "stale:"*"$type"* ]]; then
      count=$((count + 1))
    fi
  done
  echo "$count"
}

print_summary() {
  local scope="$1"
  
  echo "Checking ${scope} installation..."
  echo ""
  
  # Count installed and stale items
  local agents_installed stale_agents skills_installed stale_skills rules_installed stale_rules
  agents_installed=$(count_installed "agents" "$scope")
  stale_agents=$(count_stale "agents")
  skills_installed=$(count_installed "skills" "$scope") 
  stale_skills=$(count_stale "skills")
  
  if [ "$scope" = "global" ]; then
    rules_installed=$(count_installed "rules" "$scope")
    stale_rules=$(count_stale "rules")
    
    # Check if global config files exist
    local config_ok=true
    local config_files=("$HOME/.claude/CLAUDE.md" "$HOME/.config/opencode/AGENTS.md" "$HOME/.github/copilot-instructions.md")
    for f in "${config_files[@]}"; do
      [ -e "$f" ] || config_ok=false
    done
    
    echo -e "${GREEN}${CHECK_MARK}${NC} Claude Code agents ($agents_installed installed, $stale_agents stale)"
    echo -e "${GREEN}${CHECK_MARK}${NC} OpenCode agents (counted above)"  
    echo -e "${GREEN}${CHECK_MARK}${NC} Skills ($skills_installed installed, $stale_skills stale)"
    if [ "$config_ok" = true ]; then
      echo -e "${GREEN}${CHECK_MARK}${NC} Global config files"
    else
      echo -e "${RED}${CROSS_MARK}${NC} Global config files (some missing)"
    fi
    echo -e "${GREEN}${CHECK_MARK}${NC} Rules ($rules_installed installed, $stale_rules stale)"
  else
    echo -e "${GREEN}${CHECK_MARK}${NC} Local agents ($agents_installed installed, $stale_agents stale)"
    echo -e "${GREEN}${CHECK_MARK}${NC} Local skills ($skills_installed installed, $stale_skills stale)"
    
    # Check local config files  
    local local_config_ok=true
    [ -e "./CLAUDE.md" ] || local_config_ok=false
    [ -e "./AGENTS.md" ] || local_config_ok=false
    
    if [ "$local_config_ok" = true ]; then
      echo -e "${GREEN}${CHECK_MARK}${NC} Local config files"
    else
      echo -e "${CYAN}${CHECK_MARK}${NC} Local config files (optional, not installed)"
    fi
  fi
}

print_issues() {
  local issue_count=${#ISSUES[@]}
  
  if [ "$issue_count" -eq 0 ]; then
    echo ""
    echo -e "${GREEN}No issues found.${NC}"
    return 0
  fi
  
  echo ""
  echo -e "${YELLOW}Warning: $issue_count issue(s) found${NC}"
  echo ""
  
  for issue in "${ISSUES[@]}"; do
    local type="${issue%%:*}"
    local rest="${issue#*:}"
    local file="${rest%%:*}" 
    local message="${rest#*:}"
    
    case "$type" in
      stale)
        echo -e "  ${RED}${CROSS_MARK} Stale file: ${NC}$file"
        echo "    $message"
        ;;
      broken)
        echo -e "  ${RED}${CROSS_MARK} Broken symlink: ${NC}$file"
        echo "    $message"
        ;;
      shadowed)
        echo -e "  ${YELLOW}${CROSS_MARK} Shadowed file: ${NC}$file"
        echo "    $message"
        ;;
      missing)
        echo -e "  ${YELLOW}${CROSS_MARK} Missing file: ${NC}$file"
        echo "    $message"
        ;;
      drift)
        echo -e "  ${CYAN}${CROSS_MARK} Content drift: ${NC}$file"
        echo "    $message"
        ;;
      build_stale)
        echo -e "  ${YELLOW}${CROSS_MARK} Build stale: ${NC}$file"
        echo "    $message"
        ;;
    esac
    echo ""
  done
  
  echo "Run 'doctor.sh --fix' to resolve these issues."
  return 1
}

# --- Fix functions ---

do_fix() {
  local fix_count=${#FIX_ACTIONS[@]}
  
  if [ "$fix_count" -eq 0 ]; then
    echo -e "${GREEN}No fixes needed.${NC}"
    return 0
  fi
  
  echo "The following changes will be made:"
  echo ""
  
  for action in "${FIX_ACTIONS[@]}"; do
    local cmd="${action%%:*}"
    local rest="${action#*:}"
    local file="${rest%%:*}"
    local details="${rest#*:}"
    
    case "$cmd" in
      DELETE)
        echo -e "  ${RED}DELETE${NC}  $file ($details)"
        ;;
      RELINK)
        echo -e "  ${BLUE}RELINK${NC}  $file ($details)"
        ;;
      INSTALL)
        echo -e "  ${GREEN}INSTALL${NC} $file ($details)"
        ;;
      BUILD)
        echo -e "  ${CYAN}BUILD${NC}   $file ($details)"
        ;;
    esac
  done
  
  echo ""
  echo -n "Proceed? [y/N] "
  read -r response
  
  if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    return 0
  fi
  
  echo ""
  echo "Applying fixes..."
  
  local needs_build=false
  
  for action in "${FIX_ACTIONS[@]}"; do
    local cmd="${action%%:*}"
    local rest="${action#*:}"
    local file="${rest%%:*}"
    local details="${rest#*:}"
    
    case "$cmd" in
      DELETE)
        if [ -e "$file" ]; then
          rm -rf "$file"
          echo -e "  ${RED}DELETED${NC}  $file"
        fi
        ;;
      RELINK)
        local source_file=""
        # Extract source from details
        if [[ "$details" == *"symlink to "* ]]; then
          source_file="${details#*symlink to }"
        fi
        
        if [ -n "$source_file" ] && [ -f "$source_file" ]; then
          # Backup original
          [ -f "$file" ] && cp "$file" "$file.bak"
          rm -f "$file"
          mkdir -p "$(dirname "$file")"
          ln -sf "$source_file" "$file"
          echo -e "  ${BLUE}RELINKED${NC} $file"
        else
          echo -e "  ${RED}FAILED${NC}   $file (source not found: $source_file)"
        fi
        ;;
      INSTALL)
        # Use install.sh to install missing components
        needs_install=true
        ;;
      BUILD)
        needs_build=true
        ;;
    esac
  done
  
  # Handle bulk operations
  if [ "$needs_install" = true ]; then
    echo -e "  ${GREEN}RUNNING${NC} install.sh to install missing components..."
    "$AGENT_NOTES_DIR/lib/install.sh" all global >/dev/null 2>&1 || true
  fi
  
  if [ "$needs_build" = true ]; then
    echo -e "  ${CYAN}NOTICE${NC}   Build stale issues detected."
    echo "           Run the build process to regenerate files from source."
  fi
  
  echo ""
  echo "Verifying fixes..."
  
  # Clear issues and re-run checks
  ISSUES=()
  FIX_ACTIONS=()
  
  local scope="${CHECK_SCOPE:-global}"
  if [ "$scope" = "global" ]; then
    check_all_global
  fi
  if [ "$scope" = "local" ]; then
    check_all_local  
  fi
  
  local remaining=${#ISSUES[@]}
  if [ "$remaining" -eq 0 ]; then
    echo -e "${GREEN}All issues resolved.${NC}"
  else
    echo -e "${YELLOW}$remaining issue(s) remain.${NC}"
  fi
}

# --- Main check functions ---

check_all_global() {
  check_stale_files "global"
  check_broken_symlinks "global" 
  check_shadowed_files "global"
  check_missing_files "global"
  check_content_drift "global"
}

check_all_local() {
  check_stale_files "local"
  check_broken_symlinks "local"
  check_shadowed_files "local" 
  check_content_drift "local"
}

# --- Help ---

show_help() {
  cat <<'EOF'
Usage: doctor.sh [options]

Health check script for agent-notes installation, inspired by `brew doctor`.

Options:
  (none)       Check global installation (default)
  --local      Check local installation (.claude/, .opencode/ in current directory)
  --fix        Fix found issues (with confirmation)
  --help       Show this help

What it checks:
  • Stale files - installed files without matching source
  • Broken symlinks - symlinks pointing to non-existent targets
  • Shadowed files - regular files where symlinks are expected
  • Missing files - source files that aren't installed
  • Content drift - copied files that differ from source
  • Build freshness - whether generated files are up-to-date with source

Examples:
  doctor.sh                    # Check global installation
  doctor.sh --local            # Check local installation
  doctor.sh --fix              # Fix global issues interactively
  doctor.sh --local --fix      # Check and fix local issues
EOF
}

# --- Main ---

SCOPE="global"
FIX_MODE=false
CHECK_SCOPE="global"

for arg in "$@"; do
  case "$arg" in
    --local)
      SCOPE="local" 
      CHECK_SCOPE="local"
      ;;
    --fix)
      FIX_MODE=true
      ;;
    --help|-h)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $arg"
      echo "Run 'doctor.sh --help' for usage."
      exit 1
      ;;
  esac
done

# Run checks
if [ "$SCOPE" = "global" ]; then
  print_summary "global"
  check_all_global
fi

if [ "$SCOPE" = "local" ]; then
  print_summary "local"  
  check_all_local
fi

# Always check build freshness (affects both global and local)
check_build_freshness

# Handle results
if [ "$FIX_MODE" = true ]; then
  echo ""
  do_fix
else
  if ! print_issues; then
    exit 1
  fi
fi