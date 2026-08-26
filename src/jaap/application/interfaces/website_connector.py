"""WebsiteConnector interface (port).

Defined as a Protocol, not ABC -- same reasoning as every other
interface in this project (ADR-0005/0008/0009/0010/0014). No concrete
implementation yet (`GreenhouseConnector`/`LeverConnector`/`WorkdayConnector`
are Milestones 20/21/22); this milestone is intentionally minimal, the
same way Milestone 13's `AIProvider` was: an interface with no
implementation and no consumer yet has almost no testable behavior of
its own, verified concretely once real implementations exist and must
satisfy it.

`platform_name` is meant to correspond to `JobPosting.platform` --
`JobPlatform`'s constants (`domain/models/job_posting.py`) were written
back in Milestone 2 specifically anticipating this: "so that a new
connector (Milestone 19+) can introduce support for a job site... without
needing to modify this domain model." This is that connector arriving on
schedule, not a new pattern.

Three responsibilities, matching the roadmap's own wording exactly:

  - "detect current platform" -> `matches()`
  - "locate apply flow" -> `navigate_to_application_form()`
  - "map fields" -> `get_field_detector()`

`get_field_detector()` does NOT duplicate FormFieldDetector's
responsibility -- a connector SELECTS or PROVIDES whichever
FormFieldDetector implementation is right for its platform, rather than
reimplementing detection logic inline. A platform that's mostly standard
HTML can return the existing PlaywrightFormFieldDetector unchanged; a
platform with custom, non-native widgets (e.g. Workday's custom
dropdowns, which the generic detector cannot see since it only queries
`input, select, textarea`) can provide its own specialized detector --
while both still produce the same DetectedField type ExactFieldMatcher
already knows how to consume.

CRITICAL SAFETY BOUNDARY, stated here as well as on
BrowserAutomationEngine.click() itself: `navigate_to_application_form()`
may click navigation controls (an "Apply Now" button, "Continue" in a
multi-step wizard) but must NEVER click a final submission control. This
was confirmed explicitly with the project owner before `click()` was
added to BrowserAutomationEngine (see docs/adr/0020-website-connector-interface.md)
specifically because it is not, and must never become, a reopening of
the "no automatic submission" boundary established in ADR-0001/0012.
There remains no code path anywhere in this codebase that submits a
completed application without human review.
"""

from __future__ import annotations

from typing import Protocol

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import FormFieldDetector


class WebsiteConnector(Protocol):
    @property
    def platform_name(self) -> str:
        """A short identifier matching JobPlatform's convention (e.g.
        "greenhouse") -- see JobPlatform in domain/models/job_posting.py."""
        ...

    def matches(self, url: str) -> bool:
        """Returns True if this connector knows how to handle the job
        posting/application at `url`."""
        ...

    def navigate_to_application_form(self, engine: BrowserAutomationEngine) -> None:
        """Given `engine` already on a job posting page, navigate to the
        actual application form -- clicking through an "Apply" button or
        similar if the platform separates the posting from the form.

        Must NEVER click a final submission control -- see this module's
        docstring for why this boundary matters and how it was confirmed.
        """
        ...

    def get_field_detector(self, engine: BrowserAutomationEngine) -> FormFieldDetector:
        """Returns the FormFieldDetector implementation appropriate for
        this platform, composed with `engine`. May be the generic
        PlaywrightFormFieldDetector unchanged, or a platform-specific
        implementation that understands this platform's own custom
        widgets -- see this module's docstring."""
        ...
