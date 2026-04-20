"""Health check for agent-notes installation."""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from .config import (
    ROOT, DIST_CLAUDE_DIR, DIST_OPENCODE_DIR, DIST_GITHUB_DIR, DIST_RULES_DIR, DIST_SKILLS_DIR,
    CLAUDE_HOME, OPENCODE_HOME, GITHUB_HOME, AGENTS_HOME,
    DATA_DIR, AGENTS_YAML, AGENTS_DIR, GLOBAL_MD, GLOBAL_COPILOT_MD,
    Color, info, issue, ok, warn, fail,
    linked, removed, skipped
)

class Issue:
    def __init__(self, issue_type: str, file: str, message: str):
        self.type = issue_type
        self.file = file
        self.message = message

class FixAction:
    def __init__(self, action: str, file: str, details: str):
        self.action = action
        self.file = file
        self.details = details

def resolve_symlink(path: Path) -> Optional[Path]:
    """Get symlink target if path is a symlink."""
    if path.is_symlink():
        try:
            return path.readlink()
        except OSError:
            return None
    return None

def symlink_target_exists(path: Path) -> bool:
    """Check if symlink target exists."""
    if not path.is_symlink():
        return False
    try:
        target = path.readlink()
        # Handle relative targets
        if not target.is_absolute():
            target = path.parent / target
        return target.exists()
    except OSError:
        return False

def files_differ(file1: Path, file2: Path) -> bool:
    """Compare file contents."""
    try:
        return file1.read_bytes() != file2.read_bytes()
    except (OSError, FileNotFoundError):
        return True

