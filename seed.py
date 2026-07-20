"""Seed the database with a super-admin, a student, and approved sample questions.

Run once after install:  python seed.py
"""

from __future__ import annotations

import json
import os

from app import create_app
from blueprints.auth import create_account
from models import ItemStats, Question, User, db
from question_types import normalize_imported_question
from subjects import get_or_create_subject

app = create_app()


def run():
    """Initialize the database with demo users and sample questions from seed.json."""
    with app.app_context():
        db.create_all()

        admin_email = app.config["SUPER_ADMIN_EMAIL"]
        if not User.query.filter_by(email=admin_email.lower()).first():
            create_account(admin_email, "password123", "מנהל ראשי")
            print(f"created super_admin: {admin_email} / password123")

        if not User.query.filter_by(email="student@example.com").first():
            create_account("student@example.com", "password123", "תלמיד לדוגמה")
            print("created student: student@example.com / password123")

        sample_path = os.path.join(os.path.dirname(__file__), "sample_questions.json")
        if Question.query.count() == 0 and os.path.exists(sample_path):
            with open(sample_path, encoding="utf-8") as f:
                arr = json.load(f)
            for i, raw in enumerate(arr):
                norm = normalize_imported_question(raw)
                if not norm["valid"]:
                    print("skip invalid:", norm["issue"])
                    continue
                ins = norm["insert"]
                subj = get_or_create_subject(ins.get("parcours"), ins.get("siman"), ins.get("subject"))
                db.session.add(
                    Question(
                        question_type=ins["question_type"],
                        text=ins["text"],
                        payload=ins["payload"],
                        choices=ins["choices"],
                        correct_answer=ins["correct_answer"],
                        explanation=ins["explanation"],
                        difficulty=ins["difficulty"],
                        section=ins["section"],
                        tags=ins["tags"],
                        source_ref=ins["source_ref"],
                        subject_id=subj.id,
                        siman=ins.get("siman"),
                        seif=ins.get("seif"),
                        parcours=ins.get("parcours"),
                        status="approved",
                    )
                )
            db.session.commit()
            print(f"seeded {Question.query.count()} approved questions")

        # collective calibration: ensure an ItemStats row per question (Phase 2)
        missing = (
            Question.query.filter(
                ~Question.id.in_(db.session.query(ItemStats.question_id))
            ).all()
        )
        for q in missing:
            db.session.add(
                ItemStats(
                    question_id=q.id,
                    question_type=q.question_type,
                    hidden_difficulty=q.difficulty,
                )
            )
        if missing:
            db.session.commit()
            print(f"initialised item_stats for {len(missing)} questions")


if __name__ == "__main__":
    run()
