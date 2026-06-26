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
    SUBFOLDER = "projects"
    CATEGORIES = ["Patterns", "Decisions", "Mistakes", "Context", "Feedback", "Sessions"]
    INDEX_SECTIONS = ["Decisions", "Patterns", "Context", "Mistakes", "Feedback"]
    SESSION_CAP = 5


class Hooks:
    """Hook command strings used in Claude Code settings.json."""
    MEMORY_BRIDGE = "agent-notes hook memory-bridge"
    PRECOMPACT_MEMORY_BRIDGE = "agent-notes hook precompact-memory-bridge"
    COST_REPORT = "agent-notes cost-report"
    GUARD_CREDENTIALS = "agent-notes hook guard-credentials"
    # Matcher scopes the credential guard to Read, Bash, and Grep tool calls only.
    # Edit/Write/WebFetch are intentionally excluded — writing is not a read threat;
    # WebFetch is not path-based. Both are left to the prompt-level prose rule.
    GUARD_CREDENTIALS_MATCHER = "Read|Bash|Grep"
