"""Connector registry: given a URL, find the WebsiteConnector that
handles it, if any.

This is the piece that was missing after Milestones 19-22:
GreenhouseConnector/LeverConnector/WorkdayConnector existed, each
correctly implementing WebsiteConnector, but nothing in the actual CLI
flow (`jaap application review`) ever constructed or consulted one --
`_handle_review` always used the generic PlaywrightFormFieldDetector
directly, regardless of which platform a JobPosting's URL actually
pointed to. This registry, and the CLI wiring that now uses it
(Milestone 23), is what makes the three connectors' work actually reach
a real autofill run rather than sitting unused.

A plain list-and-check, not a plugin/registration framework: adding a
fourth connector means adding one line here, matching this project's
consistent preference for the smallest mechanism that solves the actual
problem (see ADR-0006 and others on this same theme).
"""

from __future__ import annotations

from jaap.application.interfaces.website_connector import WebsiteConnector
from jaap.infrastructure.connectors.greenhouse_connector import GreenhouseConnector
from jaap.infrastructure.connectors.lever_connector import LeverConnector
from jaap.infrastructure.connectors.workday_connector import WorkdayConnector

_CONNECTORS: tuple[WebsiteConnector, ...] = (
    GreenhouseConnector(),
    LeverConnector(),
    WorkdayConnector(),
)


def find_connector(url: str) -> WebsiteConnector | None:
    """Returns the first registered connector whose `matches(url)` is
    True, or None if no connector recognizes this URL -- callers must
    treat None as "fall back to the generic FormFieldDetector", not as
    an error; most job postings are not on a platform this project has
    a connector for yet, and that's an expected, ordinary case.
    """
    for connector in _CONNECTORS:
        if connector.matches(url):
            return connector
    return None
