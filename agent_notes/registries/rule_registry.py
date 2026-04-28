"""Rule registry for loading and managing rule descriptors."""

from __future__ import annotations
from pathlib import Path
from typing import Optional
from functools import lru_cache

from ..config import RULES_DIR
from ..domain.rule import Rule


class RuleRegistry:
    """Registry of rule descriptors from data/rules/*.md."""
    
    def __init__(self, rules: list[Rule]):
        self._rules = rules
        self._by_name = {r.name: r for r in rules}
    
    def all(self) -> list[Rule]:
        """Return all rules."""
        return self._rules.copy()
    
    def get(self, name: str) -> Rule:
        """Get rule by name. Raises KeyError if unknown."""
        if name not in self._by_name:
            raise KeyError(f"Rule '{name}' not found in registry")
        return self._by_name[name]
    
    def names(self) -> list[str]:
        """Return sorted list of rule names."""
        return sorted(self._by_name.keys())


def _extract_title_from_md(md_path: Path) -> str:
    """Extract first # heading from markdown file, or return filename stem."""
    if not md_path.exists():
        return md_path.stem
    
    try:
        content = md_path.read_text()
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()
        
        # No heading found, use filename
        return md_path.stem
    except Exception:
        # Fallback to filename if we can't read the file
        return md_path.stem


def load_rule_registry(rules_dir: Optional[Path] = None) -> RuleRegistry:
    """Load all rules from data/rules/*.md."""
    if rules_dir is None:
        rules_dir = RULES_DIR
    
    if not rules_dir.exists():
        return RuleRegistry([])
    
    rules = []
    for rule_file in sorted(rules_dir.glob("*.md")):
        title = _extract_title_from_md(rule_file)
        
        rule = Rule(
            name=rule_file.stem,
            path=rule_file,
            title=title
        )
        rules.append(rule)
    
    return RuleRegistry(rules)


@lru_cache(maxsize=1)
def default_rule_registry() -> RuleRegistry:
    """Return the default rule registry, cached."""
    return load_rule_registry()