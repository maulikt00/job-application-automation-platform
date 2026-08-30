"""Workday-backed WebsiteConnector implementation.

Design grounded in real, published evidence for URL patterns, with an
explicitly honest confidence distinction for field detection -- see
WorkdayFormFieldDetector's own module docstring for the latter.

  - **URL patterns**: two real domain families, both confirmed from
    independent sources (Workday scraper/API tooling documentation,
    third-party Workday integration guides): `{tenant}.wd{N}.myworkdayjobs.com`
    (the data-center number varies per company -- confirmed explicitly:
    "Companies use different Workday data centers (wd1, wd3, wd5, etc.)...
    Do not assume wd3 works for all companies") and the newer
    `myworkdaysite.com` format. `matches()` checks for the stable
    substrings `myworkdayjobs.com` and `myworkdaysite.com`, not a fixed
    tenant/data-center number.
  - **The application-form URL**: a third-party-scraped example
    suggested a simple `/apply`-suffix relationship (the same pattern
    Lever's own API documents explicitly, ADR-0022), so
    `navigate_to_application_form()` tries that first via the shared
    `_url_utils.append_apply_path()`. Real-world validation against
    Workday's own careers site (2026-08, see ADR-0031) found this does
    NOT reveal a form by itself on at least this tenant -- clicking
    "Apply" instead opens an in-page modal (never a direct navigation)
    offering several paths: "Autofill with Resume" (Workday's own AI
    resume-parsing feature, a different thing from JAAP's autofill),
    "Apply Manually", "Use My Last Application" (requires an existing
    session), and a third-party redirect option (e.g. "Apply with
    SEEK"). "Apply Manually" is chosen deliberately as the most neutral
    of these.
  - **A real, more fundamental limitation found via this same
    validation, not merely a bug**: even "Apply Manually" led directly
    to a mandatory account-creation/sign-in step before any actual
    application field could be reached. JAAP does not automate account
    creation or login, under any circumstances -- this is a firm,
    deliberate boundary, not a gap to be engineered around. See
    ADR-0031 for the full reasoning and why this may not be fixable
    without a separate, deliberate decision to support persistent
    browser sessions (a real architectural change, not attempted here).
  - **A separate, genuinely fixable bug found while confirming
    ADR-0031's finding against a second Workday tenant (NVIDIA's,
    2026-08, see ADR-0032)**: clicking "Apply Manually" can report a
    Playwright timeout even when the underlying click actually
    succeeded -- confirmed directly: the page's URL had already
    changed to the expected `.../applyManually` suffix by the time the
    exception was raised. This click causes an immediate page
    transition, and Playwright's own click() waits for the clicked
    element to remain stable/attached before declaring success; on a
    slower-responding real site, the element can disappear (the page
    having already moved on) before that wait resolves, timing out
    even though nothing is actually wrong. This is caught and treated
    as informational, not a hard failure -- see the try/except in
    `navigate_to_application_form()` below.
  - **A third, more foundational bug found on a real posting's page
    with heavy site chrome (NVIDIA's, 2026-08, see ADR-0033)**: the
    original "is a form present" check (`input, [role="combobox"]`
    anywhere on the page) is far too weak against a real corporate
    site -- NVIDIA's own posting page had a nav search box, a country
    selector, and a OneTrust cookie-consent widget's own checkboxes,
    all genuinely present in the DOM before any Apply interaction at
    all, causing the check to falsely report "form found" without ever
    attempting the Apply flow. Fixed by additionally requiring
    Workday's own `data-automation-id` attribute -- the same marker
    `WorkdayFormFieldDetector`'s combobox detection already uses, on
    the same honest, community-sourced (not primary-source-confirmed)
    confidence basis stated there. This has NOT been verified against
    an actual, real Workday application form's markup, since every
    real attempt so far has hit the sign-in wall before reaching one --
    stated honestly, not glossed over.
  - **Confirmed as genuinely multi-step**: independent sources describe
    "the full Workday application flow (upload, auto-fill form, review,
    submit)" -- multiple stages, not a single page. This connector's
    `navigate_to_application_form()` only gets to the START of that flow
    (the first form step), matching this project's already-established
    multi-step handling: `AutofillApplicationUseCase` operates on
    whatever page is currently loaded, and a multi-step flow requires
    re-running the review/autofill step after advancing between pages --
    this was already true for any multi-step ATS before Workday, not a
    new limitation introduced here.

See WorkdayFormFieldDetector's own module docstring for the honest
confidence distinction on custom-widget (combobox) detection: it is
based on the standard, cross-platform ARIA pattern for accessible
custom dropdowns, not a confirmed Workday-specific selector the way
Greenhouse's/Lever's details were -- and is designed so a detected
combobox can never be automatically filled, only surfaced for human
review.

Same honest scope limitation as Greenhouse/Lever: embedded iframe
integrations (if Workday offers one for a given tenant configuration)
are out of scope, since `BrowserAutomationEngine` has no cross-frame
interaction capability.
"""

