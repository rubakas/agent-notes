"""Skill registry for loading and managing skill descriptors."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Dict, List
from functools import lru_cache
import re

from ..config import SKILLS_DIR
from ..domain.skill import Skill


class SkillRegistry:
    """Registry of skill descriptors from data/skills/*/SKILL.md."""
    
    def __init__(self, skills: list[Skill]):
        self._skills = skills
        self._by_name = {s.name: s for s in skills}
    
    def all(self) -> list[Skill]:
        """Return all skills."""
        return self._skills.copy()
    
    def get(self, name: str) -> Skill:
        """Get skill by name. Raises KeyError if unknown."""
        if name not in self._by_name:
            raise KeyError(f"Skill '{name}' not found in registry")
        return self._by_name[name]
    
    def names(self) -> list[str]:
        """Return sorted list of skill names."""
        return sorted(self._by_name.keys())
    
    def by_group(self) -> Dict[str, List[Skill]]:
        """Return skills grouped by their group field."""
        groups: Dict[str, List[Skill]] = {}
        for skill in self._skills:
            group_name = skill.group or "uncategorized"
            if group_name not in groups:
                groups[group_name] = []
            groups[group_name].append(skill)
        
        # Sort skills within each group
        for skills_in_group in groups.values():
            skills_in_group.sort(key=lambda s: s.name)
        
        return groups


def _parse_skill_frontmatter(skill_md_path: Path) -> tuple[str, Optional[str]]:
    """Parse SKILL.md frontmatter for description and group.
    
    Returns:
        (description, group) where description is first line if no frontmatter,
        and group is None if not specified.
    """
    if not skill_md_path.exists():
        return skill_md_path.parent.name, None
    
    content = skill_md_path.read_text()
    lines = content.split('\n')
    
    # Check for YAML frontmatter
    if lines and lines[0].strip() == '---':
        # Find the closing ---
        end_idx = None
        for i in range(1, len(lines)):
            if lines[i].strip() == '---':
                end_idx = i
                break
        
        if end_idx is not None:
            # Parse the YAML frontmatter
            frontmatter_lines = lines[1:end_idx]
            group = None
            description = None
            
            for line in frontmatter_lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip().strip('"\'')
                    if key == 'group':
                        group = value
                    elif key == 'description':
                        description = value
            
            # If no description in frontmatter, use first non-empty line after frontmatter
            if not description:
                for line in lines[end_idx + 1:]:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        description = line
                        break
            
            return description or skill_md_path.parent.name, group
    
    # No frontmatter - use first non-empty line as description
    for line in lines:
        line = line.strip()
        if line:
            return line, None
    
    # Fallback to directory name
    return skill_md_path.parent.name, None


def load_skill_registry(skills_dir: Optional[Path] = None) -> SkillRegistry:
    """Load all skills from data/skills/*/SKILL.md."""
    if skills_dir is None:
        skills_dir = SKILLS_DIR
    
    if not skills_dir.exists():
        return SkillRegistry([])
    
    skills = []
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue
        
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        
        description, group = _parse_skill_frontmatter(skill_md)
        
        skill = Skill(
            name=skill_dir.name,
            path=skill_dir,
            description=description,
            group=group
        )
        skills.append(skill)
    
    return SkillRegistry(skills)


@lru_cache(maxsize=1)
def default_skill_registry() -> SkillRegistry:
    """Return the default skill registry, cached."""
    return load_skill_registry()