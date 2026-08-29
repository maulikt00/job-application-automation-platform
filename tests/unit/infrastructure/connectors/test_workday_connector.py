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
from jaap.domain.exceptions import BrowserAutomationError
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
    <input id="legalName" type="text" name="legalName" data-automation-id="legalNameSection_input1">
    <label for="email">Email</label>
    <input id="email" type="email" name="email" data-automation-id="email">
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


# The tests below cover a real-world-validation-found fix (ADR-0031):
# Workday's own careers site revealed that the `/apply`-suffix URL alone
# does not reliably lead to a form -- clicking "Apply" opens an in-page
# modal (never a navigation) offering several paths, and even the most
# neutral one ("Apply Manually") can lead to a mandatory sign-in wall.
# These use a SEPARATE server fixture, since they need `/apply` to also
# serve real content (an Apply button triggering a modal), not the
# direct-form content `workday_server` above provides.


_MODAL_POSTING_HTML = """
<html><body>
  <h1>Software Engineer</h1>
  <button id="apply_btn">Apply</button>
  <div id="modal" style="display:none;">
    <button id="manual_btn">Apply Manually</button>
  </div>
  <div id="form_container"></div>
  <script>
    document.getElementById('apply_btn').addEventListener('click', function () {
      document.getElementById('modal').style.display = 'block';
    });
    document.getElementById('manual_btn').addEventListener('click', function () {
      document.getElementById('form_container').innerHTML =
        '<form><input type="text" id="legalName" data-automation-id="legalNameSection_input1"></form>';
    });
  </script>
</body></html>
"""

_MODAL_TO_LOGIN_HTML = """
<html><body>
  <h1>Software Engineer</h1>
  <button id="apply_btn">Apply</button>
  <div id="modal" style="display:none;">
    <button id="manual_btn">Apply Manually</button>
  </div>
  <script>
    document.getElementById('apply_btn').addEventListener('click', function () {
      document.getElementById('modal').style.display = 'block';
    });
    document.getElementById('manual_btn').addEventListener('click', function () {
      window.location.href = 'login.html';
    });
  </script>
</body></html>
"""

_LOGIN_WALL_HTML = """
<html><body>
  <h2>Sign In</h2>
  <button>Sign in with Google</button>
  <button>Sign in with email</button>
</body></html>
"""


@pytest.fixture
def modal_server(tmp_path: Path):
    """A server where the /apply path does NOT contain a form directly
    -- the real form only appears after clicking "Apply" (opens an
    in-page modal) then "Apply Manually" within it.
    """
    docroot = tmp_path / "modal_docroot"
    posting_dir = docroot / "Acme" / "job" / "posting123"
    apply_dir = posting_dir / "apply"
    apply_dir.mkdir(parents=True)
    (posting_dir / "index.html").write_text(_MODAL_POSTING_HTML)
    (apply_dir / "index.html").write_text(_MODAL_POSTING_HTML)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(docroot), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/Acme/job/posting123/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


@pytest.fixture
def login_wall_server(tmp_path: Path):
    """A server where "Apply Manually" leads to a sign-in wall, not a
    form -- reproducing what Workday's own careers site actually did.
    """
    docroot = tmp_path / "login_docroot"
    posting_dir = docroot / "Acme" / "job" / "posting456"
    apply_dir = posting_dir / "apply"
    apply_dir.mkdir(parents=True)
    (posting_dir / "index.html").write_text(_MODAL_TO_LOGIN_HTML)
    (apply_dir / "index.html").write_text(_MODAL_TO_LOGIN_HTML)
    (apply_dir / "login.html").write_text(_LOGIN_WALL_HTML)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(docroot), **kwargs)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/Acme/job/posting456/"
    finally:
        server.shutdown()
        thread.join(timeout=5)


