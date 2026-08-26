"""Lever-backed WebsiteConnector implementation.

Design grounded in Lever's own published API documentation, not
assumption -- verified directly before writing any code:

  - **URL patterns**: Lever-hosted job postings live at
    `jobs.lever.co/{company}/{posting-id}`, confirmed across multiple
    Lever sources (help docs, the official `postings-api` GitHub repo,
    third-party API wrappers). EU-hosted accounts use
    `jobs.eu.lever.co` instead (confirmed directly from Lever's own
    Postings API documentation) -- both are checked in `matches()`.
  - **A deterministic, documented application-form URL**: Lever's own
    Postings API explicitly distinguishes `hostedUrl` ("a URL which
    points to Lever's hosted job posting page") from `applyUrl` ("a URL
    which points to Lever's hosted application form"), and confirms the
    relationship between them directly with real examples:
    `hostedUrl = https://jobs.lever.co/{company}/{id}`,
    `applyUrl = https://jobs.lever.co/{company}/{id}/apply` -- the exact
    same URL with `/apply` appended. This is a meaningfully different,
    and more reliable, mechanism than GreenhouseConnector's click-based
    fallback (ADR-0021): Lever's own API guarantees the relationship
    between the two URLs, so `navigate_to_application_form()` here is
    pure, deterministic URL manipulation (`engine.navigate()`), never a
    click. Verified to correctly preserve query strings and handle a
    URL that already ends in `/apply` idempotently before being relied on.
  - **Lower confidence on an exact field-name selector than Greenhouse's**,
    stated honestly: Lever's help documentation describes the form in
    admin-configuration terms ("Full Name", "Email" are required by
    default) rather than showing raw HTML markup the way Greenhouse's
    API docs did. Rather than guess a specific `name="..."` attribute
    with more confidence than is warranted, the post-navigation
    verification below checks only for the presence of *some* `<input>`
    element -- a weaker, more honest check than Greenhouse's
    `input[name="first_name"]`, but one that doesn't rely on an
    unconfirmed assumption.

**A real, honest scope limitation, matching GreenhouseConnector's**:
Lever's own public Postings API documentation explicitly mentions "HTML
and iframe modes are for embedding" as a separate integration option
from the directly-hosted `jobs.lever.co` case this connector supports.
Embedded iframe integrations remain out of scope for the same reason as
Greenhouse's (ADR-0021 decision #3): `BrowserAutomationEngine.evaluate()`
runs against the main frame only, and cross-frame interaction is a real,
separate feature this project has not built.
"""

from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import FormFieldDetector
from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector


class LeverConnector:
    """Satisfies application.interfaces.website_connector.WebsiteConnector."""

    @property
    def platform_name(self) -> str:
        return JobPlatform.LEVER

    def matches(self, url: str) -> bool:
        return "jobs.lever.co" in url or "jobs.eu.lever.co" in url

    def navigate_to_application_form(self, engine: BrowserAutomationEngine) -> None:
        """Constructs the `/apply` URL from the current page's URL (Lever's
        own documented `hostedUrl` -> `applyUrl` relationship) and
        navigates there directly -- no click involved, unlike
        GreenhouseConnector's fallback, since Lever's URL contract makes
        this deterministic. Verifies at least one `<input>` element is
        present afterward, raising a clear error if not (see this
        module's docstring for why a generic input check is used rather
        than a specific, unconfirmed field name).
        """
        current_url = engine.evaluate("window.location.href")
        apply_url = _append_apply_path(current_url)
        if apply_url != current_url:
            engine.navigate(apply_url)

        if not engine.evaluate("document.querySelector('input') !== null"):
            raise ValueError(
                f"Navigated to {apply_url!r}, but no <input> element was found "
                "afterward -- this page's structure may not match "
                "LeverConnector's assumptions."
            )

    def get_field_detector(self, engine: BrowserAutomationEngine) -> FormFieldDetector:
        # Lever's own application-form documentation describes standard
        # fields (Full Name, Email, file upload for resume) with no
        # indication of custom, non-native widgets -- the generic
        # detector is used unchanged, same reasoning as GreenhouseConnector.
        return PlaywrightFormFieldDetector(engine)


def _append_apply_path(url: str) -> str:
    """Appends `/apply` to `url`'s path, preserving any query string and
    handling a trailing slash or an already-present `/apply` suffix
    idempotently. A pure function, verified directly against Lever's own
    documented URL examples (including a query-string case) before being
    relied on.
    """
    parts = urlsplit(url)
    path = parts.path.rstrip("/")
    if path.endswith("/apply"):
        return url
    return urlunsplit((parts.scheme, parts.netloc, path + "/apply", parts.query, parts.fragment))
