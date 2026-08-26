"""Tests for the shared append_apply_path() URL utility.

Extracted from test_lever_connector.py once workday_connector.py needed
the identical logic (both Lever and Workday document a `/apply`-suffix
relationship between a posting URL and its application form URL -- see
ADR-0022/0023). These tests no longer test Lever-specific behavior, so
they moved to their own file alongside the extraction.
"""

from __future__ import annotations

from jaap.infrastructure.connectors._url_utils import append_apply_path


def test_appends_to_a_plain_url() -> None:
    assert (
        append_apply_path("https://jobs.lever.co/leverdemo/5ac21346")
        == "https://jobs.lever.co/leverdemo/5ac21346/apply"
    )


def test_is_idempotent_when_already_present() -> None:
    url = "https://jobs.lever.co/leverdemo/5ac21346/apply"
    assert append_apply_path(url) == url


def test_preserves_query_strings() -> None:
    assert append_apply_path(
        "https://jobs.lever.co/leverdemo/5ac21346?lever-source=LinkedIn"
    ) == "https://jobs.lever.co/leverdemo/5ac21346/apply?lever-source=LinkedIn"


def test_handles_a_trailing_slash() -> None:
    assert (
        append_apply_path("https://jobs.lever.co/leverdemo/5ac21346/")
        == "https://jobs.lever.co/leverdemo/5ac21346/apply"
    )


def test_works_for_a_workday_style_url_too() -> None:
    # Confirms this is genuinely shared logic, not coincidentally
    # similar -- both platforms document the same /apply relationship
    # independently (see ADR-0023).
    assert append_apply_path(
        "https://acme.wd5.myworkdayjobs.com/Acme/job/USA-CA/Engineer_JR-001"
    ) == "https://acme.wd5.myworkdayjobs.com/Acme/job/USA-CA/Engineer_JR-001/apply"
