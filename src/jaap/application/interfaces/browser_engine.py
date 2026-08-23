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
earlier draft had sketched form detection as a new engine method, which
would have coupled a supposedly generic automation toolkit to
forms-specific domain knowledge. See docs/adr/0009-form-field-detector.md.

`fill()`, `check()`, and `select_option()` (added Milestone 10) are the
three action primitives an autofill engine needs -- still generic (any
web automation needs "fill a field" or "check a box," not just job
applications), following the exact same reasoning as `evaluate()`.

Exception translation (deferred in ADR-0008/0009 until there was a
concrete consumer): every operational method here can raise
`jaap.domain.exceptions.BrowserAutomationError` if the underlying
browser operation fails. Implementations preserve the original
exception via chaining (`raise ... from exc`) -- see
docs/adr/0010-autofill-engine.md. The `RuntimeError` raised by calling
an operation before `launch()`/after `close()` is a separate, ordinary
programmer-error guard, not part of this translation -- it was never a
Playwright-raised error to begin with.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, Self


class BrowserAutomationEngine(Protocol):
    def launch(self) -> None:
        """Start the browser. Must be called before other operations."""
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

    def fill(self, selector: str, value: str) -> None:
        """Fill a text-like field (text, email, tel, textarea, etc.)
        matching `selector` with `value`."""
        ...

    def check(self, selector: str, checked: bool) -> None:
        """Set a checkbox or radio button matching `selector` to `checked`."""
        ...

    def select_option(self, selector: str, value: str) -> None:
        """Select the option with the given `value` in a <select> element
        matching `selector`."""
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
