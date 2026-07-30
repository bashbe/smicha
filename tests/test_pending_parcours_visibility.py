"""Pending questions are previewable in Parcours by validation staff only."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTO_SYNC_DB"] = "0"

from app import create_app  # noqa: E402
from models import Question, StudentParcours, StudentProfile, Subject, User, UserRole, db  # noqa: E402


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def _seed_user_and_pending_question(role: str):
    user = User(email=f"{role}@example.com", password_hash="x", full_name=role)
    db.session.add(user)
    db.session.flush()
    db.session.add(UserRole(user_id=user.id, role=role))
    db.session.add(
        StudentProfile(
            id=user.id,
            full_name=role,
            onboarded=True,
            section=["shulchan_aruch"],
        )
    )
    db.session.add(StudentParcours(user_id=user.id, parcours="bassar_bechalav"))
    subject = Subject(
        parcours="bassar_bechalav",
        siman=87,
        title="נושא בדיקה ממתין",
    )
    db.session.add(subject)
    db.session.flush()
    question = Question(
        text="שאלה ממתינה לבדיקה",
        explanation="הסבר מלא לשאלה",
        difficulty=1,
        section=["shulchan_aruch"],
        status="pending",
        subject_id=subject.id,
        siman=87,
        seif=1,
        parcours="bassar_bechalav",
        question_type="multiple_choice",
        payload={
            "type": "multiple_choice",
            "question_text": "שאלה ממתינה לבדיקה",
            "options": [
                {"number": 1, "text": "תשובה נכונה", "is_correct": True},
                {"number": 2, "text": "תשובה שגויה", "is_correct": False},
            ],
            "difficulty_level": 1,
            "exam_section": ["shulchan_aruch"],
            "explanation": "הסבר מלא לשאלה",
            "parcours": "bassar_bechalav",
            "sujet": "נושא בדיקה ממתין",
            "siman": 87,
            "seif": 1,
        },
        choices=[
            {"label": "1", "text": "תשובה נכונה"},
            {"label": "2", "text": "תשובה שגויה"},
        ],
        correct_answer="1",
    )
    db.session.add(question)
    db.session.commit()
    return user.id, subject.id, question.id


def _client_for(app, user_id: str):
    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = user_id
    return client


def test_pending_visible_to_validator_and_super_admin():
    for role in ("validator", "super_admin"):
        app = _fresh_app()
        with app.app_context():
            user_id, subject_id, question_id = _seed_user_and_pending_question(role)
        client = _client_for(app, user_id)

        parcours_response = client.get("/app/parcours")
        assert parcours_response.status_code == 200
        assert "נושא בדיקה ממתין".encode() in parcours_response.data

        chapter_response = client.get(f"/app/chapitre/{subject_id}")
        assert chapter_response.status_code == 200
        assert question_id.encode() in chapter_response.data


def test_pending_hidden_from_ordinary_student_and_answer_api():
    app = _fresh_app()
    with app.app_context():
        user_id, subject_id, question_id = _seed_user_and_pending_question("student")
    client = _client_for(app, user_id)

    parcours_response = client.get("/app/parcours")
    assert parcours_response.status_code == 200
    assert "נושא בדיקה ממתין".encode() not in parcours_response.data

    chapter_response = client.get(f"/app/chapitre/{subject_id}")
    assert chapter_response.status_code == 302

    answer_response = client.post(
        "/api/answer",
        json={
            "question_id": question_id,
            "given_answer": "1",
            "response_time_ms": 1000,
            "mode": "study",
        },
    )
    assert answer_response.status_code == 404
    assert answer_response.get_json()["error"] == "question not available"


if __name__ == "__main__":
    tests = [
        test_pending_visible_to_validator_and_super_admin,
        test_pending_hidden_from_ordinary_student_and_answer_api,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
