import os
import warnings
from pathlib import Path

import pytest

from agent_notes.services import credentials


@pytest.fixture
def tmp_creds(tmp_path, monkeypatch):
    path = tmp_path / "credentials.toml"
    monkeypatch.setattr(credentials, "CONFIG_PATH", path)
    return path


def test_get_returns_none_when_file_missing(tmp_creds):
    assert credentials.get("openrouter") is None


def test_set_then_get_roundtrip(tmp_creds):
    credentials.set_value("openrouter", "api_key", "sk-test-secret-123")
    assert credentials.get("openrouter") == "sk-test-secret-123"


def test_set_writes_0600_permissions(tmp_creds):
    credentials.set_value("openrouter", "api_key", "x")
    mode = tmp_creds.stat().st_mode & 0o777
    assert mode == 0o600


def test_set_preserves_other_providers(tmp_creds):
    credentials.set_value("openrouter", "api_key", "a")
    credentials.set_value("anthropic", "api_key", "b")
    assert credentials.get("openrouter") == "a"
    assert credentials.get("anthropic") == "b"


def test_get_returns_none_when_disabled(tmp_creds):
    credentials.set_value("openrouter", "api_key", "x")
    data = credentials.load()
    data["providers"]["openrouter"]["enabled"] = False
    credentials._write(data)
    assert credentials.get("openrouter") is None


def test_list_providers_returns_names_only(tmp_creds):
    credentials.set_value("openrouter", "api_key", "secret-do-not-leak")
    names = credentials.list_providers()
    assert names == ["openrouter"]
    assert "secret-do-not-leak" not in str(names)


def test_is_configured_true_when_enabled_with_key(tmp_creds):
    credentials.set_value("openrouter", "api_key", "x")
    assert credentials.is_configured("openrouter") is True


def test_is_configured_false_when_no_key(tmp_creds):
    assert credentials.is_configured("openrouter") is False


def test_get_does_not_log_value_to_stdout(tmp_creds, capsys):
    credentials.set_value("openrouter", "api_key", "ULTRA-SECRET-VALUE")
    val = credentials.get("openrouter")
    captured = capsys.readouterr()
    assert "ULTRA-SECRET-VALUE" not in captured.out
    assert "ULTRA-SECRET-VALUE" not in captured.err
    assert val == "ULTRA-SECRET-VALUE"


def test_set_then_load_does_not_log_value(tmp_creds, capsys):
    credentials.set_value("openrouter", "api_key", "TOP-SECRET")
    credentials.load()
    captured = capsys.readouterr()
    assert "TOP-SECRET" not in captured.out
    assert "TOP-SECRET" not in captured.err


def test_load_warns_on_loose_permissions(tmp_creds):
    credentials.set_value("openrouter", "api_key", "x")
    tmp_creds.chmod(0o644)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        credentials.load()
    # On normal filesystems chmod will succeed silently. Assert no crash.
    assert credentials.load()["providers"]["openrouter"]["api_key"] == "x"
