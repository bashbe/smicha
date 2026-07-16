"""Idempotent migration: add UserAnswer.predicted_r (retention instrumentation).

`db.create_all()` never ADDs columns to existing tables, so run this once
against a database that predates the retention-instrumentation change (dev
SQLite you don't want to wipe, or prod Postgres):

    python -m scripts.migrate_predicted_r

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
        "predicted_r": "FLOAT",
    },
}


def migrate() -> None:
    app = create_app()
    with app.app_context():
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
