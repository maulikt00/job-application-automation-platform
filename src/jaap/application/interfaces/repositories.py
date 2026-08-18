"""Repository interfaces (ports) for the six aggregate roots.

Defined as `typing.Protocol`, not `abc.ABC` -- see
docs/adr/0005-repository-interfaces-and-mapping-strategy.md for the full
reasoning. In short: this matches ARCHITECTURE.md's existing description
of AIProvider/WebsiteConnector as structural contracts rather than a
class hierarchy, and it means a test double never needs to inherit from
anything to satisfy an interface -- just match the method shapes.

Conventions every repository follows:
  - `get(id)` returns `None` when nothing matches, never raises. "Not
    found" is a normal, expected outcome a use case decides how to
    handle -- not automatically an error.
  - `save(entity)` is an upsert: insert if the id doesn't exist yet,
    otherwise update the existing row.
  - `delete(id)` raises `jaap.domain.exceptions.ReferentialIntegrityError`
    if the entity is still referenced elsewhere and the underlying
    foreign key is RESTRICT (see ADR-0004) -- never a raw SQLAlchemy
    exception. It is a no-op (no error) if the id doesn't exist.

This module imports only from the domain layer, never from
infrastructure -- application/interfaces/ is where the abstraction lives;
infrastructure/database/repositories/ is where it's implemented.
"""

from __future__ import annotations

from typing import Protocol

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


class ProfileRepository(Protocol):
    def get(self, profile_id: ProfileId) -> Profile | None: ...
    def save(self, profile: Profile) -> None: ...
    def delete(self, profile_id: ProfileId) -> None: ...


class ResumeRepository(Protocol):
    def get(self, resume_id: ResumeId) -> Resume | None: ...
    def save(self, resume: Resume) -> None: ...
    def delete(self, resume_id: ResumeId) -> None: ...
    def list_by_profile(self, profile_id: ProfileId) -> list[Resume]: ...


class CoverLetterTemplateRepository(Protocol):
    def get(self, template_id: CoverLetterTemplateId) -> CoverLetterTemplate | None: ...
    def save(self, template: CoverLetterTemplate) -> None: ...
    def delete(self, template_id: CoverLetterTemplateId) -> None: ...
    def list_by_profile(self, profile_id: ProfileId) -> list[CoverLetterTemplate]: ...


class AnswerRepository(Protocol):
    def get(self, answer_id: AnswerId) -> Answer | None: ...
    def save(self, answer: Answer) -> None: ...
    def delete(self, answer_id: AnswerId) -> None: ...
    def list_by_profile(self, profile_id: ProfileId) -> list[Answer]: ...


class JobPostingRepository(Protocol):
    def get(self, job_posting_id: JobPostingId) -> JobPosting | None: ...
    def save(self, job_posting: JobPosting) -> None: ...
    def delete(self, job_posting_id: JobPostingId) -> None: ...
    def find_by_platform_and_external_id(
        self, platform: str, external_id: str
    ) -> JobPosting | None:
        """Look up a posting by its connector-supplied dedup key (see
        JobPosting.external_id / ADR-0003), not by `url`."""
        ...


class ApplicationRepository(Protocol):
    def get(self, application_id: ApplicationId) -> Application | None: ...
    def save(self, application: Application) -> None:
        """Upsert. `status_history` is persisted append-only (only events
        beyond what's already stored are inserted); `answer_ids` is fully
        replaced on every save. See ADR-0005 for why."""
        ...

    def delete(self, application_id: ApplicationId) -> None: ...
    def list_by_profile(self, profile_id: ProfileId) -> list[Application]: ...
