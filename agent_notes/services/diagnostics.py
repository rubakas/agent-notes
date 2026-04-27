"""Diagnostic checks and fixes for agent-notes installation."""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from ..domain.diagnostics import Issue, FixAction
from .fs import resolve_symlink, symlink_target_exists, files_differ


def check_stale_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for installed files without matching source - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ..cli_backend import load_registry
    from .. import install_state, doctor_checks
    from ..state import get_scope
    from pathlib import Path
    
    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)
    doctor_checks.check_stale(scope, scope_state, registry, issues, fix_actions)

def _find_dist_source(symlink: Path, scope: str) -> Optional[Path]:
    """Map an installed path back to its dist source for relinking.
    
    Iterates all registered backends; returns first dist source whose
    component and filename match the given symlink.
    """
    from ..cli_backend import load_registry
    from .. import installer
    registry = load_registry()
    
    symlink = symlink.resolve() if symlink.exists() else Path(os.path.abspath(symlink))
    name = symlink.name
    parent_name = symlink.parent.name  # e.g. "agents", "skills", "rules"
    
    # Try each backend's dist source for this component
    for backend in registry.all():
        src_dir = installer.dist_source_for(backend, parent_name)
        if src_dir is None:
            continue
        candidate = src_dir / name
        if candidate.exists():
            return candidate
    
    # Config files (global only): check each backend's config_filename
    if scope == "global":
        for backend in registry.all():
            config_fn = installer.config_filename_for(backend)
            if config_fn == name:
                src = installer.dist_source_for(backend, "config")
                if src is not None:
                    candidate = src / config_fn
                    if candidate.exists():
                        return candidate
    
    # Scripts
    def _get_bin_home():
        from ..config import BIN_HOME
        return BIN_HOME
        
    def _get_dist_scripts_dir():
        from ..config import DIST_SCRIPTS_DIR
        return DIST_SCRIPTS_DIR
        
    bin_home = _get_bin_home()
    dist_scripts_dir = _get_dist_scripts_dir()
    
    if bin_home and str(symlink).startswith(str(bin_home)):
        if dist_scripts_dir:
            source = dist_scripts_dir / name
            if source.exists():
                return source
    
    # Universal skills
    def _get_dist_skills_dir():
        from ..config import DIST_SKILLS_DIR
        return DIST_SKILLS_DIR
        
    if parent_name == "skills":
        dist_skills_dir = _get_dist_skills_dir()
        if dist_skills_dir:
            source = dist_skills_dir / name
            if source.exists():
                return source
    
    return None


def check_broken_symlinks(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for symlinks with non-existent targets - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ..cli_backend import load_registry
    from .. import install_state, doctor_checks
    from ..state import get_scope
    from pathlib import Path
    
    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)
    doctor_checks.check_broken(scope, registry, issues, fix_actions, scope_state)

