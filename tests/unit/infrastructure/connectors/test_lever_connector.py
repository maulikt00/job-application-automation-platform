"""Tests for LeverConnector, against a REAL headless Chromium instance
and a REAL local HTTP server (run in a background thread within this
test process, matching the pattern established in
test_review_end_to_end.py) -- not mocks, and not `file://` URLs.

A real HTTP server is required here specifically: LeverConnector's
navigation logic manipulates URL *paths* (`/posting-id` ->
`/posting-id/apply`), which only behaves like real Lever URLs when
directory-style paths resolve the way a real web server resolves them
(serving `index.html` for a directory path). A `file://` URL ending in
`.html` would make `/apply`-appending produce an invalid path
(`index.html/apply`) -- a real trap discovered while developing this
connector, not a hypothetical one; documented in ADR-0022.
"""

from __future__ import annotations

import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from jaap.application.interfaces.website_connector import WebsiteConnector
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.connectors.lever_connector import LeverConnector

_POSTING_HTML = "<html><body><h1>Account Executive at Acme</h1><p>Description...</p></body></html>"
_APPLY_FORM_HTML = """
<html><body>
  <form>
    <label for="name">Full Name</label>
    <input id="name" type="text" name="name">
    <label for="email">Email</label>
    <input id="email" type="email" name="email">
    <input type="file" name="resume">
  </form>
</body></html>
"""


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def connector() -> WebsiteConnector:
    return LeverConnector()


@pytest.fixture
def lever_server(tmp_path: Path):
    """A real local HTTP server serving a Lever-style directory
    structure: a posting page at `/acme/5ac21346/` and its application
    form at `/acme/5ac21346/apply/` -- matching how a real web server
    resolves directory-style URLs to index.html, which a `file://` URL
    ending in `.html` cannot replicate.
    """
    docroot = tmp_path / "docroot"
    posting_dir = docroot / "acme" / "5ac21346"
    apply_dir = posting_dir / "apply"
    apply_dir.mkdir(parents=True)
    (posting_dir / "index.html").write_text(_POSTING_HTML)
    (apply_dir / "index.html").write_text(_APPLY_FORM_HTML)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(docroot), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/acme/5ac21346/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_platform_name_matches_job_platform_lever(connector: WebsiteConnector) -> None:
    assert connector.platform_name == JobPlatform.LEVER


def test_matches_jobs_lever_co(connector: WebsiteConnector) -> None:
    assert connector.matches("https://jobs.lever.co/acme/5ac21346") is True


def test_matches_jobs_eu_lever_co(connector: WebsiteConnector) -> None:
    assert connector.matches("https://jobs.eu.lever.co/acme/5ac21346") is True


def test_does_not_match_an_unrelated_url(connector: WebsiteConnector) -> None:
    assert connector.matches("https://example.com/careers/12345") is False


def test_navigate_to_application_form_moves_to_the_apply_url(
    settings: Settings, connector: WebsiteConnector, lever_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(lever_server)

        connector.navigate_to_application_form(engine)

        current_url = engine.evaluate("window.location.href")
        assert current_url.rstrip("/").endswith("/apply")
        assert engine.evaluate("document.querySelector('input') !== null")


def test_navigate_to_application_form_is_idempotent(
    settings: Settings, connector: WebsiteConnector, lever_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(lever_server)
        connector.navigate_to_application_form(engine)
        first_url = engine.evaluate("window.location.href")

        connector.navigate_to_application_form(engine)  # already there -- must not re-navigate oddly

        assert engine.evaluate("window.location.href") == first_url


def test_get_field_detector_returns_a_playwright_form_field_detector(
    settings: Settings, connector: WebsiteConnector, lever_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(lever_server)
        detector = connector.get_field_detector(engine)
        assert isinstance(detector, PlaywrightFormFieldDetector)


def test_get_field_detector_detects_the_real_lever_style_fields(
    settings: Settings, connector: WebsiteConnector, lever_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(lever_server)
        connector.navigate_to_application_form(engine)
        detector = connector.get_field_detector(engine)

        fields = detector.detect_fields()

        by_name = {f.name: f for f in fields}
        assert by_name["name"].field_type == "text"
        assert by_name["email"].field_type == "email"
        assert by_name["resume"].field_type == "file"
