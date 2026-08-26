# ADR-0021: `GreenhouseConnector` — First Concrete `WebsiteConnector`, Grounded in Verified Evidence

## Status

Accepted — 2026-07-09

## Context

Milestone 20 builds `GreenhouseConnector`, the first concrete
`WebsiteConnector` (ADR-0020). Before writing any code, Greenhouse's own
published documentation, API examples, and a real embedded-integration
JavaScript snippet were inspected directly (via web search) -- the same
discipline already applied to the `anthropic`/`ollama` SDKs in
Milestones 14/15. Several concrete, non-obvious facts came directly from
this research and shaped the design; none were assumed from memory.

## Decisions

### 1. `matches()` checks two real domains, not one

`boards.greenhouse.io` (the long-standing hosted-board domain,
confirmed across multiple Greenhouse support articles) and
`job-boards.greenhouse.io` (a second, newer domain, confirmed directly
from Greenhouse's own embed JavaScript: `targetDomain:
'https://job-boards.greenhouse.io'`). Checking only the first would have
silently failed to recognize job postings using the second, a real gap
that would not have been discovered without actually inspecting a real
embed script rather than assuming a single canonical domain.

### 2. `get_field_detector()` returns the existing generic `PlaywrightFormFieldDetector`, unchanged

Confirmed, not assumed: Greenhouse's own Job Board API documentation
shows the application form's example HTML using plain, native inputs --
`<input type="text" name="first_name">`, `name="last_name"`,
`name="email"` -- not custom JS-rendered widgets. There is nothing
Greenhouse-specific to detect that the generic detector would miss, so
`GreenhouseConnector` does not provide a specialized one. This is the
"mostly standard HTML, reuse the generic detector" branch of ADR-0020's
`get_field_detector()` design, now demonstrated concretely rather than
just described hypothetically.

### 3. A real, honest scope limitation: embedded (iframe) integrations are out of scope

Greenhouse also offers an integration where a company embeds their job
board and application form inside an `<iframe>` on their own domain --
confirmed directly by inspecting real embed JavaScript, which constructs
a `grnhse_iframe` element. Content inside an iframe is not part of the
top-level page's DOM: `BrowserAutomationEngine.evaluate()` runs against
the main frame only, so neither it nor the generic
`PlaywrightFormFieldDetector` can see inside one. Supporting the embedded
case would require genuine cross-frame interaction capability, which
`BrowserAutomationEngine` does not have -- a real, separate feature, not
built here. `matches()` deliberately returns `False` for a third-party
domain hosting an embedded iframe (it only matches Greenhouse's own
hosting domains), so this connector correctly declines to handle a case
it cannot support, rather than silently failing partway through one.

### 4. `navigate_to_application_form()` checks for the form first, using a real confirmed marker, before clicking anything

`input[name="first_name"]` -- taken directly from Greenhouse's own API
documentation's example form HTML, not invented -- is used as the "is
the application form already present" check. Greenhouse-hosted job post
URLs appear to typically serve the job description and the application
form on the same page (Greenhouse's own documentation describes a "job
post URL" as resolving directly to "the job post (application form)"),
so the common case is a no-op. A defensive fallback handles the case
where the description and form are genuinely separate: clicking a
visible "Apply" element via Playwright's own text-matching selector
syntax (`engine.click("text=Apply")`), then re-checking for the form and
raising a clear `ValueError` if it still isn't present, rather than
silently returning as if navigation succeeded.

### 5. A genuine testing lesson, recorded because it's a real trap, not a hypothetical one

An early manual smoke test used an inline `data:` URL with a raw `#`
character inside an `href="#"` attribute. The page loaded with
completely empty content -- not because of any bug in `click()` or
`GreenhouseConnector`, but because `#` starts a URL fragment, and
everything after it in the `data:` URI was being interpreted as a
fragment identifier rather than page content. The formal test suite uses
real temporary HTML files (`tmp_path`) for anything involving JS event
listeners instead, avoiding this entire class of encoding fragility.
Documented here so a future connector's own tests don't rediscover the
same trap independently.

### 6. No automated test for the "no Apply element exists at all" failure path

Verified manually: `engine.click("text=Apply")` on a page with no
matching text raises `BrowserAutomationError` correctly (via the
underlying ~30-second actionability timeout, since `click()` waits for a
matching element to exist). This is accepted, correct behavior -- not
enshrined as an automated test, since doing so would add a genuinely
wasteful 30-second cost to the suite for a path already confirmed to
behave reasonably, matching this project's established practice of not
writing slow tests for already-understood timeout-based failure modes
(see ADR-0011/0019's similar decisions).

## Alternatives Considered

- **Matching only `boards.greenhouse.io`.** Rejected; see decision #1 --
  a second, real, currently-used domain was found by inspecting actual
  embed JavaScript, not assumed to not exist.
- **A Greenhouse-specific `FormFieldDetector` implementation.** Rejected;
  see decision #2 -- Greenhouse's own documented form structure gives no
  reason to build one.
- **Supporting embedded iframe integrations in this milestone.**
  Rejected; see decision #3 -- a materially larger feature
  (cross-frame interaction) than this milestone's scope, and honestly
  named as such rather than attempted partially.
- **Unconditionally clicking "Apply" without first checking whether the
  form is already present.** Rejected; see decision #4 -- would add an
  unnecessary click (and its associated risk of hitting the slow
  no-match timeout) for what appears to be the common case.
- **A formal automated test for the "no Apply element" failure path.**
  Rejected; see decision #6.

## Consequences

**Positive:**
- `GreenhouseConnector`'s design decisions are each traceable to a
  specific, cited piece of real Greenhouse documentation or code, not a
  plausible-sounding guess -- the same discipline already established
  for `ClaudeProvider`/`OllamaProvider`'s SDK-grounded designs.
- The iframe-embedded limitation is named precisely, with the exact
  technical reason (`evaluate()`'s main-frame-only scope) rather than a
  vague "some cases may not work."
- A real, reusable testing lesson (the `data:` URL `#`-fragment trap) is
  now documented for future connector work to avoid independently
  rediscovering.

**Trade-offs:**
- Companies using Greenhouse's embedded (iframe) integration -- likely a
  meaningful fraction of real-world Greenhouse usage -- are not
  supported by this connector. `matches()` correctly declines rather
  than mishandling them, but this is a real capability gap, not just a
  theoretical one, until cross-frame interaction is built as its own
  feature.

## References

- ADR-0020 -- `WebsiteConnector`'s interface design, in particular the
  `get_field_detector()` selection/composition pattern this connector
  is the first real example of.
- ADR-0009/0010/0011 -- the precedent for verifying real SDK/platform
  behavior directly rather than assuming it, and for not writing
  automated tests around already-understood slow timeout paths.