def check_stale_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for installed files without matching source."""
    if scope == "global":
        base_dirs = [
            Path.home() / ".claude",
            Path.home() / ".config/opencode", 
            Path.home() / ".github"
        ]
    else:
        base_dirs = [Path(".claude"), Path(".opencode"), Path(".")]
    
    for base_dir in base_dirs:
        if not base_dir.exists():
            continue
            
        # Check agents
        agents_dir = base_dir / "agents"
        if agents_dir.exists():
            for installed_file in agents_dir.glob("*.md"):
                name = installed_file.name
                
                if "opencode" in str(base_dir):
                    source_file = DIST_OPENCODE_DIR / "agents" / name
                else:
                    source_file = DIST_CLAUDE_DIR / "agents" / name
                
                if not source_file.exists():
                    issues.append(Issue("stale", str(installed_file), 
                                      "Not found in source. Likely left over from a previous version."))
                    fix_actions.append(FixAction("DELETE", str(installed_file), 
                                               "stale, no matching source"))
        
        # Check skills
        skills_dir = base_dir / "skills"
        if skills_dir.exists():
            for installed_skill in skills_dir.iterdir():
                if not installed_skill.is_dir():
                    continue
                skill_name = installed_skill.name
                source_skill = DIST_SKILLS_DIR / skill_name
                
                if not source_skill.exists():
                    issues.append(Issue("stale", str(installed_skill),
                                      "Not found in source. Likely left over from a previous version."))
                    fix_actions.append(FixAction("DELETE", str(installed_skill),
                                               "stale, no matching source"))
        
        # Check rules (only for Claude directory)
        if "claude" in str(base_dir):
            rules_dir = base_dir / "rules"
            if rules_dir.exists():
                for installed_rule in rules_dir.glob("*.md"):
                    name = installed_rule.name
                    source_rule = DIST_RULES_DIR / name
                    
                    if not source_rule.exists():
                        issues.append(Issue("stale", str(installed_rule),
                                          "Not found in source. Likely left over from a previous version."))
                        fix_actions.append(FixAction("DELETE", str(installed_rule),
                                                   "stale, no matching source"))

def _find_dist_source(symlink: Path, scope: str) -> Optional[Path]:
    """Map an installed path back to its dist source for relinking."""
    symlink = symlink.resolve() if symlink.exists() else Path(os.path.abspath(symlink))
    name = symlink.name
    parent_name = symlink.parent.name

    if scope == "global":
        # Skills: ~/.claude/skills/<name> or ~/.config/opencode/skills/<name> or ~/.agents/skills/<name>
        if parent_name == "skills":
            source = DIST_SKILLS_DIR / name
            if source.exists():
                return source

        # Agents: ~/.claude/agents/<name>.md → dist/claude/agents/<name>.md
        if parent_name == "agents":
            for dist_dir in [DIST_CLAUDE_DIR, DIST_OPENCODE_DIR]:
                source = dist_dir / "agents" / name
                if source.exists():
                    return source

        # Rules: ~/.claude/rules/<name> or ~/.config/opencode/rules/<name>
        if parent_name == "rules":
            source = DIST_RULES_DIR / name
            if source.exists():
                return source

        # Global config files
        config_map = {
            "CLAUDE.md": DIST_CLAUDE_DIR / "CLAUDE.md",
            "AGENTS.md": DIST_OPENCODE_DIR / "AGENTS.md",
            "copilot-instructions.md": DIST_GITHUB_DIR / "copilot-instructions.md",
        }
        if name in config_map:
            source = config_map[name]
            if source.exists():
                return source
    else:
        # Local skills
        if parent_name == "skills":
            source = DIST_SKILLS_DIR / name
            if source.exists():
                return source

        # Local agents
        if parent_name == "agents":
            for dist_dir in [DIST_CLAUDE_DIR, DIST_OPENCODE_DIR]:
                source = dist_dir / "agents" / name
                if source.exists():
                    return source

        # Local rules
        if parent_name == "rules":
            source = DIST_RULES_DIR / name
            if source.exists():
                return source

    return None


def check_broken_symlinks(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for symlinks with non-existent targets."""
    if scope == "global":
        base_dirs = [
            Path.home() / ".claude",
            Path.home() / ".config/opencode",
            Path.home() / ".github"
        ]
    else:
        base_dirs = [Path(".claude"), Path(".opencode"), Path(".")]
    
    for base_dir in base_dirs:
        if not base_dir.exists():
            continue
            
        # Find all symlinks and check targets
        for root, dirs, files in os.walk(base_dir):
            root_path = Path(root)
            for file in files:
                symlink = root_path / file
                if symlink.is_symlink() and not symlink_target_exists(symlink):
                    source = _find_dist_source(symlink, scope)
                    issues.append(Issue("broken", str(symlink), "Symlink target does not exist"))
                    if source:
                        fix_actions.append(FixAction("RELINK", str(symlink), f"symlink to {source}"))
                    else:
                        fix_actions.append(FixAction("DELETE", str(symlink), "broken symlink, no source available"))
            
            # Check directory symlinks too
            for dir_name in dirs:
                symlink = root_path / dir_name
                if symlink.is_symlink() and not symlink_target_exists(symlink):
                    source = _find_dist_source(symlink, scope)
                    issues.append(Issue("broken", str(symlink), "Symlink target does not exist"))
                    if source:
                        fix_actions.append(FixAction("RELINK", str(symlink), f"symlink to {source}"))
                    else:
                        fix_actions.append(FixAction("DELETE", str(symlink), "broken symlink, no source available"))

