"""One-off data migration: reverse the "acceptation par défaut" business rule.

The product default flipped back from "approved" (accepted unless a student
reports it) to "pending" (needs validator/admin approval before students ever
see it) — see the 4-state status rule in README.md (pending / approved /
a_revoir / rejected). This script brings an EXISTING database in line with
the new default by requeuing every question currently "approved" back into
"pending" — questions already "rejected" or "a_revoir" are left untouched
since a validator already made an explicit decision on those.

WARNING: running this on a database with live student traffic makes every
previously-approved question invisible to students until a validator/admin
re-approves it individually (or via "אשר הכל" on the pending filter). Only
run this deliberately, on purpose, with the team aware of the impact.

    python -m scripts.migrate_requeue_approved

Fresh installs don't need it — `seed.py` and `blueprints/admin.py` already
insert new questions as "pending".
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
        updated = Question.query.filter_by(status="approved").update({"status": "pending"})
        db.session.commit()
        print(f"{updated} שאלות עברו מ-approved ל-pending")


if __name__ == "__main__":
    migrate()
