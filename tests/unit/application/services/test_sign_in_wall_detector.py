"""Tests for the shared sign-in-wall detector (ADR-0040)."""

from __future__ import annotations

from jaap.application.services.sign_in_wall_detector import looks_like_sign_in_wall
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings


def test_detects_a_real_sign_in_page(tmp_path) -> None:
    form = tmp_path / "signin.html"
    form.write_text(
        '<html><body><h2>Sign In</h2>'
        '<button>Sign in with Google</button></body></html>',
        encoding="utf-8",
    )
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")

        assert looks_like_sign_in_wall(engine) is True


def test_does_not_flag_an_ordinary_application_form(tmp_path) -> None:
    form = tmp_path / "form.html"
    form.write_text(
        '<html><body><form><input type="text" name="first_name"></form></body></html>',
        encoding="utf-8",
    )
    settings = Settings(_env_file=None)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{form}")

        assert looks_like_sign_in_wall(engine) is False
