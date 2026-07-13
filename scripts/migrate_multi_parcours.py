"""Idempotent migration for the multi-parcours feature (per-parcours exam dates).

Creates the `student_parcours` table and backfills one active parcours
(bassar_bechalav) per already-onboarded student, copying the legacy global
fields from `student_profiles` (exam_date, daily_completion_streak,
last_daily_completion_date). The legacy columns are kept in place (deprecated,
no longer read or written by the app).

Run once against an existing database (dev SQLite you don't want to wipe, or
prod Postgres):

    python -m scripts.migrate_multi_parcours

Fresh installs don't need it — `python seed.py` builds the full schema, and
the onboarding flow creates the `student_parcours` rows.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import Question, StudentParcours, StudentProfile, db  # noqa: E402

DEFAULT_PARCOURS = "bassar_bechalav"


def migrate() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()  # creates student_parcours (new table, no ALTER needed)

        created = 0
        already = {r.user_id for r in StudentParcours.query.all()}
        for sp in StudentProfile.query.filter_by(onboarded=True).all():
            if sp.id in already:
                print(f"ok   {sp.id} already has student_parcours rows")
                continue
            db.session.add(
                StudentParcours(
                    user_id=sp.id,
                    parcours=DEFAULT_PARCOURS,
                    exam_date=sp.exam_date,
                    daily_completion_streak=sp.daily_completion_streak or 0,
                    last_daily_completion_date=sp.last_daily_completion_date,
                    # created_at aligné sur le profil pour que la barre de
                    # préparation (prep_pct) reste continue après migration.
                    created_at=sp.created_at,
                )
            )
            created += 1
            print(f"add  {sp.id} -> {DEFAULT_PARCOURS} (exam_date={sp.exam_date})")
        db.session.commit()

        # Les questions sans parcours disparaîtraient des files filtrées par
        # parcours actif — warning non bloquant pour audit.
        orphan = Question.query.filter(Question.parcours.is_(None)).count()
        if orphan:
            print(f"WARNING: {orphan} question(s) with parcours=NULL — invisible "
                  f"to students until a parcours is set (/admin/questions)")

        print(f"migration complete ({created} student_parcours row(s) created)")


if __name__ == "__main__":
    migrate()
