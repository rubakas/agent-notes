"""Display and summary functions for agent-notes diagnostics."""

from pathlib import Path
from typing import List, Dict

from ...domain.diagnostics import Issue


def _cli_base_dir(backend, scope: str) -> Path:
    """Get base directory for a CLI backend."""
    if scope == "global":
        return backend.global_home
    else:
        return Path(backend.local_dir)


def _count_agents(backend, scope: str) -> tuple:
    """Count (installed, expected) agents for a CLI backend."""
    from ... import installer

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
    from ... import installer

    # Helper to get DIST_SKILLS_DIR
    def _get_dist_skills_dir():
        from ...config import DIST_SKILLS_DIR
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
        from ...config import BIN_HOME
        return BIN_HOME

    def _get_dist_scripts_dir():
        from ...config import DIST_SCRIPTS_DIR
        return DIST_SCRIPTS_DIR

    bin_home = _get_bin_home()
    dist_scripts_dir = _get_dist_scripts_dir()

    installed = len([f for f in bin_home.iterdir() if f.is_file() and (dist_scripts_dir / f.name).exists()]) if bin_home and bin_home.exists() else 0
    expected = len([f for f in dist_scripts_dir.iterdir() if f.is_file()]) if dist_scripts_dir and dist_scripts_dir.exists() else 0
    return installed, expected


def _count_rules(backend, scope: str) -> tuple:
    """Count (installed, expected) rules for a CLI backend."""
    from ... import installer

    # Helper to get DIST_RULES_DIR
    def _get_dist_rules_dir():
        from ...config import DIST_RULES_DIR
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
    from ... import installer

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


def _check_role_models(state):
    """Display role→model assignments and check compatibility."""
    from ...model_registry import load_model_registry
    from ...cli_backend import load_registry
    from ...role_registry import load_role_registry
    from ...config import Color

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


def count_stale(issues: List[Issue], item_type: str) -> int:
    """Count stale issues of a specific type."""
    count = 0
    for issue in issues:
        if issue.type == "stale" and item_type in issue.file:
            count += 1
    return count


def _print_status(label: str, installed: int, expected: int):
    """Print OK/WARN status for a component."""
    from ...config import ok, warn
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

    from ...cli_backend import load_registry
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
        from ...config import ok, warn
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
            from ...config import BIN_HOME
            installed, expected = _count_scripts()
            _print_status(f"scripts ({BIN_HOME})", installed, expected)


def print_issues(issues: List[Issue]) -> bool:
    """Print found issues. Returns True if no issues."""
    from ...config import Color

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
