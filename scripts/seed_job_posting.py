"""One-off script to insert a JobPosting directly into the database.

There is no CreateJobPostingUseCase yet -- Milestone 7 deliberately
deferred it, since real job posting creation will eventually come from
Phase 4's connectors (Greenhouse, Lever, LinkedIn, ...), not a manual
CLI command. Until then, this script is how you get a JobPostingId to
use with `jaap application start`.

Usage (from the repo root, with the venv active):
    python scripts/seed_job_posting.py \\
        --company "Acme Corp" --title "Senior Backend Engineer" \\
        --url "https://acme.example.com/jobs/123" --platform greenhouse
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allows running this script directly (`python scripts/seed_job_posting.py`)
# without needing PYTHONPATH set manually -- the rest of the project relies
# on pytest.ini's `pythonpath = src` for this during tests, but a standalone
# script has no equivalent, so it's done explicitly here instead.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jaap.domain.models import JobPlatform, JobPosting, new_job_posting_id
from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.database.base import Base
from jaap.infrastructure.database.repositories.sqlite_job_posting_repository import (
    SqliteJobPostingRepository,
)
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
    create_session_factory,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a JobPosting directly into the database")
    parser.add_argument("--company", required=True, dest="company_name")
    parser.add_argument("--title", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--platform", default=JobPlatform.OTHER)
    parser.add_argument("--external-id", default=None)
    args = parser.parse_args()

    settings = Settings()
    engine = create_engine_from_settings(settings)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    repository = SqliteJobPostingRepository(session_factory)

    posting = JobPosting(
        id=new_job_posting_id(),
        company_name=args.company_name,
        title=args.title,
        url=args.url,
        platform=args.platform,
        external_id=args.external_id,
    )
    repository.save(posting)
    print(f"Created job posting {posting.id} ({posting.company_name} -- {posting.title})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
