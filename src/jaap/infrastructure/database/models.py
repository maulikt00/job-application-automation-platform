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
  - Foreign keys use ON DELETE CASCADE; SQLite only enforces this when
    "PRAGMA foreign_keys=ON" is set per-connection, which session.py wires
    up automatically.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
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


# Many-to-many join table for Application <-> Answer (see Milestone 2's
# domain-model diagram: this relationship needs a join table once persisted).
# A plain Table + Column is used here (not mapped_column, which only
# applies inside an ORM-mapped class body) since this table has no
# corresponding domain object of its own -- it's purely a join table.
application_answers = Table(
    "application_answers",
    Base.metadata,
    Column("application_id", Uuid, ForeignKey("applications.id", ondelete="CASCADE"), primary_key=True),
    Column("answer_id", Uuid, ForeignKey("answers.id", ondelete="CASCADE"), primary_key=True),
)


class ApplicationORM(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_posting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True
    )
    cover_letter_template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("cover_letter_templates.id", ondelete="SET NULL"), nullable=True
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
    status_events: Mapped[list[ApplicationStatusEventORM]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="ApplicationStatusEventORM.sequence",
    )
    answers: Mapped[list[AnswerORM]] = relationship(
        secondary=application_answers, backref="applications"
    )


class ApplicationStatusEventORM(Base):
    """Persists ApplicationStatusEvent, a domain value object.

    `id` here is purely an ORM row identity (auto-incrementing integer) --
    it has no domain-visible counterpart, since value objects have no
    identity of their own (see domain/models/application.py). `sequence`
    provides deterministic ordering even if two events share a
    `changed_at` timestamp (e.g. sub-second transitions in tests).
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