def check_shadowed_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for regular files where symlinks are expected."""
    files_to_check = []
    
    if scope == "global":
        # Global config files that should be symlinks
        files_to_check.extend([
            Path.home() / ".claude/CLAUDE.md",
            Path.home() / ".config/opencode/AGENTS.md",
            Path.home() / ".github/copilot-instructions.md"
        ])
        
        # Agents
        claude_agents_dir = DIST_CLAUDE_DIR / "agents"
        if claude_agents_dir.exists():
            for f in claude_agents_dir.glob("*.md"):
                files_to_check.append(Path.home() / ".claude/agents" / f.name)
        
        opencode_agents_dir = DIST_OPENCODE_DIR / "agents"
        if opencode_agents_dir.exists():
            for f in opencode_agents_dir.glob("*.md"):
                files_to_check.append(Path.home() / ".config/opencode/agents" / f.name)
        
        # Skills
        if DIST_SKILLS_DIR.exists():
            for skill_dir in sorted(DIST_SKILLS_DIR.iterdir()):
                if skill_dir.is_dir():
                    files_to_check.extend([
                        Path.home() / ".claude/skills" / skill_dir.name,
                        Path.home() / ".config/opencode/skills" / skill_dir.name
                    ])
        
        # Rules
        if DIST_RULES_DIR.exists():
            for f in DIST_RULES_DIR.glob("*.md"):
                files_to_check.append(Path.home() / ".claude/rules" / f.name)
    else:
        # Local files that should be symlinks (or copies in copy mode)
        files_to_check.extend([
            Path("./CLAUDE.md"),
            Path("./AGENTS.md")
        ])
        
        # Local agents
        claude_agents_dir = DIST_CLAUDE_DIR / "agents"
        if claude_agents_dir.exists():
            for f in claude_agents_dir.glob("*.md"):
                files_to_check.append(Path(".claude/agents") / f.name)
        
        opencode_agents_dir = DIST_OPENCODE_DIR / "agents"
        if opencode_agents_dir.exists():
            for f in opencode_agents_dir.glob("*.md"):
                files_to_check.append(Path(".opencode/agents") / f.name)
    
    for file in files_to_check:
        if file.exists() and not file.is_symlink():
            # Determine source file
            source_file = None
            if "/agents/" in str(file):
                name = file.name
                if "opencode" in str(file):
                    source_file = DIST_OPENCODE_DIR / "agents" / name
                else:
                    source_file = DIST_CLAUDE_DIR / "agents" / name
            elif "/skills/" in str(file):
                skill_name = file.name
                source_file = DIST_SKILLS_DIR / skill_name
            elif "/rules/" in str(file):
                name = file.name
                source_file = DIST_RULES_DIR / name
            elif file.name == "CLAUDE.md":
                source_file = DIST_CLAUDE_DIR / "CLAUDE.md"
            elif file.name == "AGENTS.md":
                source_file = DIST_OPENCODE_DIR / "AGENTS.md"
            elif file.name == "copilot-instructions.md":
                source_file = DIST_GITHUB_DIR / "copilot-instructions.md"
            
            if source_file:
                issues.append(Issue("shadowed", str(file),
                                  "Regular file instead of symlink. Won't receive updates."))
                fix_actions.append(FixAction("RELINK", str(file),
                                           f"replace copy with symlink to {source_file}"))

def check_missing_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for source files that aren't installed."""
    if scope != "global":
        return  # Only check global installations for missing files
    
    for cli in ["claude", "opencode"]:
        base = _cli_base_dir(cli, scope)
        dist_dir = DIST_CLAUDE_DIR if cli == "claude" else DIST_OPENCODE_DIR
        
        # Agents
        installed, expected = _count_agents(cli, scope)
        if expected > 0 and installed == 0:
            issues.append(Issue("missing_group", f"{cli}/agents", f"not installed ({expected} available)"))
            fix_actions.append(FixAction("INSTALL", f"{cli}/agents", f"install {expected} agents"))
        elif expected > installed:
            agents_src = dist_dir / "agents"
            if agents_src.exists():
                for f in agents_src.glob("*.md"):
                    target = base / "agents" / f.name
                    if not target.exists():
                        issues.append(Issue("missing", str(target), "Source exists but not installed"))
                        fix_actions.append(FixAction("INSTALL", str(target), f"install {cli} agent"))
        
        # Skills
        installed, expected = _count_skills(cli, scope)
        if expected > 0 and installed == 0:
            issues.append(Issue("missing_group", f"{cli}/skills", f"not installed ({expected} available)"))
            fix_actions.append(FixAction("INSTALL", f"{cli}/skills", f"install {expected} skills"))
        elif expected > installed:
            if DIST_SKILLS_DIR.exists():
                for skill_dir in sorted(DIST_SKILLS_DIR.iterdir()):
                    if skill_dir.is_dir():
                        target = base / "skills" / skill_dir.name
                        if not target.exists():
                            issues.append(Issue("missing", str(target), "Source exists but not installed"))
                            fix_actions.append(FixAction("INSTALL", str(target), "install skill"))
        
        # Config
        all_ok, desc, missing = _check_config(cli, scope)
        if not all_ok:
            if desc == "not installed":
                issues.append(Issue("missing_group", f"{cli}/config", "not installed"))
                fix_actions.append(FixAction("INSTALL", f"{cli}/config", "install config files"))
            else:
                # Some installed, some missing - list individual missing
                if cli == "claude":
                    config_files = [
                        (CLAUDE_HOME / "CLAUDE.md", DIST_CLAUDE_DIR / "CLAUDE.md"),
                        (GITHUB_HOME / "copilot-instructions.md", DIST_GITHUB_DIR / "copilot-instructions.md")
                    ]
                else:
                    config_files = [
                        (OPENCODE_HOME / "AGENTS.md", DIST_OPENCODE_DIR / "AGENTS.md")
                    ]
                for target, source in config_files:
                    if source.exists() and not target.exists():
                        issues.append(Issue("missing", str(target), "Source exists but not installed"))
                        fix_actions.append(FixAction("INSTALL", str(target), f"install from {source}"))
        
        # Rules (Claude only)
        if cli == "claude":
            installed, expected = _count_rules(scope)
            if expected > 0 and installed == 0:
                issues.append(Issue("missing_group", f"{cli}/rules", f"not installed ({expected} available)"))
                fix_actions.append(FixAction("INSTALL", f"{cli}/rules", f"install {expected} rules"))
            elif expected > installed:
                if DIST_RULES_DIR.exists():
                    for f in DIST_RULES_DIR.glob("*.md"):
                        target = CLAUDE_HOME / "rules" / f.name
                        if not target.exists():
                            issues.append(Issue("missing", str(target), "Source exists but not installed"))
                            fix_actions.append(FixAction("INSTALL", str(target), "install rule"))

