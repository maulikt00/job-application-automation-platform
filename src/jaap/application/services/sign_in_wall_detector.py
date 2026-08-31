"""Shared sign-in-wall detection -- usable by any WebsiteConnector
implementation, or by the CLI's generic, no-connector fallback path.

Originally built inside WorkdayConnector specifically (ADR-0031), since
that was the only real evidence available at the time. Extracted here
after a second, wholly unrelated real site (IBM's careers site,
`careers.ibm.com`, redirecting an unauthenticated session to
`login.ibm.com`) confirmed this is a general, cross-platform pattern,
not a Workday-specific one (ADR-0040) -- exactly matching what
ADR-0034 always intended `AuthenticationRequiredError` to be (a formal
part of the `WebsiteConnector` interface contract), just not yet
exercised anywhere but Workday until now.
"""

from __future__ import annotations

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine

# A deliberately general, cross-platform text pattern -- not a
# primary-source-confirmed selector the way Greenhouse's/Lever's field
# structures were. May not catch every possible site's specific
# wording, but is the best available general signal, and has now been
# confirmed correct on two wholly unrelated real sites (Workday's,
# ADR-0031; IBM's, ADR-0040).
_SIGN_IN_INDICATOR_SCRIPT = r"""
(() => {
  const text = document.body.innerText || "";
  return /sign in|log in|create.{0,10}account/i.test(text);
})()
"""


def looks_like_sign_in_wall(engine: BrowserAutomationEngine) -> bool:
    return bool(engine.evaluate(_SIGN_IN_INDICATOR_SCRIPT))
