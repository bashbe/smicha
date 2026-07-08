"""One-off data migration: accept all pre-existing questions by default.

The product default flipped from "pending" (needs validator approval) to
"approved" (accepted unless a student reports it). This script brings an
EXISTING database in line with the new default by approving every question
still sitting in "pending" — questions already "rejected" are left untouched
since a validator already made an explicit decision on those.

    python -m scripts.migrate_approve_pending

Fresh installs don't need it — `python seed.py` already inserts approved
questions.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import Question, db  # noqa: E402


def migrate() -> None:
    app = create_app()
    with app.app_context():
        updated = Question.query.filter_by(status="pending").update({"status": "approved"})
        db.session.commit()
        print(f"{updated} שאלות עברו מ-pending ל-approved")


if __name__ == "__main__":
    migrate()
