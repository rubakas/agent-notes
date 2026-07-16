"""Build agent configuration files from source."""

import yaml
import shutil
from pathlib import Path

from ..config import (
    AGENTS_YAML,
    DIST_DIR,
    info
)
from ..services.rendering import generate_agent_files, render_globals, load_agents_config


# Re-export for backward compatibility
def _load_frontmatter_template(template_name):
    """DEPRECATED: Use services.rendering._load_frontmatter_template instead."""
    from ..services.rendering import _load_frontmatter_template
    return _load_frontmatter_template(template_name)
def copy_global_files() -> list[Path]:
    """Copy global files and rules to destination."""
    from ..config import RULES_DIR, DIST_RULES_DIR
    
    copied_files = []
    
    # Use the rendering service for global files
    copied_files.extend(render_globals())
    
    # Copy all rules files
    if RULES_DIR.exists():
        # Build rule files
        DIST_RULES_DIR.mkdir(parents=True, exist_ok=True)
        for rule_file in RULES_DIR.glob('*.md'):
            dest_file = DIST_RULES_DIR / rule_file.name
            shutil.copy2(rule_file, dest_file)
            copied_files.append(dest_file)
    
    return copied_files


def copy_skills() -> list[Path]:
    """Copy skill directories to dist/skills/."""
    from ..config import find_skill_dirs
    
    dist_skills = DIST_DIR / "skills"
    # Clean and recreate
    if dist_skills.exists():
        shutil.rmtree(dist_skills)
    dist_skills.mkdir(parents=True, exist_ok=True)
    
    copied = []
    for skill_dir in find_skill_dirs():
        dest = dist_skills / skill_dir.name
        shutil.copytree(skill_dir, dest)
        copied.append(dest)
    return copied



def copy_commands() -> list[Path]:
    """Copy command files from data/commands/ to dist/claude/commands/."""
    from ..config import DATA_DIR, DIST_DIR
    src = DATA_DIR / "commands"
    if not src.exists():
        return []
    dest = DIST_DIR / "claude" / "commands"
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    copied = []
    for f in src.glob("*.md"):
        out = dest / f.name
        shutil.copy2(f, out)
        copied.append(out)
    return copied


def count_lines(file_path: Path) -> int:
    """Count lines in a file or all files within a directory."""
    try:
        if file_path.is_dir():
            return sum(
                len(f.read_text().splitlines())
                for f in file_path.rglob("*")
                if f.is_file()
            )
        return len(file_path.read_text().splitlines())
    except Exception:
        return 0


def count_dist_clis(files: list[Path], dist_dir: Path, cli_names: set[str]) -> int:
    """Count distinct CLI backends among generated files (dist/<cli>/... paths).

    Files outside dist_dir or under non-CLI top-level dirs (rules/, skills/)
    are ignored."""
    found = set()
    for f in files:
        try:
            rel = f.relative_to(dist_dir)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in cli_names:
            found.add(rel.parts[0])
    return len(found)


def format_build_summary(n_files: int, n_lines: int, n_clis: int) -> str:
    """One-line build summary, e.g. 'Generated 96 files (13,748 lines) across 4 CLIs'."""
    file_word = "file" if n_files == 1 else "files"
    cli_word = "CLI" if n_clis == 1 else "CLIs"
    return f"Generated {n_files} {file_word} ({n_lines:,} lines) across {n_clis} {cli_word}"


def build(role_models=None, role_efforts=None, scope='global', project_path=None,
          profile_label: str = "") -> None:
    """Build agent configuration files from source.

    Args:
        role_models: Optional explicit {cli: {role: model_id}} pins that override
            persisted state (e.g. wizard selections not yet written to state.json)
        role_efforts: Optional explicit {cli: {role: effort}} pins, same semantics
        scope: which state.json scope's pins drive the render ('global' or 'local')
        project_path: project path for scope='local'
        profile_label: named profile whose pins drive the render ("" = default profile)
    """
    from ..services.state_store import load_state
    from ..registries.cli_registry import load_registry

    # Read configuration
    try:
        agents_config, tiers = load_agents_config()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return

    # Load state if present (no error if missing)
    state = load_state()

    # Generate agent files (state=None is backward compatible)
    print("Generating agent files...")
    agent_files = generate_agent_files(agents_config, tiers, state=state,
                                       scope=scope, project_path=project_path,
                                       role_models=role_models, role_efforts=role_efforts,
                                       profile_label=profile_label)
    
    # Copy global files
    print("Copying global files...")
    global_files = copy_global_files()
    
    # Copy skills
    print("Copying skills...")
    skill_files = copy_skills()

    # Copy commands
    print("Copying commands...")
    command_files = copy_commands()

    # Report results — one-line summary (per-file listing was too noisy)
    all_files = agent_files + global_files + skill_files + command_files
    total_lines = sum(count_lines(f) for f in all_files)
    cli_names = {b.name for b in load_registry().all()}
    n_clis = count_dist_clis(all_files, DIST_DIR, cli_names)
    print(f"\n{format_build_summary(len(all_files), total_lines, n_clis)}")


if __name__ == '__main__':
    build()