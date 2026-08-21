# ADR-0008: Browser Automation Engine Interface and Playwright Version Pin

## Status

Accepted — 2026-07-09

## Context

Milestone 8 built the first infrastructure component with no relationship
to the database: `BrowserAutomationEngine`, the abstraction Phase 2's
remaining milestones (form detection, autofill, resume upload, human
review) all build on. Several decisions needed resolving: how the
interface should be defined and scoped, whether to use Playwright's
sync or async API, how much of Playwright's own object model the
interface should expose, and -- discovered only during this milestone's
clean-venv verification, not while writing code -- a real version-pin
problem.

## Decisions

### 1. `Protocol`, not `ABC`

Same reasoning as ADR-0005's repository interfaces: structural typing
means a test double satisfies `BrowserAutomationEngine` by matching
method shapes, no inheritance required; mypy verifies conformance
statically (confirmed directly for `PlaywrightBrowserEngine`).

### 2. Playwright's sync API, not async

The rest of this codebase -- repositories, use cases, the CLI -- is
entirely synchronous. Introducing async here would mean either mixing
sync/async across the whole future call stack (use case -> browser
engine -> Playwright) or wrapping every browser call in `asyncio.run()`.
Playwright's sync API is fully supported for this exact use case. If a
future async consumer (e.g. Phase 5's FastAPI) needs this, sync
Playwright calls can be wrapped in a thread pool executor at that
boundary rather than rewriting this layer now for a need that doesn't
exist yet.

### 3. The interface never exposes raw Playwright objects

`BrowserAutomationEngine.navigate()` returns nothing, not a Playwright
`Page`. This is the decision that makes the abstraction genuinely
swappable rather than a Playwright-shaped wrapper in name only -- if a
`Page` object leaked out, every future caller (Milestone 9's form
detector, Milestone 10's autofill engine) would depend on Playwright's
API directly, not on this interface. The interface stays at the level
`ARCHITECTURE.md` already describes: actions, and starting in Milestone
9, structured data -- never raw library objects.

### 4. Milestone 8's scope: `launch()`, `navigate()`, `close()`, `screenshot()`

Matches the roadmap's stated scope for this milestone, plus
`screenshot()` -- included now (not deferred to Milestone 12) since it's
simple, immediately verifiable against a real browser, and directly
useful later for the human review gate. `click()`/`fill()`/file-upload
are deliberately not part of this milestone's interface; they belong to
Milestone 10/11 once there's a concrete form-filling consumer to design
their exact shape against.

### 5. No exception translation yet

Unlike `ReferentialIntegrityError` (ADR-0005), `BrowserAutomationEngine`
does not yet translate Playwright's own exceptions into a
project-specific one. There is no use-case-level consumer of this
interface yet (that's Milestone 10's autofill engine) to design a
translation against -- following the same "don't build an abstraction
without a concrete consumer" discipline ADR-0006 established for
deferring DTOs. Revisit when Milestone 10 needs it.

Basic defensive guards exist regardless: calling `navigate()` or
`screenshot()` before `launch()`, or after `close()`, raises a plain
`RuntimeError` with a clear message. This is ordinary programmer-error
handling, not business-rule or domain-invariant translation, so it
doesn't conflict with the deferral above.

### 6. `headless` is a new `Settings` field, not hardcoded

Defaults to `True`. A developer can set `JAAP_HEADLESS=false` locally to
watch the browser interactively while developing Milestone 9/10's form
detection and autofill logic.

### 7. `playwright` is pinned tightly (`==1.56.0`), not a version range

Originally scoped as `playwright>=1.45,<2.0` (matching every other
dependency's range-based pinning style). A clean-venv verification --
the same discipline that caught real bugs in Milestones 4 and 5 --
caught a genuine regression: a freshly installed `1.62.0` raised
`"using Playwright Sync API inside the asyncio loop"` the moment
`PlaywrightBrowserEngine.launch()` called `sync_playwright().start()`,
even with no async test plugin installed anywhere in the environment.
Every test that never actually launched a browser (the two guard-clause
tests) passed regardless of version; every test that did, failed on
`1.62.0` and passed on `1.56.0`. Root cause not fully diagnosed --
plausibly a change in how a newer Playwright version detects an active
asyncio event loop, and something in this specific test environment
trips a false positive that `1.56.0`'s detection logic didn't. Pinning
tightly is the honest, verified-safe choice until the actual cause is
understood; a wide range would have silently reintroduced this exact
failure for anyone installing fresh later, including this project's own
future clean-venv checks.

## Alternatives Considered

- **Async Playwright API.** Rejected; see decision #2.
- **Exposing Playwright's `Page` object from `navigate()`.** Rejected;
  see decision #3.
- **A dedicated `BrowserAutomationError` now**, mirroring
  `ReferentialIntegrityError`. Rejected for now; see decision #5.
- **Leaving `playwright` as a version range** and treating the
  clean-venv failure as environment noise to route around (e.g. skip
  browser tests in CI). Rejected: the failure is real and reproducible,
  not flaky, and a version range that can silently regress a real
  capability is worse than a tight pin with a documented reason.

## Consequences

**Positive:**
- Milestone 8's tests run against a real, actual headless Chromium
  instance, not mocks -- meaningfully stronger verification than
  mocking Playwright's API would have provided, made possible by this
  sandbox having Chromium pre-provisioned.
- The composition root pattern (constructor-injected `Settings`, no
  global state) extends cleanly to a second infrastructure component
  beyond the database layer.

**Trade-offs:**
- The tight version pin means a future Playwright security/bugfix
  release won't be picked up automatically the way `SQLAlchemy>=2.0,<3.0`
  or similar ranges allow -- someone needs to deliberately re-verify and
  bump this pin later, ideally once the asyncio-loop-detection root
  cause is actually understood rather than just worked around.
- No exception translation yet means Milestone 10's autofill engine will
  need to make this decision properly when it becomes the first real
  consumer -- deferred deliberately, not overlooked.

## References

- ADR-0005 -- the repository `Protocol` pattern and exception-translation
  precedent this milestone follows/defers against.
- ADR-0006 -- the "don't build without a concrete consumer" discipline
  applied here to both DTOs (there) and exception translation (here).
- ADR-0001 -- the "AI never touches browser automation" structural
  boundary this interface's existence is the first concrete piece of.
