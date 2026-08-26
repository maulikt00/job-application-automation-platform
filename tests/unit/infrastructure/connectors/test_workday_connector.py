"""Tests for WorkdayConnector and WorkdayFormFieldDetector, against a
REAL headless Chromium instance and a REAL local HTTP server (same
pattern as test_lever_connector.py -- Workday's own `/apply`-suffix
URL pattern needs directory-style URL resolution a `file://` URL
cannot replicate).
"""

from __future__ import annotations

import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from jaap.application.interfaces.website_connector import WebsiteConnector
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.connectors.workday_connector import WorkdayConnector
from jaap.infrastructure.connectors.workday_form_field_detector import (
    WorkdayFormFieldDetector,
)

_POSTING_HTML = "<html><body><h1>Software Engineer at Acme</h1><p>Description...</p></body></html>"
_APPLY_FORM_HTML = """
<html><body>
  <form>
    <label for="legalName">Legal Name</label>
    <input id="legalName" type="text" name="legalName">
    <label for="email">Email</label>
    <input id="email" type="email" name="email">
    <div id="countryLabel">Country</div>
    <div role="combobox" aria-labelledby="countryLabel" aria-required="true"
         data-automation-id="countryDropdown">United States</div>
  </form>
</body></html>
"""


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def connector() -> WebsiteConnector:
    return WorkdayConnector()


@pytest.fixture
def workday_server(tmp_path: Path):
    """A real local HTTP server serving a Workday-style directory
    structure: a posting page and its `/apply` application form,
    matching the pattern established in test_lever_connector.py.
    """
    docroot = tmp_path / "docroot"
    posting_dir = docroot / "Acme" / "job" / "USA-CA" / "Engineer_JR-001"
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
        yield f"http://127.0.0.1:{server.server_port}/Acme/job/USA-CA/Engineer_JR-001/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_platform_name_matches_job_platform_workday(connector: WebsiteConnector) -> None:
    assert connector.platform_name == JobPlatform.WORKDAY


def test_matches_myworkdayjobs_domain(connector: WebsiteConnector) -> None:
    assert connector.matches("https://acme.wd5.myworkdayjobs.com/Acme/job/123") is True


def test_matches_different_data_center_numbers(connector: WebsiteConnector) -> None:
    # Confirmed real finding: the wd{N} data-center number varies per
    # company -- must not hardcode a specific one.
    assert connector.matches("https://acme.wd1.myworkdayjobs.com/Acme/job/123") is True
    assert connector.matches("https://acme.wd3.myworkdayjobs.com/Acme/job/123") is True


def test_matches_myworkdaysite_domain(connector: WebsiteConnector) -> None:
    assert connector.matches("https://acme.myworkdaysite.com/recruiting/acme/site") is True


def test_does_not_match_an_unrelated_url(connector: WebsiteConnector) -> None:
    assert connector.matches("https://example.com/careers/12345") is False


def test_navigate_to_application_form_moves_to_the_apply_url(
    settings: Settings, connector: WebsiteConnector, workday_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(workday_server)

        connector.navigate_to_application_form(engine)

        current_url = engine.evaluate("window.location.href")
        assert current_url.rstrip("/").endswith("/apply")


def test_get_field_detector_returns_a_workday_form_field_detector(
    settings: Settings, connector: WebsiteConnector, workday_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(workday_server)
        detector = connector.get_field_detector(engine)
        assert isinstance(detector, WorkdayFormFieldDetector)


def test_get_field_detector_detects_native_fields_and_the_combobox(
    settings: Settings, connector: WebsiteConnector, workday_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(workday_server)
        connector.navigate_to_application_form(engine)
        detector = connector.get_field_detector(engine)

        fields = detector.detect_fields()

        by_name = {f.name: f for f in fields}
        assert by_name["legalName"].field_type == "text"
        assert by_name["legalName"].selector == "#legalName"
        assert by_name["email"].field_type == "email"
        assert by_name["countryDropdown"].field_type == "combobox"


def test_combobox_field_always_has_no_selector(
    settings: Settings, connector: WebsiteConnector, workday_server: str
) -> None:
    # The core safety property this milestone's design depends on: a
    # detected combobox must never be automatically fillable.
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(workday_server)
        connector.navigate_to_application_form(engine)
        detector = connector.get_field_detector(engine)

        fields = detector.detect_fields()

        combobox = next(f for f in fields if f.field_type == "combobox")
        assert combobox.selector is None


def test_combobox_label_resolves_via_aria_labelledby(
    settings: Settings, connector: WebsiteConnector, workday_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(workday_server)
        connector.navigate_to_application_form(engine)
        detector = connector.get_field_detector(engine)

        fields = detector.detect_fields()

        combobox = next(f for f in fields if f.field_type == "combobox")
        assert combobox.label == "Country"


def test_combobox_required_reflects_aria_required(
    settings: Settings, connector: WebsiteConnector, workday_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(workday_server)
        connector.navigate_to_application_form(engine)
        detector = connector.get_field_detector(engine)

        fields = detector.detect_fields()

        combobox = next(f for f in fields if f.field_type == "combobox")
        assert combobox.required is True
