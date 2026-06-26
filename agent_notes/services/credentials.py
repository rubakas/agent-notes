"""Credentials store. Read API for provider API keys.

CRITICAL: This module's `get()` function MUST NOT log, print, or expose values
in exception messages. Treat every value as a secret. Tests verify this.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

try:
    import tomllib  # 3.11+
except ImportError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ImportError as exc:
        raise ImportError(
            "tomli is required on Python < 3.11. Install it: pip install tomli"
        ) from exc

CONFIG_PATH = Path.home() / ".agent-notes" / "credentials.toml"
SAFE_MODE = 0o600


def _ensure_dir() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)


def _ensure_perms() -> None:
    """Ensure 0600 on the file. Warn (not fail) if loose; never raise."""
    if not CONFIG_PATH.exists():
        return
    current = CONFIG_PATH.stat().st_mode & 0o777
    if current != SAFE_MODE:
        try:
            CONFIG_PATH.chmod(SAFE_MODE)
        except OSError:
            import warnings
            warnings.warn(
                f"Credentials file at {CONFIG_PATH} has loose permissions "
                f"(0o{current:o}); could not tighten to 0o600. Fix manually."
            )


def load() -> dict:
    """Load the full credentials TOML. Returns {} if missing.

    Returned dict structure:
      {"providers": {"<name>": {"api_key": str, "base_url": str?, "enabled": bool}}}
    """
    _ensure_dir()
    _ensure_perms()
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("rb") as fh:
        return tomllib.load(fh)


def get(provider: str, key: str = "api_key") -> Optional[str]:
    """Return a credential value. Returns None if not configured.

    DO NOT LOG OR PRINT THE RETURN VALUE. The caller is responsible for
    treating it as opaque. Errors raised from this function MUST NOT
    contain the value.
    """
    data = load()
    provider_block = data.get("providers", {}).get(provider, {})
    if not provider_block.get("enabled", True):
        return None
    return provider_block.get(key)


def set_value(provider: str, key: str, value: str) -> None:
    """Write a credential. Tightens permissions to 0600 on write.

    Existing values for other providers are preserved.
    """
    _ensure_dir()
    data = load()
    data.setdefault("providers", {}).setdefault(provider, {})
    data["providers"][provider][key] = value
    data["providers"][provider].setdefault("enabled", True)
    _write(data)


def _write(data: dict) -> None:
    """Atomic write. Sets 0600 immediately."""
    _ensure_dir()
    fd, tmp_path = tempfile.mkstemp(
        prefix=".credentials-", suffix=".tmp", dir=str(CONFIG_PATH.parent)
    )
    tmp_pathobj = Path(tmp_path)
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(_dump_toml(data))
        tmp_pathobj.chmod(SAFE_MODE)
        tmp_pathobj.replace(CONFIG_PATH)
    finally:
        if tmp_pathobj.exists():
            tmp_pathobj.unlink()


def _dump_toml(data: dict) -> str:
    """Serialize credentials dict to TOML using tomli_w.

    None values are filtered out before serialization — TOML has no null type.
    The hand-rolled predecessor would have written Python's ``None`` repr, which
    is not valid TOML and would fail on read-back anyway.
    """
    import tomli_w  # lazy import — only needed when writing credentials

    providers = data.get("providers", {})
    clean: dict = {"providers": {}}
    for name, block in providers.items():
        clean["providers"][name] = {k: v for k, v in block.items() if v is not None}
    return tomli_w.dumps(clean)


def list_providers() -> list:
    """Names only — never include the values."""
    return sorted(load().get("providers", {}).keys())


def is_configured(provider: str) -> bool:
    """True iff the provider has an api_key set and is enabled. Does not return the value."""
    data = load()
    block = data.get("providers", {}).get(provider, {})
    return bool(block.get("api_key")) and block.get("enabled", True)
