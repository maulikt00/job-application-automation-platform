"""Tests for the Settings configuration object.

Uses monkeypatch.setenv rather than a real .env file, and passes
_env_file=None to the constructor, so these tests are deterministic and
unaffected by whatever .env file (if any) happens to exist on disk.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from jaap.infrastructure.config.settings import Settings


def test_defaults_when_no_env_vars_are_set(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "JAAP_ENV",
        "JAAP_DATABASE_URL",
        "JAAP_LOG_LEVEL",
        "JAAP_LOG_DIR",
        "ANTHROPIC_API_KEY",
        "OLLAMA_HOST",
    ):
        monkeypatch.delenv(var, raising=False)

    settings = Settings(_env_file=None)

    assert settings.environment == "development"
    assert settings.database_url == "sqlite:///./data/jaap.db"
    assert settings.log_level == "INFO"
    assert settings.log_dir == Path("logs")
    assert settings.anthropic_api_key is None
    assert settings.ollama_host == "http://localhost:11434"


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAAP_ENV", "production")
    monkeypatch.setenv("JAAP_DATABASE_URL", "sqlite:///./data/custom.db")
    monkeypatch.setenv("JAAP_LOG_LEVEL", "debug")
    monkeypatch.setenv("JAAP_LOG_DIR", "/tmp/jaap-logs")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("OLLAMA_HOST", "http://ollama.internal:11434")

    settings = Settings(_env_file=None)

    assert settings.environment == "production"
    assert settings.database_url == "sqlite:///./data/custom.db"
    assert settings.log_level == "DEBUG"
    assert settings.log_dir == Path("/tmp/jaap-logs")
    assert settings.anthropic_api_key == "sk-test-123"
    assert settings.ollama_host == "http://ollama.internal:11434"


def test_invalid_environment_value_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAAP_ENV", "staging")  # not one of the allowed literals

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_log_level_is_normalized_to_uppercase(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAAP_LOG_LEVEL", "warning")

    settings = Settings(_env_file=None)

    assert settings.log_level == "WARNING"


def test_invalid_log_level_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JAAP_LOG_LEVEL", "VERBOSE")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_can_be_constructed_directly_with_python_attribute_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Every field also has an env-var validation_alias (e.g. JAAP_LOG_LEVEL).
    # populate_by_name=True ensures direct keyword construction using the
    # plain attribute name (as any test fixture or future script would
    # naturally do) still works, rather than being silently dropped by
    # extra="ignore".
    monkeypatch.delenv("JAAP_LOG_LEVEL", raising=False)

    settings = Settings(_env_file=None, log_level="WARNING")

    assert settings.log_level == "WARNING"
