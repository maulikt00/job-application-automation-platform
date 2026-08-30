"""CLI commands for Application: `jaap application start|attach-resume|submit|list|review`."""

from __future__ import annotations

import argparse
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

from jaap.application.exceptions import JobPostingNotFoundError
from jaap.application.interfaces.browser_engine import BrowserAutomationEngine
from jaap.application.interfaces.website_connector import WebsiteConnector
from jaap.application.services.field_matcher import ExactFieldMatcher
from jaap.application.use_cases.attach_resume_to_application import (
    AttachResumeToApplicationUseCase,
)
from jaap.application.use_cases.autofill_application import AutofillApplicationUseCase
from jaap.application.use_cases.review_application import ReviewApplicationUseCase
from jaap.application.use_cases.start_application import StartApplicationUseCase
from jaap.application.use_cases.submit_application import SubmitApplicationUseCase
from jaap.domain.exceptions import AuthenticationRequiredError
from jaap.domain.models import ApplicationId, JobPostingId, ProfileId, ResumeId
from jaap.infrastructure.browser.form_field_detector import PlaywrightFormFieldDetector
from jaap.infrastructure.browser.playwright_engine import PlaywrightBrowserEngine
from jaap.infrastructure.connectors.registry import find_connector

if TYPE_CHECKING:
    from jaap.presentation.cli.main import Context


def register(subparsers: argparse._SubParsersAction) -> None:
    application_parser = subparsers.add_parser("application", help="Manage applications")
    application_subparsers = application_parser.add_subparsers(dest="action", required=True)

    start_parser = application_subparsers.add_parser("start", help="Start a new draft application")
    start_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    start_parser.add_argument("--job-posting-id", required=True, type=uuid.UUID)
    start_parser.set_defaults(handler=_handle_start)

    attach_resume_parser = application_subparsers.add_parser(
        "attach-resume", help="Attach a resume to a draft application"
    )
    attach_resume_parser.add_argument("--application-id", required=True, type=uuid.UUID)
    attach_resume_parser.add_argument("--resume-id", required=True, type=uuid.UUID)
    attach_resume_parser.set_defaults(handler=_handle_attach_resume)

    submit_parser = application_subparsers.add_parser("submit", help="Submit a draft application")
    submit_parser.add_argument("--application-id", required=True, type=uuid.UUID)
    submit_parser.add_argument(
        "--cover-letter-text-override",
        default=None,
        help=(
            "Literal cover letter text for this submission only (e.g. from "
            "`jaap cover-letter generate`), used regardless of whether a "
            "cover_letter_template_id is also set (see ADR-0013)."
        ),
    )
    submit_parser.set_defaults(handler=_handle_submit)

    list_parser = application_subparsers.add_parser(
        "list", help="List applications for a profile"
    )
    list_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    list_parser.set_defaults(handler=_handle_list)

    review_parser = application_subparsers.add_parser(
        "review",
        help=(
            "Autofill a job posting's application page and produce a "
            "reviewable report + screenshot. Never submits -- JAAP has no "
            "capability to click a submit button."
        ),
    )
    review_parser.add_argument("--profile-id", required=True, type=uuid.UUID)
    review_parser.add_argument("--job-posting-id", required=True, type=uuid.UUID)
    review_parser.add_argument("--resume-id", type=uuid.UUID, default=None)
    review_parser.add_argument("--screenshot-path", type=Path, default=None)
    review_parser.add_argument(
        "--interactive",
        action="store_true",
        help=(
            "If a connector reports that signing in is required "
            "(AuthenticationRequiredError), pause with the browser open "
            "so you can sign in yourself, then retry when you press "
            "Enter, instead of failing immediately. JAAP still never "
            "automates the sign-in step itself (see ADR-0034). Requires "
            "JAAP_HEADLESS=false, since you need to see the browser "
            "window to sign in with."
        ),
    )
    review_parser.set_defaults(handler=_handle_review)


def _handle_start(args: argparse.Namespace, context: Context) -> int:
    use_case = StartApplicationUseCase(
        context.application_repository, context.profile_repository, context.job_posting_repository
    )
    application = use_case.execute(
        profile_id=ProfileId(args.profile_id), job_posting_id=JobPostingId(args.job_posting_id)
    )
    print(f"Started application {application.id} (status: {application.current_status.value})")
    return 0


def _handle_attach_resume(args: argparse.Namespace, context: Context) -> int:
    use_case = AttachResumeToApplicationUseCase(
        context.application_repository, context.resume_repository
    )
    application = use_case.execute(
        application_id=ApplicationId(args.application_id), resume_id=ResumeId(args.resume_id)
    )
    print(f"Attached resume {args.resume_id} to application {application.id}")
    return 0


def _handle_submit(args: argparse.Namespace, context: Context) -> int:
    use_case = SubmitApplicationUseCase(
        context.application_repository,
        context.resume_repository,
        context.answer_repository,
        context.cover_letter_template_repository,
    )
    application = use_case.execute(
        ApplicationId(args.application_id),
        cover_letter_text_override=args.cover_letter_text_override,
    )
    print(f"Submitted application {application.id} (status: {application.current_status.value})")
    return 0


