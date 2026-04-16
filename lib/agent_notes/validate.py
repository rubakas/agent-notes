"""Lint all agent-notes configs."""

import re
from pathlib import Path
from typing import List, Set, Optional

from .config import (
    ROOT, DIST_DIR, SOURCE_DIR, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_RULES_DIR,
    Color, find_skill_dirs
)

class ValidationError:
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message

class ValidationWarning:
    def __init__(self, file_path: str, message: str):
        self.file_path = file_path
        self.message = message

def has_field(file_path: Path, field: str) -> bool:
    """Check if file has frontmatter field."""
    try:
        content = file_path.read_text()
        return f"{field}:" in content
    except (FileNotFoundError, OSError):
        return False

def get_field(file_path: Path, field: str) -> Optional[str]:
    """Extract frontmatter field value."""
    try:
        content = file_path.read_text()
        lines = content.split('\n')
        
        in_frontmatter = False
        for line in lines:
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    break  # End of frontmatter
            
            if in_frontmatter and line.startswith(f"{field}:"):
                value = line.split(':', 1)[1].strip()
                # Remove quotes
                value = value.strip('"\'')
                return value
        
        return None
    except (FileNotFoundError, OSError):
        return None

def line_count(file_path: Path) -> int:
    """Count lines in file."""
    try:
        return len(file_path.read_text().split('\n'))
    except (FileNotFoundError, OSError):
        return 0

def has_frontmatter(file_path: Path) -> bool:
    """Check if file starts with frontmatter."""
    try:
        content = file_path.read_text()
        return content.startswith("---\n")
    except (FileNotFoundError, OSError):
        return False

def check_unclosed_code_blocks(file_path: Path) -> bool:
    """Check for unclosed code blocks."""
    try:
        content = file_path.read_text()
        fence_count = content.count('```')
        return fence_count % 2 == 0  # Even number means all blocks are closed
    except (FileNotFoundError, OSError):
        return True

