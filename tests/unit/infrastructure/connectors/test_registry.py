"""Tests for the connector registry -- pure, fast, no browser needed
(matches() itself is just a string check for each connector)."""

from __future__ import annotations

from jaap.infrastructure.connectors.greenhouse_connector import GreenhouseConnector
from jaap.infrastructure.connectors.lever_connector import LeverConnector
from jaap.infrastructure.connectors.registry import find_connector
from jaap.infrastructure.connectors.workday_connector import WorkdayConnector


def test_finds_greenhouse_connector() -> None:
    connector = find_connector("https://boards.greenhouse.io/acme/jobs/12345")
    assert isinstance(connector, GreenhouseConnector)


def test_finds_lever_connector() -> None:
    connector = find_connector("https://jobs.lever.co/acme/5ac21346")
    assert isinstance(connector, LeverConnector)


def test_finds_workday_connector() -> None:
    connector = find_connector("https://acme.wd5.myworkdayjobs.com/Acme/job/123")
    assert isinstance(connector, WorkdayConnector)


def test_returns_none_for_an_unrecognized_platform() -> None:
    # The expected, ordinary case for most job postings today -- must
    # not raise, callers are expected to fall back to the generic
    # FormFieldDetector.
    assert find_connector("https://example.com/careers/12345") is None
