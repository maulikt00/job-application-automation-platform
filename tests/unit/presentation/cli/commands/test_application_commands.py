"""Tests for application_commands: start, attach-resume, submit, list."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from jaap.application.exceptions import (
    ApplicationNotReadyForSubmissionError,
    JobPostingNotFoundError,
)
from jaap.domain.models import (
    ApplicationStatus,
    JobPosting,
    Profile,
    Resume,
    new_job_posting_id,
    new_profile_id,
    new_resume_id,
)
from jaap.infrastructure.config.settings import Settings
from jaap.presentation.cli.commands.application_commands import (
    _handle_attach_resume,
    _handle_autofill_current_page,
    _handle_list,
    _handle_review,
    _handle_start,
    _handle_submit,
)
from jaap.presentation.cli.main import Context
from tests.unit.application.use_cases.fakes import (
    FakeAnswerRepository,
    FakeApplicationRepository,
    FakeCoverLetterTemplateRepository,
    FakeJobPostingRepository,
    FakeProfileRepository,
    FakeResumeRepository,
)


def _make_context() -> Context:
    return Context(
        profile_repository=FakeProfileRepository(),
        resume_repository=FakeResumeRepository(),
        job_posting_repository=FakeJobPostingRepository(),
        application_repository=FakeApplicationRepository(),
        answer_repository=FakeAnswerRepository(),
        cover_letter_template_repository=FakeCoverLetterTemplateRepository(),
        settings=Settings(_env_file=None),
    )


def _seed_profile_and_posting(context: Context) -> tuple[Profile, JobPosting]:
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)
    posting = JobPosting(
        id=new_job_posting_id(), company_name="Acme", title="Eng", url="https://acme.example.com/1"
    )
    context.job_posting_repository.save(posting)
    return profile, posting


def _start_application(context: Context, profile: Profile, posting: JobPosting):
    args = argparse.Namespace(profile_id=profile.id, job_posting_id=posting.id)
    _handle_start(args, context)
    return next(iter(context.application_repository.list_by_profile(profile.id)))


def test_handle_start_creates_a_draft_application(capsys) -> None:
    context = _make_context()
    profile, posting = _seed_profile_and_posting(context)
    args = argparse.Namespace(profile_id=profile.id, job_posting_id=posting.id)

    exit_code = _handle_start(args, context)

    assert exit_code == 0
    assert "draft" in capsys.readouterr().out


def test_full_lifecycle_start_attach_resume_submit(capsys) -> None:
    context = _make_context()
    profile, posting = _seed_profile_and_posting(context)
    resume = Resume(id=new_resume_id(), profile_id=profile.id, label="R", file_path=Path("r.pdf"))
    context.resume_repository.save(resume)

    application = _start_application(context, profile, posting)

    attach_args = argparse.Namespace(application_id=application.id, resume_id=resume.id)
    _handle_attach_resume(attach_args, context)

    submit_args = argparse.Namespace(
        application_id=application.id, cover_letter_text_override=None
    )
    exit_code = _handle_submit(submit_args, context)

    assert exit_code == 0
    reloaded = context.application_repository.get(application.id)
    assert reloaded.current_status == ApplicationStatus.SUBMITTED


def test_handle_submit_raises_when_no_resume_attached() -> None:
    context = _make_context()
    profile, posting = _seed_profile_and_posting(context)
    application = _start_application(context, profile, posting)

    submit_args = argparse.Namespace(
        application_id=application.id, cover_letter_text_override=None
    )
    with pytest.raises(ApplicationNotReadyForSubmissionError):
        _handle_submit(submit_args, context)


def test_handle_list_prints_no_applications_when_none_exist(capsys) -> None:
    context = _make_context()
    args = argparse.Namespace(profile_id=new_profile_id())

    exit_code = _handle_list(args, context)

    assert exit_code == 0
    assert "No applications found." in capsys.readouterr().out


def test_handle_list_prints_each_application(capsys) -> None:
    context = _make_context()
    profile, posting = _seed_profile_and_posting(context)
    _start_application(context, profile, posting)

    list_args = argparse.Namespace(profile_id=profile.id)
    exit_code = _handle_list(list_args, context)

    assert exit_code == 0
    assert "status=draft" in capsys.readouterr().out


def test_handle_review_raises_job_posting_not_found_before_touching_the_browser() -> None:
    # _handle_review constructs a real PlaywrightBrowserEngine internally
    # (it's composition-root-style code, like main.py's build_context),
    # so it can't be fully unit-tested with fakes -- but the job-posting
    # lookup happens BEFORE any browser is touched, so this specific path
    # is fast and fake-testable. The real, full happy path is covered by
    # tests/unit/infrastructure/browser/test_review_end_to_end.py.
    context = _make_context()
    args = argparse.Namespace(
        profile_id=new_profile_id(),
        job_posting_id=new_job_posting_id(),
        resume_id=None,
        screenshot_path=None,
    )

    with pytest.raises(JobPostingNotFoundError):
        _handle_review(args, context)


# --- application autofill-current-page (ADR-0041) ---
#
# _handle_autofill_current_page has no "before touching the browser"
# path to test the way _handle_review does (there's no job posting to
# look up at all -- that's the whole point). A real CDP connection
# can't be tested here (see test_attached_browser_engine.py for
# AttachedBrowserEngine's own, separately-verified logic and its
# documented note that real connection behavior needs an actual Chrome
# instance to verify). Instead, this tests the CLI handler's own
# orchestration logic -- constructing the use cases correctly, calling
# execute() with the right arguments, printing the report -- via a
# fake engine satisfying BrowserAutomationEngine directly, patched in
# place of AttachedBrowserEngine.


class _FakeAttachedEngine:
    """A fake BrowserAutomationEngine used only to verify
    _handle_autofill_current_page's own orchestration logic, not any
    real CDP connection -- AttachedBrowserEngine's own connection logic
    is tested separately, with mocks, in test_attached_browser_engine.py.
    """

    def __init__(self, cdp_url: str) -> None:
        self.cdp_url = cdp_url

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def evaluate(self, script: str):
        if "window.location.href" in script:
            return "https://example.com/some-application-page"
        # The real field-detection script would run here against a real
        # page; returning an empty list is a safe, simple stand-in --
        # this test is about the CLI's own orchestration, not detection.
        return []

    def fill(self, selector: str, value: str) -> None:
        pass

    def check(self, selector: str, checked: bool) -> None:
        pass

    def select_option(self, selector: str, value: str) -> None:
        pass

    def upload_file(self, selector: str, file_path) -> None:
        pass

    def click(self, selector: str) -> None:
        pass

    def screenshot(self, path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fake-screenshot")


def test_handle_autofill_current_page_connects_with_the_given_cdp_url(
    tmp_path, capsys
) -> None:
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)

    with patch(
        "jaap.presentation.cli.commands.application_commands.AttachedBrowserEngine"
    ) as fake_engine_class:
        fake_engine_class.side_effect = _FakeAttachedEngine
        args = argparse.Namespace(
            profile_id=profile.id,
            resume_id=None,
            screenshot_path=tmp_path / "shot.png",
            cdp_url="http://localhost:9222",
        )

        exit_code = _handle_autofill_current_page(args, context)

    assert exit_code == 0
    fake_engine_class.assert_called_once_with(cdp_url="http://localhost:9222")
    output = capsys.readouterr().out
    assert "Autofilled" in output
    assert "Nothing has been submitted" in output


def test_handle_autofill_current_page_reports_no_matched_platform_for_an_unrecognized_url(
    tmp_path, capsys
) -> None:
    # The fake engine's URL ("example.com") matches no real connector --
    # confirms the ordinary, unconnected case doesn't print a false
    # "Detected platform" line.
    context = _make_context()
    profile = Profile(id=new_profile_id(), full_name="A", email="a@example.com")
    context.profile_repository.save(profile)

    with patch(
        "jaap.presentation.cli.commands.application_commands.AttachedBrowserEngine"
    ) as fake_engine_class:
        fake_engine_class.side_effect = _FakeAttachedEngine
        args = argparse.Namespace(
            profile_id=profile.id,
            resume_id=None,
            screenshot_path=tmp_path / "shot.png",
            cdp_url="http://localhost:9222",
        )

        _handle_autofill_current_page(args, context)

    assert "Detected platform" not in capsys.readouterr().out
