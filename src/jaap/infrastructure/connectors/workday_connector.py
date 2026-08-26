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
  - **The application-form URL**: confirmed from a real, independently
    scraped Workday job posting example ending in `.../apply` -- the
    same `/apply`-suffix relationship Lever's own API documents
    explicitly (ADR-0022). `navigate_to_application_form()` therefore
    reuses the identical shared logic (`_url_utils.append_apply_path()`),
    extracted specifically because this pattern is now confirmed for two
    platforms independently, not coincidentally similar.
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
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.connectors._url_utils import append_apply_path
from jaap.infrastructure.connectors.workday_form_field_detector import (
    WorkdayFormFieldDetector,
)


class WorkdayConnector:
    """Satisfies application.interfaces.website_connector.WebsiteConnector."""

    @property
    def platform_name(self) -> str:
        return JobPlatform.WORKDAY

    def matches(self, url: str) -> bool:
        return "myworkdayjobs.com" in url or "myworkdaysite.com" in url

    def navigate_to_application_form(self, engine: BrowserAutomationEngine) -> None:
        """Constructs the `/apply` URL from the current page's URL (the
        same confirmed pattern as LeverConnector, see this module's
        docstring) and navigates there directly. Only reaches the START
        of Workday's multi-step application flow -- see this module's
        docstring for why walking every subsequent step is out of scope,
        consistent with this project's existing multi-step handling.
        """
        current_url = engine.evaluate("window.location.href")
        apply_url = append_apply_path(current_url)
        if apply_url != current_url:
            engine.navigate(apply_url)

        if not engine.evaluate("document.querySelector('input, [role=\"combobox\"]') !== null"):
            raise ValueError(
                f"Navigated to {apply_url!r}, but no <input> or combobox element "
                "was found afterward -- this page's structure may not match "
                "WorkdayConnector's assumptions."
            )

    def get_field_detector(self, engine: BrowserAutomationEngine) -> FormFieldDetector:
        # Unlike GreenhouseConnector/LeverConnector, Workday's own
        # custom-widget usage is well-known enough to warrant a
        # specialized detector rather than reusing the generic one
        # unchanged -- see WorkdayFormFieldDetector's own docstring for
        # the honest confidence distinction on exactly what's detected.
        return WorkdayFormFieldDetector(engine)
