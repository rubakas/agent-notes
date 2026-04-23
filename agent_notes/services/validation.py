"""Validation helpers used by commands/validate.py."""

import re
from pathlib import Path
from typing import Optional


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