def test_navigate_falls_back_to_clicking_apply_then_apply_manually(
    settings: Settings, connector: WebsiteConnector, modal_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(modal_server)

        connector.navigate_to_application_form(engine)  # must not raise

        assert engine.evaluate("document.querySelector('#legalName') !== null")


def test_navigate_raises_a_clear_error_when_apply_manually_leads_to_a_sign_in_wall(
    settings: Settings, connector: WebsiteConnector, login_wall_server: str
) -> None:
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(login_wall_server)

        with pytest.raises(ValueError, match="requires creating an account or signing in"):
            connector.navigate_to_application_form(engine)


# The test below covers a real-world-validation-found fix (ADR-0032,
# found while confirming ADR-0031's finding against a second Workday
# tenant): the "Apply Manually" click can raise BrowserAutomationError
# even when it actually succeeds, since it causes an immediate page
# transition Playwright's own click() has trouble reporting cleanly on
# a slower real site. Verified directly against a live site (confirmed:
# the URL had already changed to the expected destination despite the
# raised exception) -- not reproducible deterministically with a fast,
# real Chromium instance and a local test server, so this uses a
# minimal fake engine instead, to verify the exception-handling logic
# itself rather than force an artificial 30-second timeout.


class _FakeEngineRaisingOnManualClick:
    """Simulates exactly one thing: the "Apply Manually" click raises
    BrowserAutomationError, while everything else behaves normally.
    Not a general-purpose fake -- built narrowly for this one test."""

    def __init__(self, field_appears_after_click: bool) -> None:
        self._field_appears_after_click = field_appears_after_click
        self._clicked_manually = False
        self.clicks: list[str] = []

    def evaluate(self, script: str) -> object:
        if "window.location.href" in script:
            return "https://example.com/job/posting"
        if "role=\"combobox\"" in script:
            return self._clicked_manually and self._field_appears_after_click
        if "sign in" in script.lower():
            return self._clicked_manually and not self._field_appears_after_click
        raise AssertionError(f"Unexpected evaluate call: {script!r}")

    def navigate(self, url: str) -> None:
        pass

    def click(self, selector: str) -> None:
        self.clicks.append(selector)
        if selector == "text=Apply Manually":
            self._clicked_manually = True
            raise BrowserAutomationError("Simulated: click succeeded but reporting failed")


def test_navigate_continues_past_a_manual_click_exception_and_finds_the_form() -> None:
    engine = _FakeEngineRaisingOnManualClick(field_appears_after_click=True)
    connector = WorkdayConnector()

    connector.navigate_to_application_form(engine)  # must not raise

    assert engine.clicks == ["text=Apply", "text=Apply Manually"]


def test_navigate_continues_past_a_manual_click_exception_and_still_detects_sign_in_wall() -> None:
    engine = _FakeEngineRaisingOnManualClick(field_appears_after_click=False)
    connector = WorkdayConnector()

    with pytest.raises(ValueError, match="requires creating an account or signing in"):
        connector.navigate_to_application_form(engine)


# The test below covers a real-world-validation-found fix (ADR-0033):
# the original "is a form present" check (any input/combobox anywhere)
# is far too weak against a real corporate site. NVIDIA's own posting
# page had a nav search box, a country selector, and a OneTrust
# cookie-consent widget's own checkboxes -- all genuinely present
# before any Apply interaction -- causing the check to falsely report
# "form found" without ever attempting the Apply flow. This reproduces
# that exact structure (the real field names/ids observed, not
# invented) to confirm the fix correctly rejects it.


def test_field_present_rejects_generic_site_chrome_without_automation_ids(
    settings: Settings, connector: WebsiteConnector, tmp_path
) -> None:
    docroot = tmp_path / "chrome_docroot"
    docroot.mkdir()
    (docroot / "index.html").write_text(
        """
        <html><body>
          <input type="text" id="nav-search" name="q" placeholder="Search">
          <div id="cookie-consent">
            <input type="checkbox" id="ot-group-id-C0002">
            <input type="checkbox" id="ot-group-id-C0003">
          </div>
          <select id="country-selector"><option>United States</option></select>
          <h1>Software Engineer</h1>
        </body></html>
        """
    )
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{docroot / 'index.html'}")

        assert connector._field_present(engine) is False


def test_field_present_recognizes_a_field_with_a_real_automation_id(
    settings: Settings, connector: WebsiteConnector, tmp_path
) -> None:
    docroot = tmp_path / "real_field_docroot"
    docroot.mkdir()
    (docroot / "index.html").write_text(
        '<html><body><input type="text" id="legalName" '
        'data-automation-id="legalNameSection_input1"></body></html>'
    )
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(f"file://{docroot / 'index.html'}")

        assert connector._field_present(engine) is True
