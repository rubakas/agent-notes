"""Unit tests for agent_notes.memory.instructions._memory_instructions."""
import pytest
from unittest.mock import MagicMock

from agent_notes.memory.instructions import _memory_instructions


def _make_state(backend: str, path: str = "/vault", strategy: str = "single-brain"):
    """Build a minimal fake state object."""
    st = MagicMock()
    st.memory.backend = backend
    st.memory.path = path
    st.memory.strategy = strategy
    return st


class TestMemoryInstructionsObsidian:
    def test_obsidian_contains_full_protocol_marker(self, tmp_path):
        """Obsidian branch returns the full memory protocol including its distinctive opener."""
        vault = tmp_path / "vault"
        vault.mkdir()
        st = _make_state("obsidian", str(vault))

        result = _memory_instructions(st)

        assert "session memory note is the durable" in result

    def test_obsidian_contains_protocol_heading(self, tmp_path):
        """Obsidian branch returns the ## Memory protocol (HARD RULE) heading."""
        vault = tmp_path / "vault"
        vault.mkdir()
        st = _make_state("obsidian", str(vault))

        result = _memory_instructions(st)

        assert "## Memory protocol (HARD RULE)" in result

    def test_obsidian_contains_persist_agent_discoveries(self, tmp_path):
        """Obsidian branch includes the Persist agent discoveries section."""
        vault = tmp_path / "vault"
        vault.mkdir()
        st = _make_state("obsidian", str(vault))

        result = _memory_instructions(st)

        assert "Persist agent discoveries" in result

    def test_obsidian_contains_memory_add_command(self, tmp_path):
        """Obsidian branch references the agent-notes memory add CLI command."""
        vault = tmp_path / "vault"
        vault.mkdir()
        st = _make_state("obsidian", str(vault))

        result = _memory_instructions(st)

        assert "agent-notes memory add" in result

    def test_obsidian_contains_vault_path(self, tmp_path):
        """Obsidian branch embeds the resolved vault path."""
        vault = tmp_path / "my-vault"
        vault.mkdir()
        st = _make_state("obsidian", str(vault))

        result = _memory_instructions(st)

        assert str(vault) in result


class TestMemoryInstructionsLocal:
    def test_local_returns_step_aside_text(self):
        """Local branch returns the step-aside text, not the obsidian protocol."""
        st = _make_state("local")

        result = _memory_instructions(st)

        assert "does not manage local memory" in result

    def test_local_has_no_memory_add_command(self):
        """Local branch does not reference agent-notes memory add."""
        st = _make_state("local")

        result = _memory_instructions(st)

        assert "agent-notes memory add" not in result

    def test_local_does_not_contain_full_protocol(self):
        """Local branch does not contain the obsidian-only protocol content."""
        st = _make_state("local")

        result = _memory_instructions(st)

        assert "session memory note is the durable" not in result


class TestMemoryInstructionsNoneState:
    def test_none_state_returns_fallback(self):
        """None state returns a fallback with the memory add CLI reference."""
        result = _memory_instructions(None)

        assert "agent-notes memory add" in result
