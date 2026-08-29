"""Tests for GreenhouseConnector, against a REAL headless Chromium
instance -- not mocks. Uses real temp HTML files (not inline `data:`
URLs) for anything involving JS event listeners: a `data:` URL with
nested quoting/escaping for inline `onclick` handlers proved fragile
while developing this connector (a raw `#` character in an `href`
attribute was silently truncating page content, since `#` starts a URL
fragment -- a real lesson learned, not a hypothetical one), so a real
file avoids that entire class of problem.
"""

from __future__ import annotations

import pytest

from jaap.application.interfaces.website_connector import WebsiteConnector
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.connectors.greenhouse_connector import GreenhouseConnector

_FORM_ALREADY_PRESENT_HTML = """
<html><body>
  <form>
    <label for="first_name">First Name</label>
    <input id="first_name" type="text" name="first_name">
    <label for="last_name">Last Name</label>
    <input id="last_name" type="text" name="last_name">
    <label for="email">Email</label>
    <input id="email" type="text" name="email">
    <button id="submit_app">Submit Application</button>
  </form>
</body></html>
"""

_DESCRIPTION_ONLY_HTML = """
<html><body>
  <h1>Senior Engineer at Acme</h1>
  <p>Job description here...</p>
  <a href="javascript:void(0)" id="apply_link">Apply for this job</a>
  <div id="form_container"></div>
  <script>
    document.getElementById('apply_link').addEventListener('click', function () {
      document.getElementById('form_container').innerHTML =
        '<form><input type="text" name="first_name"></form>';
    });
  </script>
</body></html>
"""

# Found via real-world validation against a live Greenhouse posting
# (job-boards.greenhouse.io, 2026-08): the application form is on the
# same page from the start (no separate "Apply" click needed at all),
# but does not finish rendering by the time the page's own "load" event
# fires -- a timing issue, not the "description-only, click reveals it"
# structure _DESCRIPTION_ONLY_HTML above models. See ADR-0028.
_DELAYED_RENDER_HTML = """
<html><body>
  <h1>Software Engineer at Acme</h1>
  <div id="form_container"></div>
  <script>
    setTimeout(function () {
      document.getElementById('form_container').innerHTML =
        '<form><input type="text" name="first_name"></form>';
    }, 1500);
  </script>
</body></html>
"""


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None)


@pytest.fixture
def connector() -> WebsiteConnector:
    return GreenhouseConnector()


def _write_html(tmp_path, filename: str, content: str) -> str:
    path = tmp_path / filename
    path.write_text(content)
    return f"file://{path}"


def test_platform_name_matches_job_platform_greenhouse(connector: WebsiteConnector) -> None:
    assert connector.platform_name == JobPlatform.GREENHOUSE


def test_matches_boards_greenhouse_io(connector: WebsiteConnector) -> None:
    assert connector.matches("https://boards.greenhouse.io/acme/jobs/12345") is True


def test_matches_job_boards_greenhouse_io(connector: WebsiteConnector) -> None:
    assert connector.matches("https://job-boards.greenhouse.io/acme/jobs/12345") is True


def test_does_not_match_an_unrelated_url(connector: WebsiteConnector) -> None:
    assert connector.matches("https://example.com/careers/12345") is False


def test_navigate_to_application_form_is_a_no_op_when_form_already_present(
    settings: Settings, connector: WebsiteConnector, tmp_path
) -> None:
    url = _write_html(tmp_path, "form_present.html", _FORM_ALREADY_PRESENT_HTML)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(url)
        connector.navigate_to_application_form(engine)  # must not raise
        assert engine.evaluate('document.querySelector(\'input[name="first_name"]\') !== null')


def test_navigate_to_application_form_clicks_apply_to_reveal_the_form(
    settings: Settings, connector: WebsiteConnector, tmp_path
) -> None:
    url = _write_html(tmp_path, "description_only.html", _DESCRIPTION_ONLY_HTML)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(url)
        assert not engine.evaluate('document.querySelector(\'input[name="first_name"]\') !== null')

        connector.navigate_to_application_form(engine)

        assert engine.evaluate('document.querySelector(\'input[name="first_name"]\') !== null')


def test_get_field_detector_returns_a_playwright_form_field_detector(
    settings: Settings, connector: WebsiteConnector, tmp_path
) -> None:
    url = _write_html(tmp_path, "form_present.html", _FORM_ALREADY_PRESENT_HTML)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(url)
        detector = connector.get_field_detector(engine)
        assert isinstance(detector, PlaywrightFormFieldDetector)


def test_get_field_detector_detects_the_real_greenhouse_style_fields(
    settings: Settings, connector: WebsiteConnector, tmp_path
) -> None:
    url = _write_html(tmp_path, "form_present.html", _FORM_ALREADY_PRESENT_HTML)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(url)
        detector = connector.get_field_detector(engine)

        fields = detector.detect_fields()

        names = {f.name for f in fields}
        assert names == {"first_name", "last_name", "email"}


def test_navigate_to_application_form_waits_for_a_delayed_render(
    settings: Settings, connector: WebsiteConnector, tmp_path
) -> None:
    # A real bug found via live-site validation (ADR-0028): the form is
    # on the same page from the start, with no "Apply" element to click
    # at all, but takes a moment to actually render after the page's own
    # "load" event fires. Checking exactly once, immediately after
    # navigation, previously raised a false "form not found" error here.
    url = _write_html(tmp_path, "delayed_render.html", _DELAYED_RENDER_HTML)
    with PlaywrightBrowserEngine(settings) as engine:
        engine.navigate(url)
        assert not engine.evaluate('document.querySelector(\'input[name="first_name"]\') !== null')

        connector.navigate_to_application_form(engine)  # must not raise

        assert engine.evaluate('document.querySelector(\'input[name="first_name"]\') !== null')
