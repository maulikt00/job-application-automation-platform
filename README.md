# Job Application Automation Platform (JAAP)

> Automate the repetitive parts of job hunting. Never automate the decision to apply.

JAAP is a Python application that helps you manage resumes, cover letters, and
reusable answers, then assists with filling out job applications in the
browser — **with a human review step before anything is ever submitted.**

This project is also a long-term learning vehicle: it's built openly, in
small reviewable milestones, using Clean Architecture, so that it stays easy
to extend (new job sites, new AI providers, new interfaces) for years without
becoming unmaintainable.

## Philosophy

- **The user decides. The software assists.** JAAP never submits an
  application without explicit human review and approval.
- **AI helps you write and think. It never touches the browser.** Cover
  letter drafts, answer suggestions, and resume tailoring come from an AI
  provider; clicking "submit" never does.
- **New platforms and providers should be additive, not invasive.** Adding
  support for a new job site or a new AI provider should mean *adding a
  file*, not editing existing, working code.
- **Built for the long haul.** Every module is small, single-responsibility,
  and testable, so the codebase can keep growing without rotting.

## Status

✅ **v1 complete** ([ADR-0039](docs/adr/0039-v1-declared-complete.md)). See
[PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) for the full milestone
breakdown. Phases 1-4 (domain models through the CLI, browser
automation, AI integration, and three website connectors --
Greenhouse, Lever, Workday) are complete, and real-world validation
against live postings on all three platforms confirmed the core
promise: a single user can find a real posting, get correct autofill
on the actual live page, and receive an honest, safe report of what
needs manual attention. Workday specifically reached a real,
authenticated application form and correctly autofilled every field
with a natural home in a Profile (name, address, phone). A handful of
known, lower-stakes items remain deliberately deferred (documented in
PROJECT_ROADMAP.md) -- not oversights, but scoped trade-offs.

## Architecture

JAAP follows Clean Architecture with four layers (domain → application →
infrastructure → presentation), where dependencies only ever point inward.
Full details, diagrams, and reasoning live in [ARCHITECTURE.md](ARCHITECTURE.md)
and the [Architecture Decision Records](docs/adr/).

## Phases

| Phase | Focus |
|---|---|
| 1 | User profiles, resumes, cover letter templates, reusable answers, SQLite storage |
| 2 | Playwright browser automation, form detection, autofill, human review before submit |
| 3 | AI provider abstraction (Claude, Ollama), AI-generated cover letters & answers, resume recommendation |
| 4 | Website connectors: Greenhouse, Lever, Workday |
| 5 | Dashboard, analytics, resume scoring, notifications, Docker, REST API, plugin system |

See [PROJECT_ROADMAP.md](PROJECT_ROADMAP.md) for the milestone-level breakdown.

## Getting Started

> **v1 complete**: domain models through the CLI, browser automation
> from field detection through the human review gate, AI integration
> (Claude, Ollama, AI-generated content), and three website connectors
> (Greenhouse, Lever, Workday) wired into the autofill flow --
> confirmed against real, live postings on all three platforms.

```bash
python -m venv .venv
source .venv/bin/activate      # or .venv\Scripts\activate on Windows
pip install -r requirements.txt -r requirements-dev.txt

# Browser automation (Phase 2) needs a separate, non-PyPI binary download --
# `pip install` alone does not provide it:
python -m playwright install chromium
```

## Running Tests

```bash
pytest tests/unit -v
```

422 tests, covering domain models, configuration/logging, the database
layer, all six repositories, core use cases, the CLI, browser automation
including form field detection/autofill/resume upload/the human review
gate (run against a real headless Chromium instance and a real local
HTTP server, not mocks), the submitted content snapshot, automated
architecture-boundary enforcement, two AI providers (`ClaudeProvider`,
`OllamaProvider`, each tested against their real SDK's response shape
via a fake client, no real API calls, and each selectable via
`--provider`), AI-generated cover letters/application answers/resume
recommendations, three website connectors (`GreenhouseConnector`,
`LeverConnector`, `WorkdayConnector`, each verified against real
Chromium), the connector registry wiring them into `jaap application
review`, a generic `--interactive` pause-and-retry mechanism for
connectors reporting a sign-in wall, a deliberately narrow first/last
name splitting feature, Profile address fields with a partial-update
command and a one-off database migration script, and a growing set of
fixes found by validating against real, live job postings on Lever,
Greenhouse, and Workday (confirmed on two independent tenants, and, for
the first time in this project's history, reaching a real, authenticated
Workday application form) -- including a firm, reinforced boundary that
JAAP will never automate account creation or sign-in.

## Tech Stack

Python 3.12+, Playwright, SQLite, SQLAlchemy, Pydantic, pytest, and (later)
FastAPI / NiceGUI. See [ARCHITECTURE.md](ARCHITECTURE.md) for how each piece
fits together.

## Contributing

This is currently a solo learning project developed milestone-by-milestone
in the open. See [CONTRIBUTING.md](CONTRIBUTING.md) for branch naming, commit
conventions, and workflow — useful context even for a project of one, and
ready for outside contributors later.

## License

[MIT](LICENSE)
