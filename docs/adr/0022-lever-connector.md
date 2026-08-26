# ADR-0022: `LeverConnector` — A Deterministic URL Contract, Not a Click

## Status

Accepted — 2026-07-09

## Context

Milestone 21 builds `LeverConnector`, the second concrete
`WebsiteConnector` (after `GreenhouseConnector`, ADR-0021). Following
the same research-before-design discipline, Lever's own published
Postings API documentation and multiple third-party API wrappers were
inspected directly before writing any code. This surfaced a genuinely
different platform characteristic from Greenhouse's, worth designing
around rather than reusing Greenhouse's click-based approach by default.

## Decisions

### 1. `matches()` checks two real domains: `jobs.lever.co` and `jobs.eu.lever.co`

Both confirmed directly from Lever's own Postings API documentation
(EU-hosted accounts use `jobs.eu.lever.co`), the same "check more than
one real domain" lesson already learned concretely in
`GreenhouseConnector` (ADR-0021 decision #1) -- here confirmed
independently for a second platform, not assumed to generalize.

### 2. `navigate_to_application_form()` is deterministic URL manipulation, never a click -- a real platform difference from Greenhouse

Lever's own Postings API documentation explicitly distinguishes
`hostedUrl` ("a URL which points to Lever's hosted job posting page")
from `applyUrl` ("a URL which points to Lever's hosted application
form"), with real, confirmed examples showing the exact relationship:
`hostedUrl = https://jobs.lever.co/{company}/{id}`,
`applyUrl = https://jobs.lever.co/{company}/{id}/apply` -- the same URL
with `/apply` appended. Because Lever's own API guarantees this
relationship, `navigate_to_application_form()` constructs the apply URL
directly (a private, pure `_append_apply_path()` function, verified
independently against four cases -- a plain URL, an already-`/apply`
URL, one with a trailing slash, and one with a query string -- before
being relied on) and calls `engine.navigate()`, never `engine.click()`.

This is recorded explicitly as a genuine platform difference, not a
missed opportunity to reuse `GreenhouseConnector`'s approach:
Greenhouse's own URL structure does not distinguish a "posting" URL
from a "form" URL the same way, so a click-based fallback was the right
design there (ADR-0021 decision #4); Lever's documented URL contract
makes deterministic navigation both possible and more reliable here.
Different platforms warranting different navigation strategies, given
different real constraints, is exactly what `WebsiteConnector`'s
per-connector design (ADR-0020) exists to accommodate.

### 3. The post-navigation verification checks for *any* `<input>`, not a specific field name -- a deliberately weaker check, and stated as such

Unlike `GreenhouseConnector`'s `input[name="first_name"]` (confirmed
directly from Greenhouse's own API docs' example HTML), Lever's help
documentation describes its form in admin-configuration language ("Full
Name" and "Email" are required by default) rather than showing raw HTML
markup. Rather than guess a specific `name="..."` attribute with more
confidence than the available evidence supports, the verification here
checks only that *some* `<input>` element exists after navigation. This
is a real, acknowledged trade-off (a weaker check than Greenhouse's),
chosen deliberately over asserting an unconfirmed selector as if it were
verified.

### 4. Same honest scope limitation as Greenhouse: embedded iframe integrations are out of scope

Lever's own public Postings API documentation states directly that
"HTML and iframe modes are for embedding" -- confirming Lever, like
Greenhouse, offers an iframe-embedded integration distinct from the
directly-hosted case this connector supports. The same reasoning as
ADR-0021 decision #3 applies: `BrowserAutomationEngine.evaluate()` runs
against the main frame only, so embedded content is invisible to it,
and cross-frame interaction remains a real, separate, unbuilt feature.
`matches()` only recognizes Lever's own hosting domains, so this
connector correctly declines the embedded case rather than mishandling it.

### 5. A real testing lesson: `file://` URLs cannot validate path-appending logic that assumes extension-less, directory-style routes

An initial manual test used `file://.../index.html` as the "posting
page" URL; appending `/apply` produced `index.html/apply`, an invalid
path -- not a bug in `_append_apply_path()` or `navigate_to_application_form()`,
but a mismatch between real Lever URLs (extension-less, server-resolved
routes) and how static file serving actually works. The formal test
suite uses a real local HTTP server (run in a background thread within
the test process, the same pattern established in Milestone 12's
`test_review_end_to_end.py`) serving a genuine directory structure
(`/acme/5ac21346/index.html` and `/acme/5ac21346/apply/index.html`),
which correctly resolves directory-style URLs the way a real web server
does. Recorded here so this specific trap (distinct from Milestone 20's
`data:` URL `#`-fragment trap) isn't rediscovered independently by a
future connector's tests.

## Alternatives Considered

- **Reusing GreenhouseConnector's click-based "check for form, click
  Apply as fallback" approach for consistency between connectors.**
  Rejected; see decision #2 -- Lever's own documented URL contract makes
  a more reliable, deterministic approach both possible and preferable
  here. Consistency between connectors is not a goal in itself when the
  underlying platforms genuinely differ.
- **Guessing a specific Lever field-name selector** (e.g. `name="name"`,
  by analogy with common web-form conventions) for the post-navigation
  check, presented with the same confidence as Greenhouse's confirmed
  selector. Rejected; see decision #3 -- overclaiming confidence not
  supported by the actual evidence found.
- **Testing the URL-manipulation logic against `file://` URLs.**
  Rejected once the mismatch was discovered; see decision #5.

## Consequences

**Positive:**
- `navigate_to_application_form()`'s Lever implementation has no
  dependency on Playwright's click/actionability timing at all for the
  common case -- purely deterministic, verified independently of any
  browser interaction (`_append_apply_path()`'s four test cases run
  with no browser involved).
- Two connectors now demonstrate that `WebsiteConnector`'s interface
  genuinely accommodates real, different per-platform navigation
  strategies, not just one connector's approach applied twice.
- The `file://` URL path-mismatch trap is documented precisely, distinct
  from Milestone 20's different `data:` URL trap, giving Milestone 22 two
  concrete, real testing lessons to avoid rediscovering.

**Trade-offs:**
- The post-navigation verification (`any <input> present`) is
  genuinely weaker than Greenhouse's connector -- a real, accepted
  limitation given the available evidence, not a shortcut taken for
  convenience.
- Lever's embedded (iframe) integration option is not supported, the
  same real capability gap as Greenhouse's, until cross-frame
  interaction exists as its own feature.

## References

- ADR-0021 -- `GreenhouseConnector`'s design, both the precedent this
  milestone follows (research-before-design, honest scope limitations)
  and the specific approach (click-based navigation) this milestone
  deliberately does not reuse, for good reason.
- ADR-0020 -- `WebsiteConnector`'s interface design, confirmed here to
  accommodate genuinely different per-platform navigation strategies.