def _handle_list(args: argparse.Namespace, context: Context) -> int:
    # Deliberately calls the repository directly rather than through a
    # use case: listing carries no business rule to enforce (unlike
    # start/submit), so a dedicated use case would add ceremony without
    # adding behavior. This is still dependency-rule-clean -- `context`
    # only exposes Protocol interfaces (application layer), never a
    # concrete SqliteApplicationRepository -- it's just skipping the
    # use-case layer for a trivial read, not skipping the abstraction.
    applications = context.application_repository.list_by_profile(ProfileId(args.profile_id))
    if not applications:
        print("No applications found.")
        return 0
    for application in applications:
        print(
            f"{application.id}  status={application.current_status.value}  "
            f"job_posting={application.job_posting_id}"
        )
    return 0


def _handle_review(args: argparse.Namespace, context: Context) -> int:
    job_posting_id = JobPostingId(args.job_posting_id)
    posting = context.job_posting_repository.get(job_posting_id)
    if posting is None:
        raise JobPostingNotFoundError(job_posting_id)

    if args.interactive and context.settings.headless:
        # Fails fast, before launching a browser at all: a headless
        # browser has no visible window for a human to sign in with,
        # so --interactive would otherwise just appear to hang with
        # nothing to interact with.
        raise ValueError(
            "--interactive requires a visible browser window to sign in "
            "with -- set JAAP_HEADLESS=false and try again."
        )

    screenshot_path = args.screenshot_path or (
        context.settings.log_dir / "review_screenshots" / f"{args.job_posting_id}.png"
    )

    # The browser closes at the end of this block -- the screenshot,
    # captured before that happens, is the reviewable artifact (see
    # ReviewApplicationUseCase's docstring and ADR-0012 for why this
    # command does not leave the browser open for a live handoff).
    # --interactive (ADR-0034) is a deliberate, explicit, opt-in
    # exception to that norm for exactly one situation (a connector
    # reporting AuthenticationRequiredError) -- the browser still closes
    # at the end of this same block either way; it just may pause,
    # still open, partway through first.
    with PlaywrightBrowserEngine(context.settings) as engine:
        engine.navigate(str(posting.url))

        # Milestone 23: consult the connector registry instead of always
        # using the generic detector. This is the real gap Milestones
        # 19-22's connectors sat behind until now -- nothing previously
        # constructed or consulted one from this command at all. Falling
        # back to the generic detector when no connector matches is the
        # expected, ordinary case for any platform without a connector
        # yet, not an error.
        connector = find_connector(str(posting.url))
        if connector is not None:
            try:
                connector.navigate_to_application_form(engine)
            except AuthenticationRequiredError as exc:
                if not args.interactive:
                    raise
                _wait_for_manual_sign_in(engine, connector, exc)
            form_field_detector = connector.get_field_detector(engine)
        else:
            form_field_detector = PlaywrightFormFieldDetector(engine)

        autofill_use_case = AutofillApplicationUseCase(
            browser_engine=engine,
            form_field_detector=form_field_detector,
            field_matcher=ExactFieldMatcher(),
            profile_repository=context.profile_repository,
            answer_repository=context.answer_repository,
            resume_repository=context.resume_repository,
        )
        review_use_case = ReviewApplicationUseCase(autofill_use_case, engine)

        review = review_use_case.execute(
            profile_id=ProfileId(args.profile_id),
            screenshot_path=screenshot_path,
            resume_id=ResumeId(args.resume_id) if args.resume_id else None,
        )

    if connector is not None:
        print(f"Detected platform: {connector.platform_name}")
        print()

    print(f"Autofilled {len(review.matched)} field(s):")
    for matched in review.matched:
        print(f"  - {matched.field.name} = {matched.value!r}  (from {matched.source})")

    print()
    if review.unmatched:
        print(f"{len(review.unmatched)} field(s) need your manual review:")
        for field in review.unmatched:
            print(f"  - {field.name}  (label: {field.label!r})")
    else:
        print("All detected fields were matched -- still review them below before proceeding.")

    print()
    print(f"Screenshot saved to: {review.screenshot_path}")
    print()
    print(
        "Nothing has been submitted. JAAP does not click submit buttons --"
        " review the screenshot and the unmatched fields above, then"
        " complete submission yourself in your own browser."
    )
    return 0


def _wait_for_manual_sign_in(
    engine: BrowserAutomationEngine,
    connector: WebsiteConnector,
    error: AuthenticationRequiredError,
) -> None:
    """Pauses with the browser still open, letting a human sign in
    themselves, then retries `navigate_to_application_form()` -- ADR-0034.

    JAAP still never automates the sign-in step itself; this only
    pauses and gets out of the way while a human does it, then resumes
    automation once they're done. Loops (rather than retrying only
    once) since a real sign-in flow can itself be multi-step (email,
    then password, then a 2FA prompt), so a human may reasonably need
    more than one attempt before `navigate_to_application_form()`
    actually succeeds.
    """
    print()
    print(f"Sign-in required: {error}")
    print()
    print("A browser window is open on the sign-in page -- please sign in there now.")
    while True:
        response = input(
            "Press Enter once you've signed in to continue (or type 'q' to give up): "
        ).strip().lower()
        if response == "q":
            raise error
        try:
            connector.navigate_to_application_form(engine)
            print("Continuing...")
            return
        except AuthenticationRequiredError as exc:
            print()
            print(f"Still looks like sign-in is required: {exc}")
            error = exc
