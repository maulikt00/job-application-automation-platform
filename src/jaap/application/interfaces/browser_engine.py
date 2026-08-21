"""BrowserAutomationEngine interface (port).

Defined as a Protocol, not ABC -- same reasoning as the repository
interfaces (ADR-0005): structural typing means a test double satisfies
this interface just by matching method shapes, no inheritance required;
mypy verifies conformance statically.

Deliberately does NOT expose raw Playwright objects (Page, ElementHandle)
to callers. This is the decision that actually makes the abstraction
swappable rather than a Playwright-shaped wrapper in name only -- if
navigate() returned a Playwright Page directly, every future caller
(Milestone 9's form detector, Milestone 10's autofill engine) would
depend on Playwright's API directly, not on this interface. The
interface stays at the level ARCHITECTURE.md already describes: actions
and, starting in Milestone 9, structured data -- never raw library
objects.

No dedicated exception translation yet, unlike ReferentialIntegrityError
in domain/exceptions.py (Milestone 5): there is no use-case-level
consumer of this interface yet to design a translation against --
that's Milestone 10's autofill engine. Revisit then, following the same
"don't build an abstraction without a concrete consumer" discipline
ADR-0006 already established for deferring DTOs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, Self


class BrowserAutomationEngine(Protocol):
    def launch(self) -> None:
        """Start the browser. Must be called before navigate()/screenshot()."""
        ...

    def navigate(self, url: str) -> None:
        """Navigate the current page to `url`."""
        ...

    def screenshot(self, path: Path) -> None:
        """Save a screenshot of the current page to `path`.

        Creates parent directories if they don't exist, matching how
        logging_config.py and session.py already handle directories they
        need (see ADR-0003/Milestone 3's logging setup).
        """
        ...

    def close(self) -> None:
        """Shut down the browser and release all resources.

        Safe to call more than once -- a second call is a no-op, not an
        error, since cleanup code (e.g. a `finally` block) shouldn't need
        to track whether close() already ran.
        """
        ...

    def __enter__(self) -> Self:
        ...

    def __exit__(self, *exc_info: object) -> None:
        ...
