import pytest
from agent_notes.memory import memory_backend as mb


class _WipBackend(mb.MemoryBackend):
    stability = "wip"
    def init(self, path): ...
    def regenerate_index(self, path): ...


def test_get_backend_guards_wip(monkeypatch):
    monkeypatch.setitem(mb._REGISTRY, "wipmem", _WipBackend())
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    with pytest.raises(ValueError):
        mb.get_backend("wipmem")
    monkeypatch.setenv("AGENT_NOTES_ENABLE_WIP", "wipmem")
    assert isinstance(mb.get_backend("wipmem"), _WipBackend)


def test_available_backends_excludes_wip_and_removed(monkeypatch):
    monkeypatch.setitem(mb._REGISTRY, "wipmem", _WipBackend())
    monkeypatch.delenv("AGENT_NOTES_ENABLE_WIP", raising=False)
    names = set(mb.available_backends())
    assert "local" in names and "obsidian" in names
    assert "wipmem" not in names and "wiki" not in names
