"""Exercise the real two-file configuration, including a student answer."""

import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import create_app
from backup_service import create_backup
from blueprints.auth import create_account
from config import Config
from models import Question, StudentParcours, db
from scripts.question_catalog import CATALOG, export_catalog, import_catalog


def test_split_storage():
    with TemporaryDirectory() as directory:
        root = Path(directory)
        private = root / "private.sqlite3"
        catalog = root / "questions.sqlite3"

        class TestConfig(Config):
            TESTING = True
            SQLALCHEMY_DATABASE_URI = f"sqlite:///{private.as_posix()}"
            QUESTIONS_DB_PATH = str(catalog)
            BACKUP_DIR = str(root / "backups")

        app = create_app(TestConfig)
        try:
            email = Config.PROTECTED_SUPER_ADMIN_EMAIL
            with app.app_context():
                assert import_catalog(CATALOG) > 0
                import_catalog(CATALOG)
                owner = create_account(email, "local-test-password", "Test")
                question = Question.query.filter_by(status="approved", question_type="multiple_choice").first()
                question.created_by = owner.id
                question.validator_note = "private evaluation"
                question_id, subject_id, answer = question.id, question.subject_id, question.correct_answer
                owner.student_profile.onboarded = True
                owner.student_profile.section = ["shulchan_aruch", "tur", "ptei_teshuva"]
                owner.student_profile.preparation_goal = "serious"
                db.session.add(StudentParcours(user_id=owner.id, parcours=question.parcours))
                db.session.commit()

                exported = root / "export.json"
                export_catalog(exported)
                assert exported.read_text(encoding="utf-8") == CATALOG.read_text(encoding="utf-8")

            client = app.test_client()
            assert client.get("/auth").status_code == 200
            assert client.post("/auth", data={"email": email, "password": "local-test-password"}).status_code == 302
            for url in ("/app/home", "/app/parcours", f"/app/chapitre/{subject_id}",
                        "/app/revision", "/admin/dashboard", "/admin/import",
                        "/admin/questions", "/admin/data?table=questions"):
                response = client.get(url)
                assert response.status_code == 200, (url, response.status_code)
                assert b'dir="rtl"' in response.data
            response = client.post("/api/answer", json={
                "question_id": question_id, "given_answer": answer,
                "response_time_ms": 1000, "mode": "study",
            })
            assert response.status_code == 200, response.get_json()
            with closing(sqlite3.connect(private)) as connection:
                assert connection.execute("select question_id from user_answers").fetchone() == (question_id,)
                assert not connection.execute(
                    "select 1 from sqlite_master where name = 'questions'"
                ).fetchone()
            with closing(sqlite3.connect(catalog)) as connection:
                assert connection.execute("select id from questions where id = ?", (question_id,)).fetchone()
                assert not connection.execute(
                    "select 1 from sqlite_master where name in ('users', 'user_answers', 'fsrs_cards')"
                ).fetchone()

            with app.app_context():
                backup = create_backup()
                with ZipFile(Path(TestConfig.BACKUP_DIR) / backup.filename) as archive:
                    assert set(archive.namelist()) == {"users.sqlite3", "questions.sqlite3"}
            assert client.post("/admin/reset-db", data={"confirm": "RESET"}).status_code == 302
            with app.app_context():
                assert db.session.get(Question, question_id) is not None
        finally:
            with app.app_context():
                db.engine.dispose()


if __name__ == "__main__":
    test_split_storage()
    print("split storage test passed")
