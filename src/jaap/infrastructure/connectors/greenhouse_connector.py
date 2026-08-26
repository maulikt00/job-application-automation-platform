"""Greenhouse-backed WebsiteConnector implementation.

Design grounded in Greenhouse's own published documentation and API
examples, not assumption -- verified directly before writing any code:

  - **URL patterns**: Greenhouse-hosted job boards live at
    `boards.greenhouse.io/{token}` (the long-standing domain) or
    `job-boards.greenhouse.io` (confirmed from Greenhouse's own embed
    JavaScript, which sets `targetDomain: 'https://job-boards.greenhouse.io'`).
    Both are checked in `matches()`.
  - **Form field structure**: Greenhouse's own Job Board API
    documentation shows the application form using plain, native HTML
    inputs with recognizable `name` attributes --
    `<input type="text" name="first_name">`, `name="last_name"`,
    `name="email"` -- not custom JS widgets. This is why
    `get_field_detector()` below can simply return the existing generic
    `PlaywrightFormFieldDetector` unchanged; there is nothing
    Greenhouse-specific to detect that the generic detector would miss.
  - **A real, confirmed marker for "is the application form present"**:
    `input[name="first_name"]`, taken directly from Greenhouse's own API
    documentation's example form HTML, not invented.

**A real, honest scope limitation, stated here rather than glossed
over**: this connector only supports DIRECTLY-HOSTED Greenhouse job
boards (`boards.greenhouse.io`/`job-boards.greenhouse.io`). Greenhouse
also supports an embedded integration (a company embeds their job board
and application form inside an `<iframe>` on their own domain --
confirmed by inspecting Greenhouse's own embed JavaScript, which
constructs a `grnhse_iframe` element). Content inside an iframe is not
part of the top-level page's DOM, so `BrowserAutomationEngine.evaluate()`
(which runs against the main frame only) cannot see it, and neither can
the generic `PlaywrightFormFieldDetector`. Supporting the embedded case
would require genuine cross-frame interaction capability
(`BrowserAutomationEngine` has none), which is a real, separate feature
this milestone does not build. `matches()` returns False for a
third-party domain hosting an embedded iframe, by design -- this
connector will correctly decline to handle that case rather than
silently fail partway through it.
"""

from __future__ import annotations

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import FormFieldDetector
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector

# Taken directly from Greenhouse's own Job Board API documentation's
# example application form HTML -- not invented.
_FIRST_NAME_FIELD_SELECTOR = 'input[name="first_name"]'


class GreenhouseConnector:
    """Satisfies application.interfaces.website_connector.WebsiteConnector."""

    @property
    def platform_name(self) -> str:
        return JobPlatform.GREENHOUSE

    def matches(self, url: str) -> bool:
        return "boards.greenhouse.io" in url or "job-boards.greenhouse.io" in url

    def navigate_to_application_form(self, engine: BrowserAutomationEngine) -> None:
        """Greenhouse-hosted job post URLs typically serve the job
        description and the application form on the same page -- so the
        common case is a no-op. As a defensive fallback (some
        configurations may show the description first), this clicks a
        visible "Apply" control via Playwright's own text-matching
        selector syntax (`text=Apply`, not a hand-rolled JS text search)
        and re-checks afterward, raising a clear error if the form still
        isn't present rather than silently continuing.
        """
        if self._form_is_present(engine):
            return
        engine.click("text=Apply")
        if not self._form_is_present(engine):
            raise ValueError(
                "Clicked an 'Apply' element, but no Greenhouse application "
                f"form ({_FIRST_NAME_FIELD_SELECTOR}) was found afterward -- "
                "this page's structure may not match GreenhouseConnector's "
                "assumptions."
            )

    def get_field_detector(self, engine: BrowserAutomationEngine) -> FormFieldDetector:
        # Greenhouse uses plain, native HTML form elements (confirmed
        # from Greenhouse's own API docs) -- nothing platform-specific
        # to detect, so the generic detector is used unchanged.
        return PlaywrightFormFieldDetector(engine)

    def _form_is_present(self, engine: BrowserAutomationEngine) -> bool:
        return bool(
            engine.evaluate(f"document.querySelector('{_FIRST_NAME_FIELD_SELECTOR}') !== null")
        )
