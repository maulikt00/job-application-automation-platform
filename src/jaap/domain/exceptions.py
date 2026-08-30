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


class BrowserAutomationError(DomainError):
    """Raised when a browser automation operation fails.

    Same reasoning as ReferentialIntegrityError, applied to
    BrowserAutomationEngine: implementations catch the underlying
    infrastructure exception (e.g. Playwright's own error types) and
    re-raise this instead, via exception chaining (`raise ... from exc`)
    so the original cause is preserved, not lost. This was deliberately
    deferred in ADR-0008/0009 until there was a real use-case-level
    consumer to design the translation against -- Milestone 10's
    AutofillApplicationUseCase is that consumer.
    """


class AIProviderError(DomainError):
    """Raised when a call to an AIProvider implementation fails.

    Same reasoning as BrowserAutomationError: ClaudeProvider and
    OllamaProvider each catch their own underlying SDK's exceptions
    (which are entirely different types between the two -- Anthropic's
    SDK shares one common base, `anthropic.AnthropicError`, while
    Ollama's `RequestError`/`ResponseError` share no common base beyond
    bare `Exception`, verified by inspecting both installed SDKs
    directly) and re-raise this instead, via exception chaining. This
    was deliberately deferred in ADR-0014/0015/0016 until there was a
    real use-case-level consumer to design the translation against --
    Milestone 16's GenerateCoverLetterUseCase is that consumer. Without
    this, a use case depending on AIProvider would need to know whether
    it's calling Claude or Ollama underneath just to catch errors
    correctly, defeating the point of the interface.
    """


class AuthenticationRequiredError(DomainError):
    """Raised by a WebsiteConnector when reaching an application's form
    requires the user to sign in first, which JAAP does not automate
    under any circumstances (a firm, deliberate boundary -- see
    ADR-0031). Distinct from BrowserAutomationError (an infrastructure
    failure) and from a connector's own generic "structure doesn't match
    my assumptions" ValueError: this specifically means "a human needs
    to authenticate before this can proceed," a genuinely different
    situation with a genuinely different possible response.

    `jaap application review --interactive` (ADR-0034) catches this
    specifically to pause and let a human sign in in the still-open
    browser window before retrying, rather than failing immediately the
    way every other error does. Found necessary via real-world
    validation against Workday (ADR-0031/0032/0033), but defined here at
    the domain level, in `WebsiteConnector`'s own interface contract,
    for any current or future connector to raise -- not specific to
    Workday's own implementation.
    """

