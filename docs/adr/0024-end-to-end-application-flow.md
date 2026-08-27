# ADR-0024: End-to-End Application Flow — Closing the Connector-Wiring Gap

## Status

Accepted — 2026-07-09

## Context

Milestone 23 closes Phase 4 with the roadmap's stated goal: "profile +
resume + AI cover letter + connector + human review, exercised against
a real (test) posting on each supported platform." Investigating what
this actually required surfaced a real, previously-undiscovered gap:
`jaap application review`'s handler (`_handle_review`) had, since
Milestone 12, always constructed `PlaywrightFormFieldDetector` directly
-- nothing in the CLI ever constructed or consulted a `WebsiteConnector`
at all. Milestones 19-22 built three working connectors that were never
actually reachable from real usage. This ADR is where that gap closes.

## Decisions

### 1. `infrastructure/connectors/registry.py`: a plain list-and-check, not a plugin framework

`find_connector(url) -> WebsiteConnector | None` checks each registered
connector's `matches()` in order and returns the first hit, or `None`.
Adding a fourth connector means adding one line -- consistent with this
project's repeated preference (ADR-0006 and others) for the smallest
mechanism that solves the actual problem, not a more elaborate
registration/discovery system nothing currently needs.

### 2. `_handle_review` now consults the registry; `None` is the expected, ordinary case, not an error

If a connector matches, `navigate_to_application_form()` runs and its
`get_field_detector()` result is used instead of the generic detector;
the detected platform is printed (`"Detected platform: greenhouse"`).
If no connector matches -- the common case for any platform this project
doesn't yet have a connector for -- the existing generic-detector
behavior is unchanged, verified directly by a dedicated regression test
asserting `"Detected platform"` does NOT appear in that case.

### 3. A real, related gap found and fixed while wiring this in: `main.py` never caught `ValueError`

Every connector's `navigate_to_application_form()` (and
`BrowserAutomationEngine.evaluate()`'s own JSON-validation check) raises
plain `ValueError` for its own expected failure modes. `main.py`'s
top-level handler only caught `(UseCaseError, DomainError)` -- neither
category. This means a connector's own clearly-designed error would
previously have surfaced as a raw, unhandled Python traceback rather
than the clean one-line message every other expected failure produces.
Fixed by adding `ValueError` to the top-level catch clause.

### 4. Testing strategy: separate "does a connector work" from "does the CLI use one" -- and avoid baking a fragile DNS dependency into the permanent suite

Whether `GreenhouseConnector.matches()` correctly recognizes real
Greenhouse domains is already verified thoroughly in
`test_greenhouse_connector.py` (Milestone 20) and `test_registry.py`
(this milestone). What was NOT yet tested anywhere was whether
`_handle_review` actually calls `navigate_to_application_form()` and
uses `get_field_detector()`'s result. `test_review_connector_wiring_end_to_end.py`
tests exactly this, using `unittest.mock.patch` to make `find_connector`
return a REAL `GreenhouseConnector` instance regardless of the test
URL -- not a fake/stub standing in for it, so its real navigation and
detection logic still runs, just without needing the test URL to
actually resolve as `boards.greenhouse.io` over real or faked DNS.

This was a deliberate choice made after directly trying the alternative
during manual verification: temporarily redirecting real connector
domains to `127.0.0.1` via `/etc/hosts` genuinely worked (confirmed by
hand, described in decision #5) but requires root and modifies
system-wide state -- a reasonable thing to do once, by hand, to prove
the fix, but not something to depend on in a portable, permanent test
suite other environments (CI, other developers' machines) will run.

### 5. A genuine, real end-to-end proof was performed by hand before any automated test was written

Using a temporary `/etc/hosts` redirect (`boards.greenhouse.io -> 127.0.0.1`)
and a real local server, the actual CLI (`jaap application review`) was
run against a URL that genuinely resolves as a real Greenhouse domain,
confirming `"Detected platform: greenhouse"` appears and autofill uses
the connector's own detector -- the same proof the automated tests
provide, performed once by hand first, exactly the "prove it actually
works before/alongside writing the formal test" discipline this project
has followed since Milestone 8. The `/etc/hosts` changes were reverted
immediately afterward.

A sandbox environment reset occurred partway through this milestone's
work (the working directory was unexpectedly cleared). Verified before
continuing: the project was fully recoverable from the last packaged
milestone zip, and a complete test run (358 passing, the count as of
Milestone 22) confirmed the recovered state was correct before
re-applying this milestone's changes -- recorded here as a real event
in this milestone's history, not smoothed over.

### 6. The comprehensive test ties every piece together, matching the roadmap's literal wording

`test_full_application_flow_end_to_end.py` runs, through the real CLI
wherever possible: profile creation, resume upload, connector-aware
review (patched connector, same reasoning as decision #4), and
submission with an AI-generated cover letter as a one-off override --
then verifies the resulting `SubmittedContentSnapshot` in the database
directly. The AI cover letter step calls `GenerateCoverLetterUseCase`
directly with a fake `AIProvider` (mirroring Milestone 16's own test
suite), not through the CLI, since `jaap cover-letter generate`
constructs a real `ClaudeProvider` and no real Claude API access exists
in this test environment, nor should a portable test suite depend on one.

## Alternatives Considered

- **Baking the `/etc/hosts` redirect into the automated test suite.**
  Rejected; see decision #4 -- proven correct once by hand (decision #5)
  is sufficient; a permanent, portable suite should not require root or
  modify system-wide DNS resolution.
- **Testing connector selection with a fake/stub `WebsiteConnector`**
  rather than a real one. Rejected: using the real `GreenhouseConnector`
  instance means this test also incidentally re-verifies that
  connector's real navigation/detection logic still works correctly when
  invoked through the actual CLI flow, not just in isolation.
- **Routing the AI cover letter step through the CLI's real
  `ClaudeProvider`.** Rejected; no real API access in this environment,
  and a portable test suite should not depend on one existing.

## Consequences

**Positive:**
- The three connectors built in Milestones 19-22 are now genuinely
  reachable from real usage, not just correct in isolation -- confirmed
  both by hand (a real `/etc/hosts`-based run) and by an automated
  regression test.
- A connector's own designed failure mode (a `ValueError` when its
  assumptions don't hold) now surfaces as a clean, readable CLI error
  instead of a raw traceback -- a real, generally-applicable fix, not
  connector-specific.
- One comprehensive test now proves the full, real story the roadmap
  asked for: profile, resume, AI-generated content, a connector, and
  submission, composing correctly together end to end.

**Trade-offs:**
- The formal test suite's connector-wiring tests rely on patching
  `find_connector` rather than genuine DNS-level domain matching --
  correct and sufficient given decision #4's reasoning, but means the
  "does a URL string actually resolve to the right connector, and does
  using that connector actually work through the CLI" chain is verified
  across two separate tests (`test_registry.py` /
  `test_greenhouse_connector.py`, and this milestone's wiring tests)
  rather than in a single, maximally end-to-end one.

## References

- ADR-0020/0021/0022/0023 -- the `WebsiteConnector` interface and its
  three concrete implementations, whose real-usage gap this milestone
  closes.
- ADR-0007 -- `main.py`'s centralized exception-translation design,
  which this milestone's `ValueError` fix extends.