from __future__ import annotations

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import FormFieldDetector
from jaap.domain.exceptions import AuthenticationRequiredError, BrowserAutomationError
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.connectors._url_utils import append_apply_path
from jaap.infrastructure.connectors.workday_form_field_detector import (
    WorkdayFormFieldDetector,
)

_FIELD_PRESENT_SCRIPT = (
    'document.querySelector(\'input[data-automation-id], select[data-automation-id], '
    'textarea[data-automation-id], [role="combobox"][data-automation-id]\') !== null'
)

# A deliberately simple, general signal -- checked only after the real,
# confirmed Apply-flow attempt below has already failed to reveal any
# field. Found necessary via live-site validation (ADR-0031): Workday's
# own careers site required signing in before any application field
# could be reached, via every path the "Start Your Application" modal
# offered except a third-party redirect.
_SIGN_IN_INDICATOR_SCRIPT = r"""
(() => {
  const text = document.body.innerText || "";
  return /sign in|log in|create.{0,10}account/i.test(text);
})()
"""


class WorkdayConnector:
    """Satisfies application.interfaces.website_connector.WebsiteConnector."""

    @property
    def platform_name(self) -> str:
        return JobPlatform.WORKDAY

    def matches(self, url: str) -> bool:
        return "myworkdayjobs.com" in url or "myworkdaysite.com" in url

    def navigate_to_application_form(self, engine: BrowserAutomationEngine) -> None:
        """First tries the `/apply`-suffix URL pattern (matching
        LeverConnector's confirmed mechanism) in case it works directly.
        If not, falls back to the real, confirmed click sequence found
        via live-site validation (ADR-0031): click "Apply" (opens an
        in-page modal, not a navigation), then "Apply Manually" (the
        most neutral of the modal's options -- see this module's
        docstring). The second click's own failure is caught and
        treated as informational, not fatal (ADR-0032): it can cause an
        immediate page transition that makes Playwright's own click()
        report a timeout even when the underlying action succeeded --
        confirmed directly against a real site, not assumed. If neither
        attempt reveals a form, checks whether the page looks like a
        sign-in/account-creation wall and raises
        `AuthenticationRequiredError` (ADR-0034) if so, rather than the
        generic "structure doesn't match assumptions" ValueError --
        JAAP will not attempt to get past this itself, by design, but
        `jaap application review --interactive` can pause here and let
        a human sign in before retrying.
        """
        current_url = engine.evaluate("window.location.href")
        apply_url = append_apply_path(current_url)
        if apply_url != current_url:
            engine.navigate(apply_url)

        if self._field_present(engine):
            return

        engine.click("text=Apply")
        try:
            engine.click("text=Apply Manually")
        except BrowserAutomationError:
            # See this module's docstring and ADR-0032: this specific
            # click can report a timeout even when it actually
            # succeeded, since it causes an immediate page transition.
            # Proceeding to check the resulting page state regardless,
            # rather than treating this as a hard failure.
            pass

        if self._field_present(engine):
            return

        if engine.evaluate(_SIGN_IN_INDICATOR_SCRIPT):
            raise AuthenticationRequiredError(
                "This Workday posting requires creating an account or "
                "signing in before the application form can be reached. "
                "JAAP does not automate account creation or login, and "
                "does not persist browser sessions between runs -- this "
                "posting cannot currently be autofilled by JAAP without "
                "signing in yourself (see `jaap application review "
                "--interactive`)."
            )

        raise ValueError(
            "Clicked through Workday's Apply flow, but no field with a "
            "data-automation-id attribute was found afterward -- this "
            "page's structure may not match WorkdayConnector's assumptions."
        )

    def get_field_detector(self, engine: BrowserAutomationEngine) -> FormFieldDetector:
        # Unlike GreenhouseConnector/LeverConnector, Workday's own
        # custom-widget usage is well-known enough to warrant a
        # specialized detector rather than reusing the generic one
        # unchanged -- see WorkdayFormFieldDetector's own docstring for
        # the honest confidence distinction on exactly what's detected.
        return WorkdayFormFieldDetector(engine)

    def _field_present(self, engine: BrowserAutomationEngine) -> bool:
        return bool(engine.evaluate(_FIELD_PRESENT_SCRIPT))
