"""Idempotent migration for the Phase 2 collective-calibration schema.

`db.create_all()` creates the NEW tables (item_stats, user_speed) but does not
ADD columns to existing tables. Run this once against an existing database
(dev SQLite that you don't want to wipe, or prod Postgres):

    python -m scripts.migrate_phase2

Fresh installs don't need it — `python seed.py` builds the full schema.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app  # noqa: E402
from models import db  # noqa: E402

# table -> {column: SQL type} to add if missing
NEW_COLUMNS = {
    "user_answers": {
        "z_item": "FLOAT",
        "z_user": "FLOAT",
        "auto_grade": "FLOAT",
    },
    "student_profiles": {
        "elo_ability": "FLOAT NOT NULL DEFAULT 0",
    },
}


def migrate() -> None:
    app = create_app()
    with app.app_context():
        # 1. create the new tables (item_stats, user_speed) if absent
        db.create_all()

        insp = inspect(db.engine)
        for table, columns in NEW_COLUMNS.items():
            if not insp.has_table(table):
                print(f"skip {table}: table absent (create_all will have made it)")
                continue
            existing = {c["name"] for c in insp.get_columns(table)}
            for col, coltype in columns.items():
                if col in existing:
                    print(f"ok   {table}.{col} already present")
                    continue
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}"))
                print(f"add  {table}.{col} {coltype}")
        db.session.commit()
        print("migration complete")


if __name__ == "__main__":
    migrate()
