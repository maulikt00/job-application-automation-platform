# ADR-0038: Address Fields on Profile

## Status

Accepted — 2026-08-30

## Context

Real-world validation against a live, authenticated Workday application
form (ADR-0036) surfaced a real, concrete gap: `addressLine1`, `city`,
and `postalCode` fields had no equivalent anywhere on `Profile` at all
-- unlike the split-name limitation (ADR-0037), this wasn't a matching
problem, it was a genuine missing capability. The project owner
requested this feature directly, so it is built here as a real,
concrete addition rather than deferred to a "come back to" list.

## Decisions

### Structured fields, not a single address string

`Profile` gains six new optional fields: `address_line1`,
`address_line2`, `city`, `state`, `postal_code`, `country`. A single
combined "address" string was considered and rejected: the real
Workday form (and most real application forms generally) present these
as separate, distinct inputs, and a combined string would have no
correct way to map onto them individually.

### All fields optional, matching `phone`'s existing pattern

Not every application asks for an address, and not every person will
want to provide one upfront -- consistent with how `phone` was already
handled. No new required fields were introduced on `Profile`.

### `UpdateProfileUseCase` was added alongside address support, not deferred

There was previously no way to change data on an existing `Profile` at
all -- a real, already-identified gap (the post-Phase-4 checkpoint
review specifically noted "Profile has only create"). Building an
address-only update mechanism would have been an oddly narrow, one-off
design when a general partial update costs no more to build. `None`
means "leave this field unchanged," a different convention from
`CreateProfileUseCase` (where `None` genuinely means "no value") --
deliberate, since the CLI's own argparse defaults are already `None` for
any flag the person doesn't pass, making "None means unset" the natural
shared convention between the CLI and this use case. There is currently
no way to explicitly clear an already-set field back to `None` -- not
needed yet, not built ahead of a real need for it.

### New synonym sets in `ExactFieldMatcher`, verified against the exact real Workday field structure

`_ADDRESS_LINE1_SYNONYMS`, `_ADDRESS_LINE2_SYNONYMS`, `_CITY_SYNONYMS`,
`_STATE_SYNONYMS`, `_POSTAL_CODE_SYNONYMS`, `_COUNTRY_SYNONYMS` --
small, explicit sets matched against both name and label, following the
exact same pattern as every other synonym set in this matcher. Verified
directly against the real fields observed in validation
(`addressLine1`/"Address Line 1", `city`/"City",
`postalCode`/"Postal Code"), not invented from assumption.

### A one-off migration script, since this project has no formal migration system

`Base.metadata.create_all()` (run at the top of every CLI invocation)
only creates tables that don't exist yet -- it never alters an existing
table's columns, a fact already documented in `main.py`'s own docstring
before this change. This project has no Alembic or equivalent migration
framework, and introducing one now, for six nullable columns, would be
disproportionate to the actual need.
`scripts/migrate_add_profile_address_fields.py` instead does the
smallest thing that solves the real problem: checks the existing
`profiles` table's columns via `PRAGMA table_info`, and `ALTER TABLE
... ADD COLUMN` for whichever of the six are missing. Idempotent (safe
to run multiple times) and additive-only (never drops or renames
anything). Verified directly against a simulated pre-migration
database: existing data survives, the new columns become immediately
usable afterward, a second run correctly reports nothing left to do,
and running it against a database with no `profiles` table at all (a
brand-new install) correctly no-ops with a clear message.

## Alternatives Considered

- **A single combined "address" string field.** Rejected; see Decisions
  above -- real forms present these as separate fields.
- **An address-only update command**, rather than a general
  `UpdateProfileUseCase`. Rejected: no more expensive to build
  generally, and a general partial-update capability is a real,
  independently useful gap this closes at the same time.
- **Introducing Alembic (or an equivalent migration framework)** for
  this schema change. Rejected as disproportionate: six nullable
  columns is exactly the kind of small, additive change a single,
  targeted script handles safely without the ongoing maintenance
  overhead of a full migration framework this project has never needed
  before.
- **Silently ignoring the existing-database problem** (assuming
  everyone would just delete and recreate their database). Rejected:
  real accumulated test/validation data would be lost unnecessarily
  when a small, safe script avoids that entirely.

## Consequences

**Positive:**
- Real fields confirmed on an actual, live Workday application form are
  now genuinely autofillable, closing a concrete gap found during
  validation.
- `jaap profile update` closes an independently real, previously-flagged
  CLI-completeness gap, not just an address-specific one.
- Existing users' data is preserved and immediately usable after a
  simple, verified, one-time migration step -- no data loss, no need to
  start over.

**Trade-offs:**
- The migration script is a manual step someone must remember to run;
  there is no automatic schema-migration detection at CLI startup. This
  is an accepted, proportionate trade-off given the project's current
  size and the absence of any other schema-migration precedent to
  build on.
- `UpdateProfileUseCase` cannot yet explicitly clear a field back to
  `None` -- a real, small limitation, deferred until an actual need for
  it appears.

## References

- ADR-0036 -- the real Workday validation run that surfaced this gap.
- ADR-0037 -- the related, but structurally different, name-splitting
  feature from the same overall request.
- `presentation/cli/main.py` -- the existing, pre-dating documentation
  of `create_all()`'s "never alters existing tables" behavior that
  necessitated the migration script.
