"""Centralized path and folder name constants for agent-notes."""


# Global defaults (shared across backends)
DEFAULT_VAULT_DIR = "Obsidian"
DEFAULT_VAULT_NAME = "agent-notes"


class Wiki:
    """Wiki backend folder structure constants."""
    DIR = "wiki"
    RAW_DIR = "raw"
    INDEX = "index.md"
    LOG = "log.md"
    SUBFOLDER = "knowledge"
    IGNORE_FILE = ".obsidianignore"
    PAGE_TYPES = ["sources", "concepts", "entities", "synthesis", "sessions"]


class Obsidian:
    """Obsidian backend folder structure constants."""
    INDEX = "Index.md"
    SUBFOLDER = "notes"
    CATEGORIES = ["Patterns", "Decisions", "Mistakes", "Context", "Sessions"]
