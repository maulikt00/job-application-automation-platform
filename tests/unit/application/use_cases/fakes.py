"""In-memory fake repositories, one per Protocol interface in
application/interfaces/repositories.py.

This module is the direct payoff of Milestone 5's Protocol-based design
(ADR-0005): each fake satisfies its interface purely by having matching
method signatures -- no inheritance from anything in
infrastructure/database/ required. Use case tests depend on these
instead of a real SqliteXRepository, so they run with no database at
all and stay fast and deterministic.

Named `fakes.py`, not `test_fakes.py`: pytest would otherwise try to
collect this as a test module itself, which it isn't.
"""

from __future__ import annotations

from pathlib import Path

from jaap.domain.models import (
    Answer,
    AnswerId,
    Application,
    ApplicationId,
    CoverLetterTemplate,
    CoverLetterTemplateId,
    JobPosting,
    JobPostingId,
    Profile,
    ProfileId,
    Resume,
    ResumeId,
)


class FakeProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[ProfileId, Profile] = {}

    def get(self, profile_id: ProfileId) -> Profile | None:
        return self._profiles.get(profile_id)

    def save(self, profile: Profile) -> None:
        self._profiles[profile.id] = profile

    def delete(self, profile_id: ProfileId) -> None:
        self._profiles.pop(profile_id, None)


class FakeResumeRepository:
    def __init__(self) -> None:
        self._resumes: dict[ResumeId, Resume] = {}

    def get(self, resume_id: ResumeId) -> Resume | None:
        return self._resumes.get(resume_id)

    def save(self, resume: Resume) -> None:
        self._resumes[resume.id] = resume

    def delete(self, resume_id: ResumeId) -> None:
        self._resumes.pop(resume_id, None)

    def list_by_profile(self, profile_id: ProfileId) -> list[Resume]:
        return [r for r in self._resumes.values() if r.profile_id == profile_id]


class FakeCoverLetterTemplateRepository:
    def __init__(self) -> None:
        self._templates: dict[CoverLetterTemplateId, CoverLetterTemplate] = {}

    def get(self, template_id: CoverLetterTemplateId) -> CoverLetterTemplate | None:
        return self._templates.get(template_id)

    def save(self, template: CoverLetterTemplate) -> None:
        self._templates[template.id] = template

    def delete(self, template_id: CoverLetterTemplateId) -> None:
        self._templates.pop(template_id, None)

    def list_by_profile(self, profile_id: ProfileId) -> list[CoverLetterTemplate]:
        return [t for t in self._templates.values() if t.profile_id == profile_id]


class FakeAnswerRepository:
    def __init__(self) -> None:
        self._answers: dict[AnswerId, Answer] = {}

    def get(self, answer_id: AnswerId) -> Answer | None:
        return self._answers.get(answer_id)

    def save(self, answer: Answer) -> None:
        self._answers[answer.id] = answer

    def delete(self, answer_id: AnswerId) -> None:
        self._answers.pop(answer_id, None)

    def list_by_profile(self, profile_id: ProfileId) -> list[Answer]:
        return [a for a in self._answers.values() if a.profile_id == profile_id]


class FakeJobPostingRepository:
    def __init__(self) -> None:
        self._postings: dict[JobPostingId, JobPosting] = {}

    def get(self, job_posting_id: JobPostingId) -> JobPosting | None:
        return self._postings.get(job_posting_id)

    def save(self, job_posting: JobPosting) -> None:
        self._postings[job_posting.id] = job_posting

    def delete(self, job_posting_id: JobPostingId) -> None:
        self._postings.pop(job_posting_id, None)

    def find_by_platform_and_external_id(
        self, platform: str, external_id: str
    ) -> JobPosting | None:
        for posting in self._postings.values():
            if posting.platform == platform and posting.external_id == external_id:
                return posting
        return None


class FakeApplicationRepository:
    def __init__(self) -> None:
        self._applications: dict[ApplicationId, Application] = {}

    def get(self, application_id: ApplicationId) -> Application | None:
        return self._applications.get(application_id)

    def save(self, application: Application) -> None:
        self._applications[application.id] = application

    def delete(self, application_id: ApplicationId) -> None:
        self._applications.pop(application_id, None)

    def list_by_profile(self, profile_id: ProfileId) -> list[Application]:
        return [a for a in self._applications.values() if a.profile_id == profile_id]


class FakeBrowserEngine:
    """Fake BrowserAutomationEngine recording every fill/check/select_option/
    upload_file call it receives, so AutofillApplicationUseCase's dispatch
    logic can be asserted on directly without a real browser. Only
    implements the methods AutofillApplicationUseCase actually calls --
    launch/navigate/etc. aren't needed for these tests."""

    def __init__(self) -> None:
        self.filled: list[tuple[str, str]] = []
        self.checked: list[tuple[str, bool]] = []
        self.selected: list[tuple[str, str]] = []
        self.uploaded: list[tuple[str, str]] = []

    def fill(self, selector: str, value: str) -> None:
        self.filled.append((selector, value))

    def check(self, selector: str, checked: bool) -> None:
        self.checked.append((selector, checked))

    def select_option(self, selector: str, value: str) -> None:
        self.selected.append((selector, value))

    def upload_file(self, selector: str, file_path: Path) -> None:
        # .as_posix(), not str(): this is a test double used purely for
        # assertions -- it has no reason to render platform-dependent
        # separators (backslashes on Windows) the way the real
        # PlaywrightBrowserEngine correctly does for actual OS file
        # access. Same root cause as the Windows path bug fixed in
        # resume_mapper.py (Milestone 5/6), here in a test double instead
        # of production code.
        self.uploaded.append((selector, file_path.as_posix()))


class FakeFormFieldDetector:
    """Fake FormFieldDetector returning a fixed, pre-configured list of
    DetectedFields, so use case tests don't need a real page to detect
    fields from."""

    def __init__(self, fields: list) -> None:
        self._fields = fields

    def detect_fields(self) -> list:
        return self._fields


class FakeFieldMatcher:
    """Fake FieldMatcher returning a fixed, pre-configured FieldMatchResult,
    so use case tests can assert on dispatch behavior (given a known
    match result, does the use case call the right engine method)
    independent of any real matching logic."""

    def __init__(self, result) -> None:
        self._result = result

    def match(self, fields, profile, answers, resume=None):
        return self._result
