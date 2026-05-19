"""v2.24.0: Derive description from note body for all existing notes."""
from __future__ import annotations
from pathlib import Path

from .base import Migration
from ...constants import Obsidian
from .._memory_utils import _parse_frontmatter, _yaml_safe


class AddDescriptionsMigration(Migration):
    name = "v2.24.0-add-descriptions"
    version = "2.24.0"
    description = "Add description field to all existing notes"

    def run(self, vault: Path) -> str:
        updated = 0
        skipped = 0
        for cat in Obsidian.CATEGORIES:
            folder = vault / cat
            if not folder.exists():
                continue
            for note in sorted(folder.glob("*.md")):
                text = note.read_text()
                fm, body = _parse_frontmatter(text)
                if fm.get("description"):
                    skipped += 1
                    continue
                desc = self._derive_description(fm, body)
                if desc:
                    new_text = self._inject_description(text, desc)
                    note.write_text(new_text)
                    updated += 1
                else:
                    skipped += 1
        from ..obsidian_backend import obsidian_regenerate_index
        obsidian_regenerate_index(vault)
        return f"{updated} notes updated, {skipped} skipped"

    def _derive_description(self, fm: dict, body: str) -> str:
        """Derive description from first non-heading body line."""
        first_line = ""
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                continue
            first_line = stripped
            break
        if not first_line:
            return ""
        if len(first_line) <= 100:
            return first_line
        truncated = first_line[:100].rsplit(" ", 1)[0]
        return truncated if truncated else first_line[:100]

    def _inject_description(self, text: str, description: str) -> str:
        """Insert description: line into existing frontmatter after type: line."""
        description = description.replace("\n", " ").replace("\r", "")
        if not text.startswith("---"):
            return text
        end = text.find("\n---", 3)
        if end == -1:
            return text
        fm_block = text[3:end]
        lines = fm_block.split("\n")
        new_lines = []
        inserted = False
        for line in lines:
            new_lines.append(line)
            if line.strip().startswith("type:") and not inserted:
                new_lines.append(f"description: {_yaml_safe(description)}")
                inserted = True
        if not inserted:
            new_lines.append(f"description: {_yaml_safe(description)}")
        return "---" + "\n".join(new_lines) + "\n---" + text[end + 4:]
