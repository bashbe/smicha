"""Tests for the /llm-pipeline support: DB models, run importer, admin pages.

pytest-compatible, also runnable standalone:  python tests/test_llm_pipeline.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTO_SYNC_DB"] = "0"

from app import create_app  # noqa: E402
from models import LLMCoherenceReport, LLMPipelineRun, LLMReview, Question, User, UserRole, db  # noqa: E402


def _fresh_app():
    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def _add_staff(role: str = "super_admin") -> User:
    user = User(email=f"{role}@example.com", full_name=role.title())
    user.set_password("secret123")
    db.session.add(user)
    db.session.flush()
    db.session.add(UserRole(user_id=user.id, role=role))
    db.session.commit()
    return user


def _valid_question(**overrides) -> dict:
    q = {
        "type": "true_false",
        "parcours": "bassar_bechalav",
        "sujet": "נושא בדיקה",
        "siman": 89,
        "seif": 1,
        "difficulty_level": 2,
        "exam_section": "shulchan_aruch",
        "statement_text": "משפט בדיקה?",
        "correct_answer": True,
        "explanation": "הסבר עםמקור",
        "tags": ["בדיקה"],
        "source": {"siman": 89, "seif": 1},
    }
    q.update(overrides)
    return q


def _make_run_dir(root: str, run_id: str, questions: list[dict], reviews: list[dict], coherence: dict | None = None) -> str:
    run_dir = os.path.join(root, run_id)
    os.makedirs(run_dir, exist_ok=True)
    meta = {
        "siman": 89, "chelek": "yd", "parcours": "bassar_bechalav",
        "max_iter": 3, "iterations": 1, "status": "done",
        "created_at": "2026-07-31T10:00:00",
    }
    with open(os.path.join(run_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    with open(os.path.join(run_dir, "final_questions.json"), "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False)
    with open(os.path.join(run_dir, "final_reviews.json"), "w", encoding="utf-8") as f:
        json.dump({"iteration": 0, "reviews": reviews}, f, ensure_ascii=False)
    if coherence:
        with open(os.path.join(run_dir, "03_coherence_v1.json"), "w", encoding="utf-8") as f:
            json.dump(coherence, f, ensure_ascii=False)
    return run_dir


# --- model tests -----------------------------------------------------------

def test_models_roundtrip():
    app = _fresh_app()
    with app.app_context():
        run = LLMPipelineRun(id="run1", siman=89, chelek="yd", parcours="bassar_bechalav",
                             status="done", run_dir="docs/pipeline_runs/run1",
                             total_questions=2, llm_approved=1, llm_flagged=1)
        db.session.add(run)
        db.session.flush()
        rev = LLMReview(run_id=run.id, question_index=0, agent_name="halakhiste",
                        agent_label="L'Halakhiste", vote="keep", confidence=0.9,
                        comment="OK", iteration=0)
        coh = LLMCoherenceReport(run_id=run.id, iteration=0, report_json={"overall": "ok"})
        db.session.add_all([rev, coh])
        db.session.commit()
        assert run.as_dict()["siman"] == 89
        assert rev.as_dict()["vote"] == "keep"
        assert coh.as_dict()["report"]["overall"] == "ok"
        assert LLMPipelineRun.query.count() == 1
        assert LLMReview.query.count() == 1
        assert LLMCoherenceReport.query.count() == 1


def test_review_unique_constraint():
    app = _fresh_app()
    with app.app_context():
        run = LLMPipelineRun(id="runU", siman=1, parcours="bassar_bechalav",
                             run_dir="docs/pipeline_runs/runU")
        db.session.add(run)
        db.session.flush()
        db.session.add(LLMReview(run_id=run.id, question_index=0, agent_name="pedagogue",
                                 agent_label="P", vote="keep", iteration=0))
        db.session.commit()
        db.session.add(LLMReview(run_id=run.id, question_index=0, agent_name="pedagogue",
                                 agent_label="P", vote="reject", iteration=0))
        try:
            db.session.commit()
            raised = False
        except Exception:
            raised = True
            db.session.rollback()
        assert raised, "duplicate (run, index, agent, iteration) should violate uq_llm_review"


# --- importer tests --------------------------------------------------------

def test_import_run_creates_questions_and_reviews():
    app = _fresh_app()
    from scripts.import_llm_run import import_run
    with app.app_context():
        with tempfile.TemporaryDirectory() as tmp:
            questions = [_valid_question(), _valid_question(seif=2, _llm_status="llm_flagged")]
            reviews = [
                {"question_index": 0, "agent": "halakhiste", "label": "L'Halakhiste",
                 "vote": "keep", "confidence": 0.9, "comment": "exact"},
                {"question_index": 1, "agent": "pedagogue", "label": "Pédagogue",
                 "vote": "reject", "confidence": 0.7, "comment": "trop facile"},
            ]
            coherence = {"iteration": 0, "overall": "needs_work", "duplicates": [],
                         "should_split": [], "coverage_gaps": [{"seif": 3, "missing": True}]}
            run_dir = _make_run_dir(tmp, "test_run_1", questions, reviews, coherence)
            with open(os.path.join(run_dir, "02_reviews_v1.json"), "w", encoding="utf-8") as f:
                json.dump({"iteration": 0, "reviews": reviews}, f)
            summary = import_run(run_dir, app=app)
            assert summary["questions_inserted"] == 2
            assert summary["questions_failed"] == 0
            assert summary["llm_flagged"] == 1
            assert summary["reviews_imported"] == 2

            run = LLMPipelineRun.query.get("test_run_1")
            assert run is not None and run.status == "done"
            assert run.total_questions == 2

            qs = Question.query.order_by(Question.seif).all()
            assert len(qs) == 2
            assert qs[0].status == "pending"
            assert qs[1].status == "a_revoir"

            revs = LLMReview.query.order_by(LLMReview.question_index).all()
            assert len(revs) == 2
            assert all(r.question_id is not None for r in revs)
            assert revs[0].question_id == qs[0].id
            assert revs[1].vote == "reject"

            coh = LLMCoherenceReport.query.filter_by(run_id="test_run_1").all()
            assert len(coh) == 1
            assert coh[0].report_json["coverage_gaps"][0]["seif"] == 3


def test_import_run_is_idempotent():
    app = _fresh_app()
    from scripts.import_llm_run import import_run
    with app.app_context():
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _make_run_dir(tmp, "test_run_2", [_valid_question()], [])
            import_run(run_dir, app=app)
            again = import_run(run_dir, app=app)
            assert again.get("already_imported") is True
            assert Question.query.count() == 1


def test_import_run_skips_invalid_questions():
    app = _fresh_app()
    from scripts.import_llm_run import import_run
    with app.app_context():
        with tempfile.TemporaryDirectory() as tmp:
            bad = _valid_question()
            bad["parcours"] = "nonexistent_parcours"
            run_dir = _make_run_dir(tmp, "test_run_3", [bad, _valid_question(seif=5)], [])
            summary = import_run(run_dir, app=app)
            assert summary["questions_inserted"] == 1
            assert summary["questions_failed"] == 1


# --- admin page tests ------------------------------------------------------

def test_llm_runs_pages_require_staff():
    app = _fresh_app()
    client = app.test_client()
    assert client.get("/admin/llm-runs").status_code in (302, 303)


def test_llm_runs_pages_render_for_staff():
    app = _fresh_app()
    with app.app_context():
        user = _add_staff("super_admin")
        db.session.add(LLMPipelineRun(id="runX", siman=26, chelek="ehy",
                                       parcours="chupa_kidushin", status="done",
                                       run_dir="docs/pipeline_runs/runX",
                                       total_questions=5, llm_approved=4, llm_flagged=1))
        db.session.commit()
        client = app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = user.id
        r = client.get("/admin/llm-runs")
        assert r.status_code == 200
        assert b"runX" in r.data
        r2 = client.get("/admin/llm-runs/runX")
        assert r2.status_code == 200
        assert b"runX" in r2.data


if __name__ == "__main__":
    test_models_roundtrip()
    test_review_unique_constraint()
    test_import_run_creates_questions_and_reviews()
    test_import_run_is_idempotent()
    test_import_run_skips_invalid_questions()
    test_llm_runs_pages_require_staff()
    test_llm_runs_pages_render_for_staff()
    print("All test_llm_pipeline tests passed.")