def validate() -> None:
    """Lint all agent-notes configs."""
    errors: List[ValidationError] = []
    warnings: List[ValidationWarning] = []
    names: Set[str] = set()
    skill_names: Set[str] = set()
    
    # Validate Claude agents
    print("Validating Claude Code agents (dist/cli/claude/agents/*.md) ...")
    
    claude_agents_dir = DIST_CLAUDE_DIR / "agents"
    if claude_agents_dir.exists():
        for f in claude_agents_dir.glob("*.md"):
            local_name = f.stem
            lines = line_count(f)
            label = f"dist/cli/claude/agents/{local_name}.md ({lines} lines)"
            
            # Frontmatter exists
            if not has_frontmatter(f):
                errors.append(ValidationError(label, "missing frontmatter"))
                continue
            
            # Required fields
            for field in ["name", "description", "model"]:
                if not has_field(f, field):
                    errors.append(ValidationError(label, f"missing required field: {field}"))
            
            # Name matches filename
            fm_name = get_field(f, "name")
            if fm_name and fm_name != local_name:
                errors.append(ValidationError(label, f"name '{fm_name}' does not match filename '{local_name}'"))
            
            # Line count
            if lines > 200:
                errors.append(ValidationError(label, "exceeds 200 line limit"))
            elif lines > 80:
                warnings.append(ValidationWarning(label, "over 80 lines (consider trimming)"))
            else:
                print(f"  {Color.GREEN}OK{Color.NC}    {label}")
            
            if fm_name:
                names.add(f"agent:{fm_name}")
    
    # Validate OpenCode agents
    print("")
    print("Validating OpenCode agents (dist/cli/opencode/agents/*.md) ...")
    
    opencode_agents_dir = DIST_OPENCODE_DIR / "agents"
    if opencode_agents_dir.exists():
        for f in opencode_agents_dir.glob("*.md"):
            local_name = f.stem
            lines = line_count(f)
            label = f"dist/cli/opencode/agents/{local_name}.md ({lines} lines)"
            
            if not has_frontmatter(f):
                errors.append(ValidationError(label, "missing frontmatter"))
                continue
            
            for field in ["description", "mode", "model"]:
                if not has_field(f, field):
                    errors.append(ValidationError(label, f"missing required field: {field}"))
            
            if lines > 200:
                errors.append(ValidationError(label, "exceeds 200 line limit"))
            elif lines > 80:
                warnings.append(ValidationWarning(label, "over 80 lines (consider trimming)"))
            else:
                print(f"  {Color.GREEN}OK{Color.NC}    {label}")
    
    # Validate Skills
    print("")
    print("Validating skills (*/SKILL.md) ...")
    
    skill_name_regex = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
    
    for skill_path in find_skill_dirs():
        skill_name = skill_path.name
        f = skill_path / "SKILL.md"
        if not f.exists():
            continue
            
        lines = line_count(f)
        label = f"{skill_name}/SKILL.md ({lines} lines)"
        
        if not has_frontmatter(f):
            errors.append(ValidationError(label, "missing frontmatter"))
            continue
        
        for field in ["name", "description"]:
            if not has_field(f, field):
                errors.append(ValidationError(label, f"missing required field: {field}"))
        
        # Name matches directory
        fm_name = get_field(f, "name")
        if fm_name and fm_name != skill_name:
            errors.append(ValidationError(label, f"name '{fm_name}' does not match directory '{skill_name}'"))
        
        # Name format (OpenCode requirement)
        if fm_name and not skill_name_regex.match(fm_name):
            errors.append(ValidationError(label, f"name '{fm_name}' does not match required pattern (lowercase alphanumeric + hyphens)"))
        
        print(f"  {Color.GREEN}OK{Color.NC}    {label}")
        
        if fm_name:
            skill_names.add(f"skill:{fm_name}")
    
    # Check for duplicate names
    print("")
    print("Checking for duplicates ...")
    
    all_names = names | skill_names
    seen = set()
    for name in all_names:
        if name in seen:
            errors.append(ValidationError("Duplicate name", name))
        seen.add(name)
    
    if all_names and not any("Duplicate name" in err.file_path for err in errors):
        print(f"  {Color.GREEN}OK{Color.NC}    No duplicate names ({len(all_names)} total)")
    
    # Global config files
    print("")
    print("Checking global config files ...")
    
    required_global = [
        DIST_CLAUDE_DIR / "CLAUDE.md",
        DIST_OPENCODE_DIR / "AGENTS.md",
        ROOT / "dist/cli/github/copilot-instructions.md",
        DIST_RULES_DIR / "code-quality.md",
        DIST_RULES_DIR / "safety.md"
    ]
    
    for file_path in required_global:
        rel_path = file_path.relative_to(ROOT)
        if file_path.exists():
            print(f"  {Color.GREEN}OK{Color.NC}    {rel_path}")
        else:
            errors.append(ValidationError(str(rel_path), "file not found"))
    
    # Unclosed code blocks
    print("")
    print("Checking for unclosed code blocks ...")
    
    codeblock_ok = True
    for md_file in ROOT.rglob("*.md"):
        # Skip .git and node_modules
        if ".git" in str(md_file) or "node_modules" in str(md_file):
            continue
        
        if not check_unclosed_code_blocks(md_file):
            rel_path = md_file.relative_to(ROOT)
            try:
                fence_count = md_file.read_text().count('```')
                errors.append(ValidationError(str(rel_path), f"unclosed code block ({fence_count} fence markers)"))
                codeblock_ok = False
            except (FileNotFoundError, OSError):
                pass
    
    if codeblock_ok:
        print(f"  {Color.GREEN}OK{Color.NC}    Code blocks valid")
    
    # Print all errors and warnings
    for error in errors:
        print(f"  {Color.RED}FAIL{Color.NC}  {error.file_path} — {error.message}")
    
    for warning in warnings:
        print(f"  {Color.YELLOW}WARN{Color.NC}  {warning.file_path} — {warning.message}")
    
    # Summary
    print("")
    print("===============================")
    if errors:
        print(f"{Color.RED}{len(errors)} error(s){Color.NC}, {len(warnings)} warning(s)")
        exit(1)
    elif warnings:
        print(f"{Color.GREEN}0 errors{Color.NC}, {Color.YELLOW}{len(warnings)} warning(s){Color.NC}")
        exit(0)
    else:
        print(f"{Color.GREEN}All checks passed.{Color.NC}")
        exit(0)