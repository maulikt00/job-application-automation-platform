"""Tests for WebsiteConnector.

Deliberately minimal, matching test_ai_provider.py's precedent: this
milestone (19) is just the interface, with no concrete implementations
(Milestone 20/21/22) and no consumers yet. There is almost nothing to
test beyond "is this Protocol well-formed" -- its real correctness will
be verified once GreenhouseConnector/LeverConnector/WorkdayConnector
exist and must structurally satisfy it.
"""

from __future__ import annotations

from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.form_field_detector import FormFieldDetector
from jaap.application.interfaces.website_connector import WebsiteConnector


class _StubConnector:
    """Throwaway, not a reusable fake -- exists only to prove
    WebsiteConnector is a well-formed, satisfiable Protocol. A real fake
    (for Milestone 20+'s use case tests) gets added once there's an
    actual consumer to test against, matching how FakeBrowserEngine
    wasn't added until Milestone 10 needed one.
    """

    @property
    def platform_name(self) -> str:
        return "stub"

    def matches(self, url: str) -> bool:
        return "stub.example.com" in url

    def navigate_to_application_form(self, engine: BrowserAutomationEngine) -> None:
        pass

    def get_field_detector(self, engine: BrowserAutomationEngine) -> FormFieldDetector:
        raise NotImplementedError


def test_a_conforming_class_satisfies_the_protocol() -> None:
    connector: WebsiteConnector = _StubConnector()

    assert connector.platform_name == "stub"


def test_matches_reflects_the_urls_it_was_designed_for() -> None:
    connector: WebsiteConnector = _StubConnector()

    assert connector.matches("https://stub.example.com/jobs/123") is True
    assert connector.matches("https://unrelated.example.com/jobs/123") is False
