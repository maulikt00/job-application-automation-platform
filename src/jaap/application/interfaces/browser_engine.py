"""BrowserAutomationEngine interface (port).

Defined as a Protocol, not ABC -- same reasoning as the repository
interfaces (ADR-0005): structural typing means a test double satisfies
this interface just by matching method shapes, no inheritance required;
mypy verifies conformance statically.

Deliberately does NOT expose raw Playwright objects (Page, ElementHandle)
to callers. This is the decision that actually makes the abstraction
swappable rather than a Playwright-shaped wrapper in name only -- if
navigate() returned a Playwright Page directly, every future caller
(Milestone 9's FormFieldDetector, Milestone 10's autofill engine) would
depend on Playwright's API directly, not on this interface. The
interface stays at the level ARCHITECTURE.md already describes: actions
and structured data -- never raw library objects.

`evaluate()` (added Milestone 9) is the interface's one generic
extension point for extracting structured data from a live, rendered
page. It is deliberately NOT a forms-specific method -- form-field
detection logic (what counts as a "field", label-guessing, which types
to exclude) lives entirely in FormFieldDetector
(application/interfaces/form_field_detector.py), composed with this
engine via constructor injection, not added here. Keeping this engine
generic (it still knows nothing about job applications specifically)
was a deliberate correction made while designing Milestone 9 -- an
earlier draft of this ADR-adjacent plan had sketched form detection as
a new engine method, which would have coupled a supposedly generic
automation toolkit to forms-specific domain knowledge. See
docs/adr/0009-form-field-detector.md.

No dedicated exception translation yet, unlike ReferentialIntegrityError
in domain/exceptions.py (Milestone 5): there is no use-case-level
consumer of this interface yet to design a translation against --
that's Milestone 10's autofill engine. Revisit then, following the same
"don't build an abstraction without a concrete consumer" discipline
ADR-0006 already established for deferring DTOs.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Self


class BrowserAutomationEngine(Protocol):
    def launch(self) -> None:
        """Start the browser. Must be called before navigate()/screenshot()."""
        ...

    def navigate(self, url: str) -> None:
        """Navigate the current page to `url`."""
        ...

    def evaluate(self, script: str) -> Any:
        """Run JavaScript `script` against the current, live, rendered page
        and return its result.

        The result MUST be JSON-compatible (str, int, float, bool, None,
        list, or dict). Implementations enforce this with a JSON
        round-trip and raise ValueError if it fails -- verified against a
        real browser: Playwright's own serialization already converts
        genuinely non-serializable JS values (DOM nodes, functions) into
        safe string placeholders before they ever reach Python, so this
        check is a defensive backstop for edge cases like NaN/Infinity
        (which Python's json module permits by default, unlike standard
        JSON) rather than the primary defense against a live DOM handle
        leaking out. Running against the live DOM (not a static HTML
        snapshot) matters because real application forms are often
        JS-rendered SPAs -- a static parser would miss content that only
        exists after client-side rendering.
        """
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