def check_content_drift(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for copied files that differ from source."""
    if scope == "global":
        base_dirs = [
            Path.home() / ".claude",
            Path.home() / ".config/opencode",
            Path.home() / ".github"
        ]
    else:
        base_dirs = [Path(".claude"), Path(".opencode"), Path(".")]
    
    for base_dir in base_dirs:
        if not base_dir.exists():
            continue
        
        # Find all .md files and check against source
        for md_file in base_dir.rglob("*.md"):
            if md_file.is_symlink():
                continue  # Skip symlinks
                
            source_file = None
            
            # Determine source file
            if "/agents/" in str(md_file):
                name = md_file.name
                if "opencode" in str(md_file):
                    source_file = DIST_OPENCODE_DIR / "agents" / name
                else:
                    source_file = DIST_CLAUDE_DIR / "agents" / name
            elif "/rules/" in str(md_file):
                name = md_file.name
                source_file = DIST_RULES_DIR / name
            elif md_file.name == "CLAUDE.md":
                source_file = DIST_CLAUDE_DIR / "CLAUDE.md"
            elif md_file.name == "AGENTS.md":
                source_file = DIST_OPENCODE_DIR / "AGENTS.md"
            elif md_file.name == "copilot-instructions.md":
                source_file = DIST_GITHUB_DIR / "copilot-instructions.md"
            
            if source_file and source_file.exists() and files_differ(md_file, source_file):
                issues.append(Issue("drift", str(md_file),
                                  "Content differs from source. Local changes will be lost on update."))

def check_build_freshness(issues: List[Issue], fix_actions: List[FixAction]):
    """Check if source files are newer than generated files."""
    agents_yaml = AGENTS_YAML
    
    # Check agents.yaml vs generated agents
    if agents_yaml.exists():
        source_time = agents_yaml.stat().st_mtime
        
        # Check Claude agents
        claude_agents_dir = DIST_CLAUDE_DIR / "agents"
        if claude_agents_dir.exists():
            for f in claude_agents_dir.glob("*.md"):
                gen_time = f.stat().st_mtime
                if source_time > gen_time:
                    issues.append(Issue("build_stale", str(f), "agents.yaml is newer than generated files"))
                    fix_actions.append(FixAction("BUILD", "agents/", "regenerate from source"))
                    break
        
        # Check OpenCode agents
        opencode_agents_dir = DIST_OPENCODE_DIR / "agents"
        if opencode_agents_dir.exists():
            for f in opencode_agents_dir.glob("*.md"):
                gen_time = f.stat().st_mtime
                if source_time > gen_time:
                    issues.append(Issue("build_stale", str(f), "agents.yaml is newer than generated files"))
                    fix_actions.append(FixAction("BUILD", "agents-opencode/", "regenerate from source"))
                    break
    
    # Check individual source agents
    source_agents_dir = AGENTS_DIR
    if source_agents_dir.exists():
        for src_file in source_agents_dir.glob("*.md"):
            source_time = src_file.stat().st_mtime
            
            # Check corresponding generated files
            claude_gen = DIST_CLAUDE_DIR / "agents" / src_file.name
            opencode_gen = DIST_OPENCODE_DIR / "agents" / src_file.name
            
            if claude_gen.exists():
                gen_time = claude_gen.stat().st_mtime
                if source_time > gen_time:
                    issues.append(Issue("build_stale", str(claude_gen), 
                                      f"{src_file} is newer than generated file"))
                    fix_actions.append(FixAction("BUILD", str(claude_gen), "regenerate from source"))
            
            if opencode_gen.exists():
                gen_time = opencode_gen.stat().st_mtime
                if source_time > gen_time:
                    issues.append(Issue("build_stale", str(opencode_gen),
                                      f"{src_file} is newer than generated file"))
                    fix_actions.append(FixAction("BUILD", str(opencode_gen), "regenerate from source"))
    
    # Check global source files
    global_sources = [
        (GLOBAL_MD, DIST_CLAUDE_DIR / "CLAUDE.md"),
        (GLOBAL_MD, DIST_OPENCODE_DIR / "AGENTS.md"),
        (GLOBAL_COPILOT_MD, DIST_GITHUB_DIR / "copilot-instructions.md")
    ]
    
    for src, gen in global_sources:
        if src.exists() and gen.exists():
            src_time = src.stat().st_mtime
            gen_time = gen.stat().st_mtime
            
            if src_time > gen_time:
                issues.append(Issue("build_stale", str(gen), f"{src} is newer than generated file"))
                fix_actions.append(FixAction("BUILD", str(gen), "regenerate from source"))

def _cli_base_dir(cli: str, scope: str) -> Path:
    """Get base directory for a CLI."""
    if scope == "global":
        return CLAUDE_HOME if cli == "claude" else OPENCODE_HOME
    else:
        return Path(".claude") if cli == "claude" else Path(".opencode")

def _count_agents(cli: str, scope: str) -> tuple:
    """Count (installed, expected) agents for a CLI."""
    base = _cli_base_dir(cli, scope)
    agents_dir = base / "agents"
    installed = len(list(agents_dir.glob("*.md"))) if agents_dir.exists() else 0
    
    dist_dir = DIST_CLAUDE_DIR if cli == "claude" else DIST_OPENCODE_DIR
    expected_dir = dist_dir / "agents"
    expected = len(list(expected_dir.glob("*.md"))) if expected_dir.exists() else 0
    
    return installed, expected

def _count_skills(cli: str, scope: str) -> tuple:
    """Count (installed, expected) skills for a CLI. Excludes broken symlinks."""
    base = _cli_base_dir(cli, scope)
    skills_dir = base / "skills"
    if skills_dir.exists():
        installed = len([d for d in skills_dir.iterdir() if d.is_dir() and d.exists()])
    else:
        installed = 0
    expected = len([d for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()]) if DIST_SKILLS_DIR.exists() else 0
    return installed, expected

def _count_rules(scope: str) -> tuple:
    """Count (installed, expected) rules. Only for Claude Code."""
    if scope == "global":
        rules_dir = CLAUDE_HOME / "rules"
    else:
        rules_dir = Path(".claude/rules")
    installed = len(list(rules_dir.glob("*.md"))) if rules_dir.exists() else 0
    expected = len(list(DIST_RULES_DIR.glob("*.md"))) if DIST_RULES_DIR.exists() else 0
    return installed, expected

def _check_config(cli: str, scope: str) -> tuple:
    """Check config files for a CLI. Returns (all_installed: bool, description: str).
    
    For Claude Code global: CLAUDE.md + copilot-instructions.md
    For Claude Code local: CLAUDE.md
    For OpenCode: AGENTS.md
    """
    if cli == "claude":
        if scope == "global":
            files = [
                (CLAUDE_HOME / "CLAUDE.md", "CLAUDE.md"),
                (GITHUB_HOME / "copilot-instructions.md", "copilot-instructions.md")
            ]
        else:
            files = [(Path("./CLAUDE.md"), "CLAUDE.md")]
    else:
        if scope == "global":
            files = [(OPENCODE_HOME / "AGENTS.md", "AGENTS.md")]
        else:
            files = [(Path("./AGENTS.md"), "AGENTS.md")]
    
    installed_names = [name for path, name in files if path.exists()]
    missing_names = [name for path, name in files if not path.exists()]
    all_installed = len(missing_names) == 0
    desc = ", ".join(installed_names) if installed_names else "not installed"
    
    return all_installed, desc, missing_names
    return all_installed, desc

def count_stale(issues: List[Issue], item_type: str) -> int:
    """Count stale issues of a specific type."""
    count = 0
    for issue in issues:
        if issue.type == "stale" and item_type in issue.file:
            count += 1
    return count

def _print_status(label: str, installed: int, expected: int):
    """Print OK/WARN status for a component."""
    if installed == 0 and expected == 0:
        ok(f"{label} (none available)", indent=4)
    elif installed == 0:
        warn(f"{label} (not installed, {expected} available)", indent=4)
    elif installed >= expected:
        ok(f"{label} ({installed} installed)", indent=4)
    else:
        missing = expected - installed
        warn(f"{label} ({installed} installed, {missing} missing)", indent=4)

def print_summary(scope: str):
    """Print installation summary grouped by CLI."""
    label = "global" if scope == "global" else "local"
    print(f"Checking AgentNotes {label} installation:")
    print("")
    
    for cli, cli_name in [("claude", "Claude Code"), ("opencode", "OpenCode")]:
        base = _cli_base_dir(cli, scope)
        print(f"  {cli_name} ({base})")
        
        # Agents
        installed, expected = _count_agents(cli, scope)
        _print_status("agents", installed, expected)
        
        # Skills
        installed, expected = _count_skills(cli, scope)
        _print_status("skills", installed, expected)
        
        # Config
        all_ok, desc, missing = _check_config(cli, scope)
        if all_ok:
            ok(f"config ({desc})", indent=4)
        elif desc == "not installed":
            warn("config (not installed)", indent=4)
        else:
            missing_str = ", ".join(missing)
            warn(f"config ({desc}) — missing: {missing_str}", indent=4)
        
        # Rules (Claude Code only)
        if cli == "claude":
            installed, expected = _count_rules(scope)
            _print_status("rules", installed, expected)

def print_issues(issues: List[Issue]) -> bool:
    """Print found issues. Returns True if no issues."""
    if not issues:
        print("")
        print(f"{Color.GREEN}No issues found.{Color.NC}")
        return True
    
    # Check if fully not installed
    non_build_issues = [i for i in issues if i.type != "build_stale"]
    if non_build_issues and all(i.type == "missing_group" for i in non_build_issues):
        print(f"\nNot installed. Run '{Color.CYAN}agent-notes install{Color.NC}' to set up.")
        return False
    
    print("")
    
    # Group broken symlinks by directory for cleaner output
    broken_by_dir: Dict[str, int] = {}
    other_issues: List[Issue] = []
    for iss in issues:
        if iss.type == "broken":
            parent = str(Path(iss.file).parent)
            broken_by_dir[parent] = broken_by_dir.get(parent, 0) + 1
        elif iss.type == "missing_group":
            continue  # Already shown in summary
        else:
            other_issues.append(iss)
    
    display_count = len(broken_by_dir) + len(other_issues)
    print(f"{Color.YELLOW}Warning: {display_count} issue(s) found{Color.NC}")
    print("")
    
    # Print grouped broken symlinks
    for dir_path, count in broken_by_dir.items():
        print(f"  {Color.RED}✗ Broken symlinks: {Color.NC}{dir_path}/ ({count} broken)")
        print(f"    Fix: run '{Color.CYAN}agent-notes install{Color.NC}' to recreate")
        print("")
    
    # Print other issues
    for iss in other_issues:
        if iss.type == "stale":
            print(f"  {Color.RED}✗ Stale: {Color.NC}{iss.file}")
            print(f"    {iss.message}")
            print(f"    Fix: run '{Color.CYAN}agent-notes doctor --fix{Color.NC}' to remove")
        elif iss.type == "shadowed":
            print(f"  {Color.YELLOW}✗ Shadowed: {Color.NC}{iss.file}")
            print(f"    {iss.message}")
            print(f"    Fix: run '{Color.CYAN}agent-notes doctor --fix{Color.NC}' to replace with symlink")
        elif iss.type == "missing":
            print(f"  {Color.YELLOW}✗ Missing: {Color.NC}{iss.file}")
            print(f"    {iss.message}")
            print(f"    Fix: run '{Color.CYAN}agent-notes doctor --fix{Color.NC}' or '{Color.CYAN}agent-notes install{Color.NC}'")
        elif iss.type == "drift":
            print(f"  {Color.CYAN}✗ Content drift: {Color.NC}{iss.file}")
            print(f"    {iss.message}")
        elif iss.type == "build_stale":
            print(f"  {Color.YELLOW}✗ Build stale: {Color.NC}{iss.file}")
            print(f"    {iss.message}")
            print(f"    Fix: run '{Color.CYAN}agent-notes build{Color.NC}'")
        else:
            continue
        
        print("")
    
    print(f"Run '{Color.CYAN}agent-notes doctor --fix{Color.NC}' to resolve these issues.")
    return False

def do_fix(issues: List[Issue], fix_actions: List[FixAction]) -> bool:
    """Apply fixes with user confirmation."""
    non_build = [i for i in issues if i.type != "build_stale"]
    if non_build and all(i.type == "missing_group" for i in non_build):
        print(f"Not installed. Run '{Color.CYAN}agent-notes install{Color.NC}' to set up.")
        return True
    
    if not fix_actions:
        print(f"{Color.GREEN}No fixes needed.{Color.NC}")
        return True
    
    print("The following changes will be made:")
    print("")
    
    for action in fix_actions:
        if action.action == "DELETE":
            print(f"  {Color.RED}DELETE{Color.NC}  {action.file} ({action.details})")
        elif action.action == "RELINK":
            print(f"  {Color.CYAN}RELINK{Color.NC}  {action.file} ({action.details})")
        elif action.action == "INSTALL":
            print(f"  {Color.GREEN}INSTALL{Color.NC} {action.file} ({action.details})")
        elif action.action == "BUILD":
            print(f"  {Color.CYAN}BUILD{Color.NC}   {action.file} ({action.details})")
    
    print("")
    response = input("Proceed? [y/N] ")
    
    if response.lower() != 'y':
        print("Aborted.")
        return False
    
    print("")
    print("Applying fixes...")
    
    needs_install = False
    needs_build = False
    
    for action in fix_actions:
        if action.action == "DELETE":
            file_path = Path(action.file)
            if file_path.exists() or file_path.is_symlink():
                if file_path.is_symlink():
                    file_path.unlink()
                elif file_path.is_dir():
                    import shutil
                    shutil.rmtree(file_path)
                else:
                    file_path.unlink()
                print(f"  {Color.RED}DELETED{Color.NC}  {action.file}")
        
        elif action.action == "RELINK":
            # Extract source from details
            if "symlink to " in action.details:
                source_file_str = action.details.split("symlink to ")[1]
                source_file = Path(source_file_str)
                
                if source_file.exists():
                    file_path = Path(action.file)
                    # Backup original
                    if file_path.exists() and not file_path.is_symlink():
                        backup_path = Path(str(file_path) + ".bak")
                        file_path.rename(backup_path)
                    
                    if file_path.exists():
                        file_path.unlink()
                    
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.symlink_to(source_file.resolve())
                    print(f"  {Color.CYAN}RELINKED{Color.NC} {action.file}")
                else:
                    print(f"  {Color.RED}FAILED{Color.NC}   {action.file} (source not found: {source_file})")
        
        elif action.action == "INSTALL":
            needs_install = True
        
        elif action.action == "BUILD":
            needs_build = True
    
    # Handle bulk operations
    if needs_install:
        print(f"  {Color.GREEN}RUNNING{Color.NC} install to install missing components...")
        from .install import install
        install()
    
    if needs_build:
        print(f"  {Color.CYAN}NOTICE{Color.NC}   Build stale issues detected.")
        print("           Run the build process to regenerate files from source.")
    
    return True

def doctor(local: bool = False, fix: bool = False) -> None:
    """Check installation health and optionally fix issues."""
    issues: List[Issue] = []
    fix_actions: List[FixAction] = []
    
    scope = "local" if local else "global"
    
    # Run all checks
    if scope == "global":
        print_summary("global")
        check_stale_files("global", issues, fix_actions)
        check_broken_symlinks("global", issues, fix_actions)
        check_shadowed_files("global", issues, fix_actions)
        check_missing_files("global", issues, fix_actions)
        check_content_drift("global", issues, fix_actions)
    else:
        print_summary("local")
        check_stale_files("local", issues, fix_actions)
        check_broken_symlinks("local", issues, fix_actions)
        check_shadowed_files("local", issues, fix_actions)
        check_content_drift("local", issues, fix_actions)
    
    # Always check build freshness
    check_build_freshness(issues, fix_actions)
    
    # Handle results
    if fix:
        print("")
        success = do_fix(issues, fix_actions)
        if success:
            # Re-run checks to verify
            print("")
            print("Verifying fixes...")
            
            # Clear and re-run checks
            issues.clear()
            fix_actions.clear()
            
            if scope == "global":
                check_stale_files("global", issues, fix_actions)
                check_broken_symlinks("global", issues, fix_actions)
                check_shadowed_files("global", issues, fix_actions)
                check_missing_files("global", issues, fix_actions)
                check_content_drift("global", issues, fix_actions)
            else:
                check_stale_files("local", issues, fix_actions)
                check_broken_symlinks("local", issues, fix_actions)
                check_shadowed_files("local", issues, fix_actions)
                check_content_drift("local", issues, fix_actions)
            
            check_build_freshness(issues, fix_actions)
            
            if not issues:
                print(f"{Color.GREEN}All issues resolved.{Color.NC}")
            else:
                print(f"{Color.YELLOW}{len(issues)} issue(s) remain.{Color.NC}")
    else:
        if not print_issues(issues):
            exit(1)