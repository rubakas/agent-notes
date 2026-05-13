"""Tests for _is_credential_file() in agent_notes.services.wiki_backend."""
import pytest
from pathlib import Path

from agent_notes.services.wiki_backend import _is_credential_file


# ── .env variants ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    ".env",
    ".env.production",
    ".env.local",
    ".env.staging",
])
def test_dotenv_variants(filename):
    assert _is_credential_file(Path(filename)) is True


# ── Key / certificate files ───────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "server.key",
    "cert.pem",
    "my.p12",
    "store.pfx",
    "java.jks",
])
def test_key_cert_files(filename):
    assert _is_credential_file(Path(filename)) is True


# ── Keystore / truststore ─────────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "app.keystore",
    "ca.truststore",
])
def test_keystore_truststore(filename):
    assert _is_credential_file(Path(filename)) is True


# ── credentials.* / secrets.* / *-secrets.* ──────────────────────────────────

@pytest.mark.parametrize("filename", [
    "credentials.json",
    "credentials.toml",
    "secrets.yaml",
    "db-secrets.toml",
    "app-secrets.json",
])
def test_credentials_secrets_files(filename):
    assert _is_credential_file(Path(filename)) is True


# ── service-account*.json ─────────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "service-account-prod.json",
    "service-account.json",
])
def test_service_account_files(filename):
    assert _is_credential_file(Path(filename)) is True


# ── *secret*.yaml / yml / json ────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "k8s-secret.yaml",
    "db-secret.yml",
    "app-secret.json",
])
def test_secret_pattern_files(filename):
    assert _is_credential_file(Path(filename)) is True


# ── *apikey* / *api-key* / *api_key* ─────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "my-apikey.txt",
    "api-key.env",
    "api_key.json",
])
def test_apikey_pattern_files(filename):
    assert _is_credential_file(Path(filename)) is True


# ── *private-key* / *private_key* ────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "server-private-key.pem",
    "my_private_key.txt",
])
def test_private_key_files(filename):
    assert _is_credential_file(Path(filename)) is True


# ── Normal code files — must NOT be filtered ─────────────────────────────────

@pytest.mark.parametrize("filename", [
    "auth.py",
    "token_handler.js",
    "secret_service.rb",
    "credentials_manager.py",
    "api_client.go",
])
def test_normal_code_files_not_filtered(filename):
    assert _is_credential_file(Path(filename)) is False


# ── Normal config files — must NOT be filtered ───────────────────────────────

@pytest.mark.parametrize("filename", [
    "config.json",
    "settings.yaml",
    "pyproject.toml",
    "package.json",
])
def test_normal_config_files_not_filtered(filename):
    assert _is_credential_file(Path(filename)) is False


# ── Case insensitivity ────────────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    ".ENV",
    "Credentials.JSON",
    "SECRETS.yaml",
    "Server.KEY",
])
def test_case_insensitive(filename):
    assert _is_credential_file(Path(filename)) is True