def check_shadowed_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for regular files where symlinks are expected - TARGETED check only."""
    from ..cli_backend import load_registry
    from .. import install_state, doctor_checks
    from ..state import get_scope
    from pathlib import Path
    
    # Get expected paths and check each one individually
    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)
    
    # Only check paths we know should exist
    for src, dst, backend_name, component in doctor_checks.expected_paths_for_install(registry, scope):
        if dst.exists() and not dst.is_symlink():
            # This is a regular file where we expected a symlink (or copy in copy mode)
            # If we're in symlink mode, this is shadowed
            if scope_state is None or scope_state.mode == "symlink":
                issues.append(Issue("shadowed", str(dst),
                              "Regular file instead of symlink. Won't receive updates."))
                fix_actions.append(FixAction("RELINK", str(dst),
                                           f"replace copy with symlink to {src}"))

def check_missing_files(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for source files that aren't installed - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ..cli_backend import load_registry
    from .. import doctor_checks, install_state
    from ..state import get_scope
    from pathlib import Path
    
    registry = load_registry()
    # Pass scope state so opted-out backends aren't flagged as "missing".
    state = install_state.load_current_state()
    scope_state = None
    if state is not None:
        try:
            project_path = Path.cwd().resolve() if scope == "local" else None
            scope_state = get_scope(state, scope, project_path)
        except (ValueError, KeyError):
            scope_state = None
    # Call via kwargs only when we actually have scope_state — tests that
    # replace doctor_checks.check_missing with a narrower signature still work.
    if scope_state is not None:
        doctor_checks.check_missing(scope, registry, issues, fix_actions, scope_state=scope_state)
    else:
        doctor_checks.check_missing(scope, registry, issues, fix_actions)

def check_content_drift(scope: str, issues: List[Issue], fix_actions: List[FixAction]):
    """Check for copied files that differ from source - DELEGATED to doctor_checks."""
    # This function is kept for backwards compatibility but delegates to the new module
    from ..cli_backend import load_registry
    from .. import install_state, doctor_checks
    from ..state import get_scope
    from pathlib import Path
    
    registry = load_registry()
    state = install_state.load_current_state()
    if state is None:
        scope_state = None
    else:
        project_path = Path.cwd() if scope == "local" else None
        scope_state = get_scope(state, scope, project_path)
    doctor_checks.check_drift(scope, registry, issues, fix_actions, scope_state)

def check_build_freshness(issues: List[Issue], fix_actions: List[FixAction]):
    """Check if source files are newer than generated files."""
    from ..config import AGENTS_YAML, AGENTS_DIR, SCRIPTS_DIR, DIST_SCRIPTS_DIR
    agents_yaml = AGENTS_YAML
    
    # Check agents.yaml vs generated agents
    if agents_yaml.exists():
        source_time = agents_yaml.stat().st_mtime
        from ..cli_backend import load_registry
        from ..config import dist_dir_for
        
        registry = load_registry()
        for backend in registry.with_feature("agents"):
            agents_dir = dist_dir_for(backend) / backend.layout.get("agents", "agents")
            if agents_dir.exists():
                for f in agents_dir.glob("*.md"):
                    gen_time = f.stat().st_mtime
                    if source_time > gen_time:
                        issues.append(Issue("build_stale", str(f), "agents.yaml is newer than generated files"))
                        fix_actions.append(FixAction("BUILD", f"agents-{backend.name}/", "regenerate from source"))
                        break
    
    # Check individual source agents
    source_agents_dir = AGENTS_DIR
    if source_agents_dir.exists():
        from ..cli_backend import load_registry
        from ..config import dist_dir_for
        
        registry = load_registry()
        for src_file in source_agents_dir.glob("*.md"):
            source_time = src_file.stat().st_mtime
            
            # Check corresponding generated files across all backends with agents
            for backend in registry.with_feature("agents"):
                gen_file = dist_dir_for(backend) / backend.layout.get("agents", "agents") / src_file.name
                if gen_file.exists():
                    gen_time = gen_file.stat().st_mtime
                    if source_time > gen_time:
                        issues.append(Issue("build_stale", str(gen_file), 
                                          f"{src_file} is newer than generated file"))
                        fix_actions.append(FixAction("BUILD", str(gen_file), "regenerate from source"))
    
    # Check scripts source vs dist
    if SCRIPTS_DIR.exists() and DIST_SCRIPTS_DIR.exists():
        for src_file in SCRIPTS_DIR.iterdir():
            if src_file.is_file():
                dist_file = DIST_SCRIPTS_DIR / src_file.name
                if dist_file.exists() and src_file.stat().st_mtime > dist_file.stat().st_mtime:
                    issues.append(Issue("build_stale", str(dist_file),
                                      f"{src_file} is newer than generated file"))
                    fix_actions.append(FixAction("BUILD", str(dist_file), "regenerate from source"))

    # Check global source files
    from ..cli_backend import load_registry
    from ..config import global_template_path, global_output_path
    
    registry = load_registry()
    for backend in registry.all():
        src = global_template_path(backend)
        gen = global_output_path(backend)
        
        if src and gen and src.exists() and gen.exists():
            src_time = src.stat().st_mtime
            gen_time = gen.stat().st_mtime
            
            if src_time > gen_time:
                issues.append(Issue("build_stale", str(gen), f"{src} is newer than generated file"))
                fix_actions.append(FixAction("BUILD", str(gen), "regenerate from source"))

    # Check plugin agents are up-to-date with dist agents
    from ..config import ROOT, DIST_DIR
    plugin_agents_dir = ROOT / ".claude-plugin" / "agents"
    dist_claude_agents = DIST_DIR / "claude" / "agents"
    if plugin_agents_dir.exists() and dist_claude_agents.exists():
        for dist_file in dist_claude_agents.glob("*.md"):
            plugin_file = plugin_agents_dir / dist_file.name
            if plugin_file.exists() and dist_file.stat().st_mtime > plugin_file.stat().st_mtime:
                issues.append(Issue("build_stale", str(plugin_file),
                                    "dist agent is newer than plugin agent — run scripts/build-plugin.sh"))
                fix_actions.append(FixAction("BUILD", ".claude-plugin/agents/", "run scripts/build-plugin.sh"))
                break  # one warning is enough

    # Check user config freshness against dist agents
    from ..services.user_config import config_path
    user_cfg = config_path()
    if user_cfg.exists() and dist_claude_agents.exists():
        cfg_time = user_cfg.stat().st_mtime
        for dist_file in dist_claude_agents.glob("*.md"):
            if cfg_time > dist_file.stat().st_mtime:
                issues.append(Issue("build_stale", str(user_cfg),
                                    "user config is newer than dist agents — run: agent-notes build"))
                fix_actions.append(FixAction("BUILD", "dist/", "regenerate from source"))
                break

def _cli_base_dir(backend, scope: str) -> Path:
    """Get base directory for a CLI backend."""
    from ..cli_backend import CLIBackend
    if scope == "global":
        return backend.global_home
    else:
        return Path(backend.local_dir)

def _count_agents(backend, scope: str) -> tuple:
    """Count (installed, expected) agents for a CLI backend."""
    from .. import installer
    
    if not backend.supports("agents"):
        return 0, 0
        
    # Count installed
    agents_dir = installer.target_dir_for(backend, "agents", scope)
    installed = len(list(agents_dir.glob("*.md"))) if agents_dir and agents_dir.exists() else 0
    
    # Count expected
    src_dir = installer.dist_source_for(backend, "agents")
    expected = len(list(src_dir.glob("*.md"))) if src_dir and src_dir.exists() else 0
    
    return installed, expected

def _count_skills(backend, scope: str) -> tuple:
    """Count (installed, expected) skills for a CLI backend. Excludes broken symlinks."""
    from .. import installer
    
    # Helper to get DIST_SKILLS_DIR
    def _get_dist_skills_dir():
        from ..config import DIST_SKILLS_DIR
        return DIST_SKILLS_DIR
    
    if not backend.supports("skills"):
        return 0, 0
        
    # Count installed
    skills_dir = installer.target_dir_for(backend, "skills", scope)
    if skills_dir and skills_dir.exists():
        installed = len([d for d in skills_dir.iterdir() if d.is_dir() and d.exists()])
    else:
        installed = 0
        
    # Count expected (universal skills)
    dist_skills_dir = _get_dist_skills_dir()
    expected = len([d for d in dist_skills_dir.iterdir() if d.is_dir()]) if dist_skills_dir and dist_skills_dir.exists() else 0
    return installed, expected

def _count_scripts() -> tuple:
    """Count (installed, expected) scripts in ~/.local/bin/."""
    # Helper functions to get config values
    def _get_bin_home():
        from ..config import BIN_HOME
        return BIN_HOME
        
    def _get_dist_scripts_dir():
        from ..config import DIST_SCRIPTS_DIR
        return DIST_SCRIPTS_DIR
    
    bin_home = _get_bin_home()
    dist_scripts_dir = _get_dist_scripts_dir()
    
    installed = len([f for f in bin_home.iterdir() if f.is_file() and (dist_scripts_dir / f.name).exists()]) if bin_home and bin_home.exists() else 0
    expected = len([f for f in dist_scripts_dir.iterdir() if f.is_file()]) if dist_scripts_dir and dist_scripts_dir.exists() else 0
    return installed, expected


def _count_rules(backend, scope: str) -> tuple:
    """Count (installed, expected) rules for a CLI backend."""
    from .. import installer
    
    # Helper to get DIST_RULES_DIR
    def _get_dist_rules_dir():
        from ..config import DIST_RULES_DIR
        return DIST_RULES_DIR
    
    if not backend.supports("rules"):
        return 0, 0
        
    # Count installed
    rules_dir = installer.target_dir_for(backend, "rules", scope)
    installed = len(list(rules_dir.glob("*.md"))) if rules_dir and rules_dir.exists() else 0
    
    # Count expected
    dist_rules_dir = _get_dist_rules_dir()
    expected = len(list(dist_rules_dir.glob("*.md"))) if dist_rules_dir and dist_rules_dir.exists() else 0
    return installed, expected

def _check_config(backend, scope: str) -> tuple:
    """Check config files for a CLI backend. Returns (all_installed: bool, description: str, missing: list)."""
    from .. import installer
    
    config_file = installer.config_filename_for(backend)
    if not config_file:
        return True, "no config file", []
    
    config_dir = installer.target_dir_for(backend, "config", scope)
    if not config_dir:
        return False, "not supported", [config_file]
    
    config_path = config_dir / config_file
    if config_path.exists():
        return True, config_file, []
    else:
        return False, "not installed", [config_file]

def count_stale(issues: List[Issue], item_type: str) -> int:
    """Count stale issues of a specific type."""
    count = 0
    for issue in issues:
        if issue.type == "stale" and item_type in issue.file:
            count += 1
    return count

def _print_status(label: str, installed: int, expected: int):
    """Print OK/WARN status for a component."""
    from ..config import ok, warn
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
    
    from ..cli_backend import load_registry
    registry = load_registry()
    for backend in registry.all():
        if not backend.supports("agents"):
            continue
        cli = backend.name
        cli_name = backend.label
        base = _cli_base_dir(backend, scope)
        print(f"  {cli_name} ({base})")
        
        # Agents
        installed, expected = _count_agents(backend, scope)
        _print_status("agents", installed, expected)
        
        # Skills
        installed, expected = _count_skills(backend, scope)
        _print_status("skills", installed, expected)
        
        # Config
        from ..config import ok, warn
        all_ok, desc, missing = _check_config(backend, scope)
        if all_ok:
            ok(f"config ({desc})", indent=4)
        elif desc == "not installed":
            warn("config (not installed)", indent=4)
        else:
            missing_str = ", ".join(missing)
            warn(f"config ({desc}) — missing: {missing_str}", indent=4)
        
        # Rules (only for backends that support rules)
        if backend.supports("rules"):
            installed, expected = _count_rules(backend, scope)
            _print_status("rules", installed, expected)

        # Scripts (global only, not per-CLI)
        if scope == "global":
            from ..config import BIN_HOME
            installed, expected = _count_scripts()
            _print_status(f"scripts ({BIN_HOME})", installed, expected)

def print_issues(issues: List[Issue]) -> bool:
    """Print found issues. Returns True if no issues."""
    from ..config import Color
    
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
    """Apply fixes with user confirmation and safety guards."""
    from .. import install_state
    from ..config import Color
    
    non_build = [i for i in issues if i.type != "build_stale"]
    if non_build and all(i.type == "missing_group" for i in non_build):
        print(f"Not installed. Run '{Color.CYAN}agent-notes install{Color.NC}' to set up.")
        return True
    
    if not fix_actions:
        print(f"{Color.GREEN}No fixes needed.{Color.NC}")
        return True
    
    print("The following changes will be made:")
    print("")
    
    # Safety check: verify DELETE actions are safe
    state = install_state.load_current_state()
    safe_delete_paths = set()
    if state is not None:
        # All paths in state.json are safe to delete
        # Check global install
        if state.global_install:
            for backend_name, bs in state.global_install.clis.items():
                for component_type, items in bs.installed.items():
                    for name, item in items.items():
                        safe_delete_paths.add(str(Path(item.target)))
        
        # Check local installs
        for project_path, scope_state in state.local_installs.items():
            for backend_name, bs in scope_state.clis.items():
                for component_type, items in bs.installed.items():
                    for name, item in items.items():
                        safe_delete_paths.add(str(Path(item.target)))
    
    for action in fix_actions:
        if action.action == "DELETE":
            file_path = Path(action.file)
            # Safety check: only allow DELETE if path is in state.json or is a symlink to our dist/
            if str(file_path) not in safe_delete_paths:
                if file_path.is_symlink():
                    target = file_path.readlink()
                    if not target.is_absolute():
                        target = file_path.parent / target
                    # Check if symlink target is within our dist/ directory
                    try:
                        from ..config import DIST_DIR
                        target_resolved = target.resolve()
                        dist_resolved = DIST_DIR.resolve()
                        if not str(target_resolved).startswith(str(dist_resolved)):
                            print(f"  {Color.RED}UNSAFE DELETE BLOCKED:{Color.NC} {action.file}")
                            print(f"    Symlink target {target} is not in agent-notes dist/")
                            print(f"    This appears to be a third-party file. Skipping for safety.")
                            continue
                    except (OSError, ValueError):
                        print(f"  {Color.RED}UNSAFE DELETE BLOCKED:{Color.NC} {action.file}")
                        print(f"    Cannot verify symlink target safety. Skipping.")
                        continue
                else:
                    print(f"  {Color.RED}UNSAFE DELETE BLOCKED:{Color.NC} {action.file}")
                    print(f"    File not in state.json and not a symlink to our dist/")
                    print(f"    This may be a user file. Skipping for safety.")
                    continue
            
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
            # Recheck safety (same logic as above)
            if str(file_path) not in safe_delete_paths:
                if file_path.is_symlink():
                    target = file_path.readlink()
                    if not target.is_absolute():
                        target = file_path.parent / target
                    try:
                        from ..config import DIST_DIR
                        target_resolved = target.resolve()
                        dist_resolved = DIST_DIR.resolve()
                        if not str(target_resolved).startswith(str(dist_resolved)):
                            print(f"  {Color.RED}SKIPPED{Color.NC}   {action.file} (unsafe)")
                            continue
                    except (OSError, ValueError):
                        print(f"  {Color.RED}SKIPPED{Color.NC}   {action.file} (unsafe)")
                        continue
                else:
                    print(f"  {Color.RED}SKIPPED{Color.NC}   {action.file} (unsafe)")
                    continue
            
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
        # Invocation is deferred to the caller (commands layer) — services must
        # not reach into the commands/top-level namespace. The caller checks
        # for action.action == "INSTALL" in fix_actions and dispatches install().
        # We flag it here by attaching a marker on the actions list.
        fix_actions.append(FixAction("_TRIGGER_INSTALL", "-", "run install"))
    
    if needs_build:
        print(f"  {Color.CYAN}NOTICE{Color.NC}   Build stale issues detected.")
        print("           Run the build process to regenerate files from source.")
    
    return True

def _check_role_models(state):
    """Display role→model assignments and check compatibility."""
    from ..model_registry import load_model_registry
    from ..cli_backend import load_registry
    from ..role_registry import load_role_registry
    from ..config import Color
    
    model_registry = load_model_registry()
    cli_registry = load_registry()
    role_registry = load_role_registry()
    issues = []
    
    print(f"\n{Color.CYAN}Role→Model Assignments:{Color.NC}\n")
    
    # Global
    if state.global_install:
        print("Global:")
        for cli_name, backend_state in state.global_install.clis.items():
            try:
                backend = cli_registry.get(cli_name)
            except KeyError:
                print(f"  {cli_name} (CLI not found in registry):")
                continue
                
            print(f"  {backend.label}:")
            if not backend_state.role_models:
                print(f"    {Color.YELLOW}(no role assignments){Color.NC}")
            else:
                for role_id, model_id in backend_state.role_models.items():
                    try:
                        role = role_registry.get(role_id)
                        model = model_registry.get(model_id)
                        
                        # Check compatibility: first_alias_for returns (provider, alias) | None
                        resolved = backend.first_alias_for(model.aliases)
                        if resolved is not None:
                            _provider, alias_str = resolved
                            model_display = f"{model.label} (as {alias_str})"
                            print(f"    {role.label} → {model_display}")
                        else:
                            model_display = f"{model.label} (INCOMPATIBLE - {backend.label} doesn't support this provider)"
                            print(f"    {role.label} → {Color.RED}{model_display}{Color.NC}")
                            issues.append(f"Global {backend.label}: {role.label} assigned to incompatible model {model.label}")
                    except KeyError as e:
                        print(f"    {role_id} → {Color.RED}{model_id} (not found: {e}){Color.NC}")
                        issues.append(f"Global {backend.label}: Invalid assignment {role_id} → {model_id}")
            print()
    
    # Local
    for project_path, local_state in state.local_installs.items():
        print(f"Local ({project_path}):")
        for cli_name, backend_state in local_state.clis.items():
            try:
                backend = cli_registry.get(cli_name)
            except KeyError:
                print(f"  {cli_name} (CLI not found in registry):")
                continue
                
            print(f"  {backend.label}:")
            if not backend_state.role_models:
                print(f"    {Color.YELLOW}(no role assignments){Color.NC}")
            else:
                for role_id, model_id in backend_state.role_models.items():
                    try:
                        role = role_registry.get(role_id)
                        model = model_registry.get(model_id)
                        
                        resolved = backend.first_alias_for(model.aliases)
                        if resolved is not None:
                            _provider, alias_str = resolved
                            model_display = f"{model.label} (as {alias_str})"
                            print(f"    {role.label} → {model_display}")
                        else:
                            model_display = f"{model.label} (INCOMPATIBLE - {backend.label} doesn't support this provider)"
                            print(f"    {role.label} → {Color.RED}{model_display}{Color.NC}")
                            issues.append(f"Local {project_path} {backend.label}: {role.label} assigned to incompatible model {model.label}")
                    except KeyError as e:
                        print(f"    {role_id} → {Color.RED}{model_id} (not found: {e}){Color.NC}")
                        issues.append(f"Local {project_path} {backend.label}: Invalid assignment {role_id} → {model_id}")
            print()
    
    if issues:
        print(f"{Color.RED}Issues found:{Color.NC}")
        for issue in issues:
            print(f"  • {issue}")
        print(f"\nRun '{Color.CYAN}agent-notes set role{Color.NC}' to fix assignments.")
    else:
        print(f"{Color.GREEN}All role assignments look good.{Color.NC}")