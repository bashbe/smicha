"""Smoke tests for the focused English admin interface."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTO_SYNC_DB"] = "0"

from app import create_app  # noqa: E402
from models import BackupApiToken, Question, StudentProfile, Subject, User, UserRole, db  # noqa: E402


def _fresh_app():
    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def _add_staff(role: str) -> User:
    user = User(email=f"{role}@example.com", full_name=role.title())
    user.set_password("secret123")
    db.session.add(user)
    db.session.flush()
    db.session.add(UserRole(user_id=user.id, role=role))
    db.session.add(StudentProfile(id=user.id, full_name=user.full_name))
    db.session.commit()
    return user


def _add_question() -> Question:
    subject = Subject(parcours="bassar_bechalav", siman=87, title="בשר בחלב")
    db.session.add(subject)
    db.session.flush()
    question = Question(
        text="מה הדין?",
        status="pending",
        question_type="true_false",
        payload={
            "type": "true_false",
            "statement_text": "מה הדין?",
            "correct_answer": True,
            "difficulty_level": 2,
            "exam_section": ["shulchan_aruch"],
            "explanation": "הסבר",
            "tags": [],
        },
        subject_id=subject.id,
        parcours="bassar_bechalav",
        siman=87,
        seif=1,
    )
    db.session.add(question)
    db.session.commit()
    return question


def _login(client, user: User):
    with client.session_transaction() as session:
        session["user_id"] = user.id


def test_primary_admin_pages_render_in_english():
    app = _fresh_app()
    with app.app_context():
        admin = _add_staff("super_admin")
        question = _add_question()
        client = app.test_client()
        _login(client, admin)
        expected = {
            "/admin/dashboard": b"Needs attention",
            "/admin/questions": b"Question bank",
            "/admin/subjects": b"Simanim & subjects",
            "/admin/users": b"Users",
            "/admin/backups": b"Backups",
            "/admin/data": b"Database explorer",
            "/admin/api-security": b"Emergency SQL API",
        }
        for path, marker in expected.items():
            response = client.get(path)
            assert response.status_code == 200, path
            assert marker in response.data, path
        scoped = client.get(
            f"/admin/analytics?parcours=bassar_bechalav&siman=87&subject={question.subject_id}"
        )
        assert scoped.status_code == 200
        assert b"Selected scope" in scoped.data

        response = client.post(
            "/admin/subjects",
            data={
                "siman_parcours": "bassar_bechalav",
                "siman_num": "87",
                "siman_topic": "",
                "subject_id": question.subject_id,
                "subject_title": "Renamed subject",
            },
        )
        assert response.status_code == 302
        assert db.session.get(Subject, question.subject_id).title == "Renamed subject"

        response = client.post("/admin/backup-api-keys", data={"label": "Secondary scheduler"})
        assert response.status_code == 200
        assert b"Copy this key now" in response.data
        assert BackupApiToken.query.filter_by(label="Secondary scheduler").count() == 1


def test_validator_cannot_edit_question_content():
    app = _fresh_app()
    with app.app_context():
        validator = _add_staff("validator")
        question = _add_question()
        original_text = question.text
        client = app.test_client()
        _login(client, validator)
        response = client.post(
            f"/admin/questions/{question.id}/edit",
            data={"action": "save", "question_text": "Changed"},
        )
        assert response.status_code == 302
        assert db.session.get(Question, question.id).text == original_text


if __name__ == "__main__":
    test_primary_admin_pages_render_in_english()
    test_validator_cannot_edit_question_content()
    print("admin UI tests passed")
