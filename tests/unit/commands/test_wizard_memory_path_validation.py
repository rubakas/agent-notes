import agent_notes.commands.wizard as wiz


def test_validate_vault_path_accepts_real_vault(tmp_path):
    (tmp_path / ".obsidian").mkdir()
    ok, reason = wiz._validate_vault_path(str(tmp_path))
    assert ok is True
    assert reason == ""


def test_validate_vault_path_flags_missing_dir(tmp_path):
    ok, reason = wiz._validate_vault_path(str(tmp_path / "does-not-exist"))
    assert ok is False
    assert "exist" in reason.lower()


def test_validate_vault_path_flags_non_vault(tmp_path):
    # exists but has no .obsidian/
    ok, reason = wiz._validate_vault_path(str(tmp_path))
    assert ok is False
    assert "obsidian" in reason.lower() or "vault" in reason.lower()
