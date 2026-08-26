"""Application configuration.

A single, validated Settings object, loaded once at the composition root
(the future CLI entry point) and passed down via constructor injection --
never imported as a global singleton reached for deep inside business
logic. This is what keeps configuration trivially mockable in tests: a
fake Settings instance in, no real .env file required.

Values are read from environment variables (or a .env file, for local
development) using pydantic-settings. Field names here intentionally
don't share one common env var prefix -- some (JAAP_ENV, JAAP_LOG_LEVEL,
...) are JAAP-specific, while others (ANTHROPIC_API_KEY, OLLAMA_HOST) use
the naming convention of the tool they configure, since those are the
names a user is likely to already have set in their shell.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class Settings(BaseSettings):
    """Application-wide configuration, loaded once and injected everywhere
    it's needed.

    Attributes:
        environment: Which environment JAAP is running in. Affects nothing
            in this milestone directly, but later milestones (e.g. the
            database layer) may branch on this.
        database_url: SQLAlchemy connection string for the SQLite database.
        log_level: Minimum severity to log, e.g. "INFO" or "DEBUG".
        log_dir: Directory where the JSON log file is written.
        anthropic_api_key: API key for Claude (Phase 3). Optional here
            since it isn't needed until the ClaudeProvider is implemented.
        anthropic_model: Which Claude model ClaudeProvider uses (Milestone 14).
            Defaults to "claude-sonnet-5" -- verified on 2026-08-25 directly
            against Anthropic's own official documentation
            (platform.claude.com/docs, "Model IDs and versioning": models
            from the 4.6 generation onward use a bare, dateless ID like
            "claude-sonnet-5" as the canonical, pinned identifier, not an
            alias), and cross-checked against the installed `anthropic`
            SDK's own `anthropic.types.model.Model` Literal type as a
            second, independent source. Both agreed.

            Model identifiers and deprecation schedules change over time.
            Before changing this default, re-verify against BOTH of:
              1. https://platform.claude.com/docs/en/about-claude/models/overview
              2. https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions
            (also check
            https://platform.claude.com/docs/en/about-claude/models/model-deprecations
            for any deprecation timeline affecting the current default)
            AND confirm the chosen identifier appears in the currently
            installed `anthropic` package's `anthropic.types.model.Model`
            Literal type. Do not trust third-party blogs/aggregator sites
            alone for this -- one was found during this project's own
            verification confidently reporting the wrong API identifier
            for this exact model. Re-run
            `tests/unit/infrastructure/ai/test_claude_provider.py` after
            changing this value (the tests assert the configured model
            string is passed through correctly, not any specific value,
            so they should pass regardless of which model you configure).
        anthropic_max_tokens: Max tokens per Claude response (Milestone 14).
            1024 is a reasonable default for cover-letter/answer-length
            text (Milestone 16/17's actual use); adjust via
            JAAP_ANTHROPIC_MAX_TOKENS if a future use case needs more.
        ollama_host: Base URL for a local Ollama server (Phase 3).
        headless: Whether Playwright launches Chromium headless (Phase 2).
            Defaults to True; set to False locally to watch the browser
            interactively while developing/debugging.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    environment: Literal["development", "testing", "production"] = Field(
        default="development", validation_alias="JAAP_ENV"
    )
    database_url: str = Field(
        default="sqlite:///./data/jaap.db", validation_alias="JAAP_DATABASE_URL"
    )
    log_level: str = Field(default="INFO", validation_alias="JAAP_LOG_LEVEL")
    log_dir: Path = Field(default=Path("logs"), validation_alias="JAAP_LOG_DIR")
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(
        default="claude-sonnet-5", validation_alias="JAAP_ANTHROPIC_MODEL"
    )
    anthropic_max_tokens: int = Field(
        default=1024, validation_alias="JAAP_ANTHROPIC_MAX_TOKENS"
    )
    ollama_host: str = Field(
        default="http://localhost:11434", validation_alias="OLLAMA_HOST"
    )
    headless: bool = Field(default=True, validation_alias="JAAP_HEADLESS")

    @field_validator("log_level")
    @classmethod
    def _normalize_and_validate_log_level(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in _VALID_LOG_LEVELS:
            allowed = ", ".join(sorted(_VALID_LOG_LEVELS))
            raise ValueError(f"log_level must be one of: {allowed} (got '{value}')")
        return normalized
