# Security Policy

JAAP is an early-stage, single-user, learning-focused project (see
[README.md](README.md) and [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md)).
This document describes what the project actually does today to help
you avoid leaking secrets or personal data, and where the current gaps
are. It does not claim protections that aren't actually implemented.

## API Keys and Credentials

**Never commit API keys, credentials, or `.env` files.** JAAP's AI
provider integrations (Phase 3: `ANTHROPIC_API_KEY`) and any future
credential-bearing config are loaded via
`infrastructure/config/settings.py`'s `Settings` object, which reads
from environment variables or a local `.env` file — never from a
committed file.

- `.env` is already listed in [`.gitignore`](.gitignore) (`.env`,
  `*.env.local`, `secrets/`) — confirm this stays true if you ever
  restructure how secrets are loaded.
- [`.env.example`](.env.example) is the template to copy from; it ships
  with every credential field blank (`ANTHROPIC_API_KEY=`) specifically
  so there's nothing to accidentally leave populated.
- If you ever commit a real secret by mistake: rotating/revoking the
  credential at its source (e.g., regenerating the Anthropic API key)
  is the only real fix. Removing the commit from your local branch
  before pushing does not undo an already-pushed exposure, and rewriting
  already-pushed history to scrub it is unreliable once anyone else may
  have fetched it — treat a pushed secret as compromised and rotate it,
  don't rely on history rewriting alone.

**Current gap, stated plainly:** `Settings.anthropic_api_key` is a plain
string field with no secret-scrubbing (no `SecretStr` type, no logging
redaction). Printing a `Settings` instance directly (e.g. `print(settings)`
or logging it whole) will currently render the raw API key in plaintext.
Avoid logging or printing the full `Settings` object; log individual
non-secret fields instead if you need to debug configuration. This is a
known limitation worth hardening later (e.g. via Pydantic's `SecretStr`),
not yet done as of this document.

## Ollama / Local Models

Ollama (`OLLAMA_HOST`, default `http://localhost:11434`) runs locally and
doesn't require an API key by default. If you expose an Ollama instance
beyond localhost (e.g., on a shared network), be aware it typically has
no built-in authentication of its own — that's an Ollama/network
configuration concern outside JAAP's control, not something this project
adds protection for.

## Browser Automation: Credentials and Session Data

`BrowserAutomationEngine` (Playwright-backed) launches a fresh, isolated
browser context for each run — it does not currently persist cookies,
saved logins, or session data between invocations. This means:

- JAAP does not currently support (and does not attempt) staying logged
  into a job site across runs. Each `jaap application review` invocation
  starts a clean browser session.
- If a job application flow requires you to log in, that login isn't
  saved by JAAP anywhere. No login credentials for third-party sites are
  collected, stored, or transmitted by this project as it exists today.
- Per [ADR-0012](docs/adr/0012-human-review-gate.md), there is no
  `click()`/`submit()` capability anywhere in this codebase — JAAP
  cannot submit an application on your behalf, which also means it never
  handles whatever credentials a submission flow might require.

## Logging Does Not Automatically Redact Secrets

`infrastructure/config/logging_config.py`'s JSON file handler
(`_JsonFormatter`) logs exactly four fields per entry: timestamp, level,
logger name, and message (plus exception info, if present) — it does
**not** scan message content for anything resembling a secret before
writing it. If application code ever logs a string that happens to
contain an API key, password, or similar, it will appear in plaintext in
the rotating log file (`<log_dir>/jaap.log` and its rotated backups).
Be deliberate about what you log; don't log full request/response
payloads to third-party APIs (Phase 3) without checking they don't embed
credentials.

## Application and Job Data May Be Sensitive

`Profile`, `Resume`, `Answer`, and `Application` (including the
[`SubmittedContentSnapshot`](docs/adr/0013-submitted-content-snapshot.md)
introduced to preserve what was actually submitted) can contain real
personal information: your name, contact details, employment history,
and free-text answers to application questions. This data is stored
locally in a SQLite file (`data/jaap.db` by default, already
`.gitignore`d) and in resume files under whatever path you configure.
Treat that database file and your resume files with the same care you'd
give any file containing personal/employment data — this project does
not currently encrypt the SQLite database at rest, and does not
implement any access control beyond your local filesystem's own
permissions.

## Reporting a Vulnerability

This is currently a solo learning project with no formal security team
or disclosure process. If you find a security issue:

- Open a GitHub issue on the repository, or
- If the issue involves something that shouldn't be public until fixed
  (e.g., a way to exfiltrate stored credentials), reach out to the
  repository owner directly rather than filing a public issue first.

There is no bug bounty program and no guaranteed response time — this
reflects the project's current stage, not a policy choice to be
unresponsive.

## What This Document Does Not Cover

This is a practical, current-state document, not a comprehensive threat
model. It does not cover supply-chain security for dependencies (see
`requirements.txt`'s version pins, e.g. the `playwright==1.56.0` pin
documented in [ADR-0008](docs/adr/0008-browser-automation-engine.md)
for an example of a dependency-related issue this project has actually
hit and fixed), deployment security (not applicable yet — there is no
deployed version of JAAP), or multi-user access control (not applicable
yet — JAAP is single-user). These may warrant their own sections once
Phase 5 (deployment, multi-user accounts) is in scope.
