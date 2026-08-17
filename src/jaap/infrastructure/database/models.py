"""SQLAlchemy ORM models.

These are deliberately separate classes from the Pydantic domain models
in domain/models/ -- not the same classes wearing two hats. SQLAlchemy's
mapped classes carry ORM-managed state (lazy-loaded relationships,
identity-mapped instances) that doesn't mix cleanly with Pydantic's
validate-on-construction model. Repositories (Milestone 5) are the
translation boundary between the two.

Schema notes:
  - IDs use SQLAlchemy's generic `Uuid` type, matching the domain's
    UUID-based strongly-typed IDs (see domain/models/ids.py).
  - All timestamps use `UTCDateTime` (types.py) so every stored datetime
    round-trips as timezone-aware UTC, matching what the domain layer
    always produces.
  - `updated_at` on every table is ORM-only bookkeeping for now -- it has
    no equivalent field on the domain models yet. Repositories may choose
    whether/how to surface it; this is flagged here deliberately rather
    than silently expanding the domain models in this milestone.
  - `JobPosting`'s partial unique index on (platform, external_id) enforces
    the deduplication key identified during the Milestone 2 architectural
    review: `url` alone is not a reliable dedup key across scrapes.
  - Foreign keys are enforced via "PRAGMA foreign_keys=ON", which
    session.py wires up automatically per-connection (SQLite ignores FK
    constraints otherwise).

See docs/adr/0004-session-loading-ordering-and-restrictive-deletes.md for
the reasoning behind the following, added during a Milestone 4 review:
  - `ApplicationORM.status_events` and `.answer_associations` use
    `lazy="selectin"`: a repository reconstructing an Application domain
    object always needs both to build `status_history`/`answer_ids`, so
    eager-loading them removes the most common way to hit
    DetachedInstanceError after a session closes. Any other
    relationship/attribute access needed for domain reconstruction must
    still happen while its session is open -- this eager-loading covers
    the common case, not every case.
  - Application <-> Answer is an ordered association object
    (`ApplicationAnswerORM`, with a `position` column), not a plain
    many-to-many table, since SQLAlchemy's `secondary=` pattern can't set
    extra columns on the join row and `Application.answer_ids` is an
    ordered tuple in the domain model.
  - `ApplicationORM.resume_id`, `.cover_letter_template_id`, and
    `ApplicationAnswerORM.answer_id` all use `ON DELETE RESTRICT`, not
    CASCADE/SET NULL: deleting a Resume/CoverLetterTemplate/Answer still
    referenced by an Application now fails loudly instead of silently
    losing the historical record of what was used.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from jaap.domain.models.job_posting import JobPlatform
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.types import UTCDateTime


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ProfileORM(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    resumes: Mapped[list[ResumeORM]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    cover_letter_templates: Mapped[list[CoverLetterTemplateORM]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    answers: Mapped[list[AnswerORM]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    applications: Mapped[list[ApplicationORM]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class ResumeORM(Base):
    __tablename__ = "resumes"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    profile: Mapped[ProfileORM] = relationship(back_populates="resumes")


class CoverLetterTemplateORM(Base):
    __tablename__ = "cover_letter_templates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    profile: Mapped[ProfileORM] = relationship(back_populates="cover_letter_templates")


class AnswerORM(Base):
    __tablename__ = "answers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_key: Mapped[str] = mapped_column(String, nullable=False, index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    profile: Mapped[ProfileORM] = relationship(back_populates="answers")


class JobPostingORM(Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        # Partial unique index: only enforced when external_id is present,
        # since not every posting (e.g. manually entered ones) will have one.
        Index(
            "uq_job_postings_platform_external_id",
            "platform",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    company_name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(
        String, nullable=False, index=True, default=JobPlatform.OTHER
    )
    external_id: Mapped[str | None] = mapped_column(String, nullable=True)
    platform_metadata: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    applications: Mapped[list[ApplicationORM]] = relationship(back_populates="job_posting")


class ApplicationORM(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # RESTRICT, not SET NULL: silently nulling out which resume/template
    # was used on a past application is the same silent-history-loss
    # footgun as the Answer join table (see ADR-0004).
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("resumes.id", ondelete="RESTRICT"), nullable=True
    )
    cover_letter_template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("cover_letter_templates.id", ondelete="RESTRICT"), nullable=True
    )
    current_status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=_utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, nullable=False, default=_utc_now, onupdate=_utc_now
    )

    profile: Mapped[ProfileORM] = relationship(back_populates="applications")
    job_posting: Mapped[JobPostingORM] = relationship(back_populates="applications")
    resume: Mapped[ResumeORM | None] = relationship()
    cover_letter_template: Mapped[CoverLetterTemplateORM | None] = relationship()

    # Eager-loaded (lazy="selectin"): a repository reconstructing the
    # Application domain object always needs these to build
    # status_history/answer_ids, so loading them by default removes the
    # most common way to hit DetachedInstanceError after the session
    # that loaded the Application closes. See ADR-0004.
    status_events: Mapped[list[ApplicationStatusEventORM]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationStatusEventORM.sequence",
        lazy="selectin",
    )
    answer_associations: Mapped[list[ApplicationAnswerORM]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationAnswerORM.position",
        lazy="selectin",
    )


class ApplicationStatusEventORM(Base):
    """Persists ApplicationStatusEvent, a domain value object.

    `id` here is purely an ORM row identity (auto-incrementing integer) --
    it has no domain-visible counterpart, since value objects have no
    identity of their own (see domain/models/application.py). `sequence`
    is NOT independently computed by the repository: Application.status_history
    is already a correctly ordered tuple by construction (transition_to()
    only ever appends to it), so the repository simply assigns
    `sequence = index` while enumerating that tuple. This also provides
    deterministic ordering even if two events share a `changed_at`
    timestamp (e.g. sub-second transitions in tests). See ADR-0004.
    """

    __tablename__ = "application_status_events"
    __table_args__ = (
        UniqueConstraint("application_id", "sequence", name="uq_status_event_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)

    application: Mapped[ApplicationORM] = relationship(back_populates="status_events")


class ApplicationAnswerORM(Base):
    """Association object for the Application <-> Answer relationship.

    A plain SQLAlchemy `secondary=` many-to-many table cannot carry an
    extra column (like `position`) on the join row -- setting one
    requires this "association object" pattern instead. `position`
    preserves the ordering of `Application.answer_ids` (an ordered tuple
    in the domain model) across a save/load round trip; see ADR-0004 for
    why this ordering was judged worth preserving (it may matter to the
    future autofill engine, e.g. matching the order questions appeared on
    the source form).

    `answer_id`'s foreign key uses ON DELETE RESTRICT, not CASCADE:
    deleting an Answer still referenced by an Application now fails
    loudly instead of silently erasing the historical join row.
    """

    __tablename__ = "application_answers"
    __table_args__ = (
        UniqueConstraint(
            "application_id", "position", name="uq_application_answer_position"
        ),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("answers.id", ondelete="RESTRICT"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    application: Mapped[ApplicationORM] = relationship(back_populates="answer_associations")
    answer: Mapped[AnswerORM] = relationship()
