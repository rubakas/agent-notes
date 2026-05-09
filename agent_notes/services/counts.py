"""Shared counting helpers for installed components."""

import os


def count_rules_total() -> int:
    """Count total available rule files (for wizard display).

    Uses the rule registry when available; falls back to counting .md files
    directly from the dist rules directory.
    """
    from ..config import DIST_RULES_DIR

    if os.environ.get('_WIZARD_TEST_MODE'):
        if not DIST_RULES_DIR.exists():
            return 0
        return len(list(DIST_RULES_DIR.glob("*.md")))

    try:
        from ..registries import default_rule_registry
        registry = default_rule_registry()
        return len(registry.all())
    except Exception:
        if not DIST_RULES_DIR.exists():
            return 0
        return len(list(DIST_RULES_DIR.glob("*.md")))


def count_skills(backend, scope: str) -> tuple:
    """Count (installed, expected) skills for a CLI backend. Excludes broken symlinks."""
    from . import installer
    from ..config import DIST_SKILLS_DIR

    if not backend.supports("skills"):
        return 0, 0

    skills_dir = installer.target_dir_for(backend, "skills", scope)
    if skills_dir and skills_dir.exists():
        installed = len([d for d in skills_dir.iterdir() if d.is_dir() and d.exists()])
    else:
        installed = 0

    expected = (
        len([d for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()])
        if DIST_SKILLS_DIR and DIST_SKILLS_DIR.exists()
        else 0
    )
    return installed, expected


def count_rules(backend, scope: str) -> tuple:
    """Count (installed, expected) rules for a CLI backend."""
    from . import installer
    from ..config import DIST_RULES_DIR

    if not backend.supports("rules"):
        return 0, 0

    rules_dir = installer.target_dir_for(backend, "rules", scope)
    installed = len(list(rules_dir.glob("*.md"))) if rules_dir and rules_dir.exists() else 0

    expected = (
        len(list(DIST_RULES_DIR.glob("*.md")))
        if DIST_RULES_DIR and DIST_RULES_DIR.exists()
        else 0
    )
    return installed, expected
