"""One-off migration: adds Profile's new address columns to an
EXISTING `profiles` table.

Base.metadata.create_all() (called at the top of every `jaap` CLI
invocation, see infrastructure/database/base.py) only ever creates
tables that don't exist yet -- it never alters an existing table's
columns. Anyone who already has a `jaap.db` from before address-field
support was added (ADR-0038) needs this script run once, so their
existing profiles gain the new (nullable) columns without losing any
existing data. A brand-new database created after this change already
gets these columns for free via create_all(), and running this script
against one is a safe no-op.

Safe to run multiple times: checks each column's existence first, and
only ever ADDs columns, never drops or renames anything.

Usage (from the repo root, with the venv active):
    python scripts/migrate_add_profile_address_fields.py

Uses the same JAAP_DATABASE_URL environment variable (or the same
default, `sqlite:///./data/jaap.db`) as the rest of the CLI, via
Settings() -- so it targets whichever database your normal `jaap`
commands already use, with no separate configuration needed.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allows running this script directly (`python scripts/migrate_add_profile_address_fields.py`)
# without needing PYTHONPATH set manually -- see the same comment in
# scripts/seed_job_posting.py for why.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import text

from jaap.infrastructure.config.settings import Settings
from jaap.infrastructure.database.session import (
    create_engine_from_settings,
)

# All nullable VARCHAR -- matches ProfileORM's own column definitions
# (infrastructure/database/models.py) exactly.
_NEW_COLUMNS = {
    "address_line1": "VARCHAR",
    "address_line2": "VARCHAR",
    "city": "VARCHAR",
    "state": "VARCHAR",
    "postal_code": "VARCHAR",
    "country": "VARCHAR",
}


def main() -> int:
    settings = Settings()
    engine = create_engine_from_settings(settings)

    with engine.connect() as conn:
        existing_columns = {
            row[1] for row in conn.execute(text("PRAGMA table_info(profiles)"))
        }

        if not existing_columns:
            print(
                "No 'profiles' table found yet -- nothing to migrate. "
                "A fresh database will already include the new columns "
                "once you create one (e.g. via `jaap profile create`)."
            )
            return 0

        added = []
        for column, sql_type in _NEW_COLUMNS.items():
            if column in existing_columns:
                continue
            conn.execute(text(f"ALTER TABLE profiles ADD COLUMN {column} {sql_type}"))
            added.append(column)
        conn.commit()

    if added:
        print(f"Added column(s) to 'profiles': {', '.join(added)}")
    else:
        print("All address columns already present on 'profiles' -- nothing to do.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
