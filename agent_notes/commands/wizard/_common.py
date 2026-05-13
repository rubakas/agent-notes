"""Shared helpers, constants, and UI imports for the install wizard."""

import os
from pathlib import Path
from typing import Dict, List

from ...config import (
    Color, DIST_SKILLS_DIR,
)
from ...services.counts import count_rules_total as _count_rules_total

_ROLE_ANSI = {
    'purple': "\033[0;35m",
    'red':    "\033[0;31m",
    'cyan':   "\033[0;36m",
    'blue':   "\033[0;34m",
    'green':  "\033[0;32m",
    'yellow': "\033[0;33m",
    'orange': "\033[0;33m",
}


def _get_skill_groups() -> Dict[str, List[str]]:
    """Get skill names grouped by technology."""
    if os.environ.get('_WIZARD_TEST_MODE'):
        if not DIST_SKILLS_DIR.exists():
            return {}
        all_skills = [d.name for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()]
    else:
        try:
            from ...registries import default_skill_registry
            registry = default_skill_registry()

            if hasattr(registry, 'by_group'):
                groups = registry.by_group()
                real_groups = {
                    gn: [s.name for s in skills]
                    for gn, skills in groups.items()
                    if gn != "uncategorized" and skills
                }
                if real_groups:
                    return real_groups
                all_skills = [s.name for s in registry.all()]
            else:
                all_skills = [skill.name for skill in registry.all()]
        except Exception:
            if not DIST_SKILLS_DIR.exists():
                return {}
            all_skills = [d.name for d in DIST_SKILLS_DIR.iterdir() if d.is_dir()]

    groups = {
        "Rails": [s for s in all_skills if s.startswith("rails-") and s != "rails-kamal"],
        "Docker": [s for s in all_skills if s.startswith("docker-")],
        "Kamal": [s for s in all_skills if s == "rails-kamal"],
        "Git": [s for s in all_skills if s == "git"]
    }

    return {k: v for k, v in groups.items() if v}


def _count_rules() -> int:
    """Count rule files."""
    return _count_rules_total()
