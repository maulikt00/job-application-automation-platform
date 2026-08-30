# ADR-0034: `--interactive` — A Generic Pause-and-Retry Mechanism for Sign-In Walls

## Status

Accepted — 2026-08-29

## Context

Following ADR-0031/0032/0033's findings (Workday's mandatory sign-in
requirement, confirmed on two independent tenants), the project owner
asked directly: could JAAP pause an application, let a human sign in
themselves, and then resume automation?

This was discussed explicitly, not just implemented, because it
initially sounds close to the credential-automation boundary this
project has held firmly since ADR-0031 -- but it is a genuinely
different thing. Every prior refusal has been about *JAAP itself*
entering credentials or creating an account. What was actually being
asked for is the opposite: JAAP pausing and getting out of the way
while a *human*, in their own hands, on their own account, does the
part JAAP correctly won't do -- then JAAP resumes. That distinction was
treated as real and load-bearing for this design, not glossed over.

Two shapes were discussed before committing to one:

- **Option A**: the same command blocks, with the browser held open,
  prompting the human to sign in and press Enter to continue. Simple;
  no persistence; no new failure modes around detached browser
  sessions.
- **Option B**: a two-command model with a detached, reconnectable
  browser (via Chrome's remote-debugging protocol), letting a human
  sign in on their own schedule across separate command invocations.
  Meaningfully more engineering, with real, un-worked-through questions
  (what if the window closes, what if the session expires between
  commands, where does handoff state live).

Option A was chosen deliberately, for two reasons discussed directly:
first, it is simpler and sufficient for the actual problem (getting
past a wall *once*, this session); second, and more importantly, this
project still has never observed a real, past-the-wall Workday form
(ADR-0033's own honest caveat) -- building Option B's added complexity
before even confirming the rest of the pipeline works once would be
exactly the kind of premature architecture the post-Phase-4 checkpoint
review warned against.

A further, more fundamental design question was also raised and
answered before implementation: should this recurring cost (signing in
again on every single run, since `SECURITY.md` commits to never
persisting a session between runs) instead be solved by persistent
session storage? This was deliberately deferred, not folded into this
ADR: it directly reopens a stated security commitment, deserves its own
focused conversation (where cookies would live, encryption, shared-machine
exposure, expiry), and there is not yet real evidence (only a
prediction) of how costly the recurring sign-in actually is in practice.

## Decisions

### 1. A new, specific domain exception: `AuthenticationRequiredError`

Added to `domain/exceptions.py` as a `DomainError` subtype, distinct
from `BrowserAutomationError` (an infrastructure failure) and from a
connector's own generic "structure doesn't match my assumptions"
`ValueError`. This specifically means "a human needs to authenticate
before this can proceed" -- a genuinely different situation warranting
a genuinely different response, not something to infer from message
text.

### 2. Formalized as part of `WebsiteConnector`'s own interface contract, not a Workday-specific detail

`application/interfaces/website_connector.py`'s docstring and
`navigate_to_application_form()`'s own docstring now state that a
connector *should* raise `AuthenticationRequiredError` for this
situation -- so any current or future connector (Greenhouse, Lever, a
fourth platform) that encounters the same wall raises the same,
specific exception, rather than each inventing its own ad-hoc signal.
`WorkdayConnector` is updated to raise it (previously a plain
`ValueError`, per ADR-0031); Greenhouse and Lever are deliberately left
unchanged, since neither has ever actually encountered a real sign-in
wall in validation -- speculatively adding detection for a situation
neither platform has shown evidence of would be building ahead of
evidence, the same discipline this whole validation effort has followed
throughout.

### 3. The pause-and-retry logic lives in the CLI's composition root, not in any connector

`_handle_review` (in `application_commands.py`) catches
`AuthenticationRequiredError` around the `navigate_to_application_form()`
call. This is a presentation-layer decision, correctly: "how to interact
with a human synchronously" is not a connector's or a use case's
concern -- Clean Architecture's dependency rule places this exactly
where it belongs. No changes were needed to `AutofillApplicationUseCase`
or `ReviewApplicationUseCase` at all; the entire mechanism is contained
between the connector raising the exception and the CLI deciding what
to do about it.

### 4. `--interactive` is opt-in; default behavior is completely unchanged

Without the flag, `AuthenticationRequiredError` propagates exactly like
any other error today (caught by `main.py`'s existing `DomainError`
handling, displayed as a clean one-line message). With the flag, the
CLI instead prints the error, tells the human a browser window is open,
and loops on `input()`: pressing Enter retries
`navigate_to_application_form()` on the same, still-open page; typing
`q` gives up and re-raises the original error. The loop continues
across multiple failed attempts (a real sign-in flow can itself be
multi-step -- email, then password, then a 2FA prompt), rather than
allowing only a single retry.

### 5. A hard, fail-fast pre-flight guard: `--interactive` requires `JAAP_HEADLESS=false`

Checked before a browser is even launched. A headless browser has no
visible window for a human to sign in with; without this guard,
`--interactive` against a headless session would silently appear to
hang with nothing to interact with. Verified directly: this raises
immediately, with no browser ever constructed.

### 6. This is a deliberate, narrow, explicit exception to ADR-0012's "no live handoff" norm -- not a reversal of it

ADR-0012 established that `jaap application review` does not leave the
browser open for a live handoff; the screenshot is the reviewable
artifact instead. `--interactive` does momentarily hold the browser
open, but only for this one, specific, opt-in situation, and the
browser still closes at the end of the same command either way -- there
is still no persistent session, no new standing capability, and the
default (non-interactive) behavior is byte-for-byte unchanged.

## Testing Strategy — and a Real Sandbox Constraint Found Along the Way

Two deliberately different approaches, found necessary partway through
building this:

- The pre-flight guard is tested through the real CLI entry point
  (`main()`) -- it needs no real browser at all, since it must fail
  before one is ever constructed.
- The actual retry-loop logic (`_wait_for_manual_sign_in()`) is tested
  directly, as an isolated unit, with a minimal fake connector -- NOT
  through the full CLI with a real browser.

This second choice was not the original plan. An end-to-end version
using a real headed Chromium instance was attempted first, and failed
with "Missing X server or $DISPLAY" -- this sandboxed development
environment has no X server, so a genuinely headed (non-headless)
Playwright browser cannot launch here at all. `xvfb-run` (a virtual
X server) was confirmed to work around this directly, but was rejected
as the actual fix: requiring a new system dependency (`xvfb`) for the
whole test suite, just to cover one mechanism's tests, was judged not
worth it, especially since the retry loop's own logic (call
`navigate_to_application_form()` again, handle `'q'`, loop on repeated
failures) does not need a real browser to verify correctly -- a fake
connector that behaves in a controlled way is sufficient, and is what
was used instead.

## Alternatives Considered

- **Option B (detached, reconnectable browser).** Rejected for now; see
  Context above.
- **Persistent session storage across runs**, removing the recurring
  sign-in cost entirely. Deliberately deferred as its own, separate,
  future conversation; see Context above.
- **A single-retry limit** rather than a loop. Rejected: a real sign-in
  flow is often itself multi-step, and a human actively driving this
  interactively should not need to re-run the whole command just
  because one intermediate step (e.g. a 2FA prompt) wasn't finished
  within a single retry.
- **Testing the retry loop through a real, headed Chromium instance**,
  accepting `xvfb` as a new test-suite dependency. Rejected; see
  Testing Strategy above.

## Consequences

**Positive:**
- JAAP can now, for the first time, actually get past a sign-in wall in
  practice -- with a human doing the sign-in themselves, opt-in, and
  with the default behavior completely unaffected for anyone not using
  the flag.
- The mechanism is genuinely general, not Workday-specific: formalized
  at the `WebsiteConnector` interface level, so any future connector
  encountering the same wall gets this behavior by raising the same
  exception, not by reimplementing it.
- A real, honest engineering finding along the way (no X server in this
  sandbox) was investigated properly (confirmed the actual cause,
  confirmed a workaround exists) before being designed around, rather
  than assumed or ignored.

**Trade-offs:**
- The recurring cost this ADR explicitly did not solve remains: every
  future `jaap application review` run against the same gated posting
  will hit the same wall again, since no session persists between runs.
  This is a known, accepted trade-off pending real usage data, not an
  oversight.
- Whether this actually gets JAAP past Workday's real form for the
  first time -- and whether `WorkdayFormFieldDetector`'s field detection
  then works correctly against it -- remains unverified; ADR-0033's own
  honest gap is unaffected by this feature and still needs real-world
  confirmation.

## References

- ADR-0031/0032/0033 -- the Workday findings that directly motivated
  this feature.
- ADR-0012 -- the "no live handoff" norm this feature deliberately,
  narrowly, and explicitly departs from for one specific situation.
- ADR-0020 -- `WebsiteConnector`'s own interface design and safety
  boundary discipline, extended here with a new, formalized exception
  type.
