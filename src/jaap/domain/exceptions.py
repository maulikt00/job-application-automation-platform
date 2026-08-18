"""Domain-level exceptions.

These represent violations of *domain invariants* -- rules that protect an
entity's own internal consistency, independent of any particular workflow.
They are distinct from business process errors (e.g. "a resume must be
attached before submission"), which are raised by the application layer's
use cases instead. See docs/adr/0002-progressive-application-lifecycle.md
for the reasoning behind this split.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Import only for type hints; avoids a circular import at runtime
    # since application.py imports InvalidStatusTransitionError from here.
    from jaap.domain.models.application import ApplicationStatus


class DomainError(Exception):
    """Base class for all domain-layer errors.

    Catching `DomainError` lets calling code handle "something about this
    entity's own invariants was violated" as a category, without needing
    to know about every specific domain exception that exists.
    """


class InvalidStatusTransitionError(DomainError):
    """Raised when an Application attempts a structurally invalid status
    transition (e.g. going straight from DRAFT to OFFER).

    This is a domain invariant, not a business rule: it fires regardless
    of *why* the transition was attempted. Business rules about whether a
    structurally-valid transition should currently be *permitted* (e.g.
    "you can't submit without a resume") live in the application layer's
    use cases, not here.
    """

    def __init__(
        self,
        current_status: ApplicationStatus,
        attempted_status: ApplicationStatus,
    ) -> None:
        self.current_status = current_status
        self.attempted_status = attempted_status
        super().__init__(
            f"Cannot transition Application from '{current_status.value}' "
            f"to '{attempted_status.value}'."
        )


class ReferentialIntegrityError(DomainError):
    """Raised when an operation would violate a referential integrity
    constraint enforced by the persistence layer -- e.g. deleting a
    Resume, CoverLetterTemplate, or Answer that is still referenced by
    an Application (see ADR-0004's RESTRICT foreign keys).

    Repositories catch the underlying infrastructure exception (e.g.
    SQLAlchemy's IntegrityError) and re-raise this instead, so the
    application layer only ever handles exceptions in the domain's own
    vocabulary -- it never needs to know what database library, if any,
    is underneath (see ARCHITECTURE.md's dependency rule).
    """
