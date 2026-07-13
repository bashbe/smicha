"""Tests for the multi-parcours feature (per-parcours exam dates, daily bonus,
revision-day selector).

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_multi_parcours.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory, before app import

from app import create_app  # noqa: E402
from models import (  # noqa: E402
    FsrsCard,
    Question,
    StudentParcours,
    StudentProfile,
    User,
    db,
)

TODAY = date.today()


def _fresh_app():
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
    return app


def _make_user(email="student@test.dev") -> str:
    u = User(email=email, password_hash="x", full_name="תלמיד בדיקה")
    db.session.add(u)
    db.session.commit()
    sp = StudentProfile(
        id=u.id, full_name=u.full_name, onboarded=True,
        section=["shulchan_aruch"], target_stability=0.95,
    )
    db.session.add(sp)
    db.session.commit()
    return u.id


def _activate(user_id: str, parcours: str, exam_date=None, **kw) -> StudentParcours:
    row = StudentParcours(user_id=user_id, parcours=parcours, exam_date=exam_date, **kw)
    db.session.add(row)
    db.session.commit()
    return row


def _make_question(parcours: str, siman=1, seif=1) -> Question:
    q = Question(
        text="שאלה", question_type="true_false",
        payload={"statement_text": "אמת?", "correct_answer": True},
        explanation="", difficulty=1, section=["shulchan_aruch"],
        status="approved", parcours=parcours, subject="נושא " + parcours,
        siman=siman, seif=seif,
    )
    db.session.add(q)
    db.session.commit()
    return q


def _make_due_card(user_id: str, q: Question, stability=5.0) -> FsrsCard:
    card = FsrsCard(
        user_id=user_id, question_id=q.id, due_date=TODAY,
        stability=stability, fsrs_difficulty=5.0, state="review", reps=3,
        last_review=datetime.utcnow() - timedelta(days=5),
        avg_response_time_ms=5000, target_stability=0.95,
    )
    db.session.add(card)
    db.session.commit()
    return card


def _login(client, user_id: str):
    with client.session_transaction() as s:
        s["user_id"] = user_id


def _answer(client, q: Question, correct=True):
    return client.post("/api/answer", json={
        "question_id": q.id,
        "given_answer": "true" if correct else "false",
        "response_time_ms": 5000,
        "combo": 0,
        "mode": "revision_daily",
    }).get_json()


def test_bonus_when_one_parcours_emptied_while_other_still_due():
    app = _fresh_app()
    with app.app_context():
        uid = _make_user()
        _activate(uid, "p1")
        _activate(uid, "p2")
        q1 = _make_question("p1")
        q2 = _make_question("p2", siman=2)
        _make_due_card(uid, q1)
        _make_due_card(uid, q2)
        client = app.test_client()
        _login(client, uid)

        # Vider p1 alors que p2 a encore une carte due : l'ancienne logique
        # globale aurait donné 0 (file totale non vide), la nouvelle donne 150.
        data = _answer(client, q1)
        assert data["is_correct"] is True
        assert data["daily_bonus"] == 150, data
        assert data["daily_bonus_parcours"] == "p1"

        sp1 = StudentParcours.query.filter_by(user_id=uid, parcours="p1").first()
        sp2 = StudentParcours.query.filter_by(user_id=uid, parcours="p2").first()
        assert sp1.daily_completion_streak == 1
        assert sp1.last_daily_completion_date == TODAY
        assert sp2.daily_completion_streak == 0
        assert sp2.last_daily_completion_date is None

        # Vider ensuite p2 le même jour : second bonus, cumulable.
        data2 = _answer(client, q2)
        assert data2["daily_bonus"] == 150, data2
        assert data2["daily_bonus_parcours"] == "p2"
        sp2 = StudentParcours.query.filter_by(user_id=uid, parcours="p2").first()
        assert sp2.daily_completion_streak == 1


def test_no_double_bonus_same_parcours_same_day():
    app = _fresh_app()
    with app.app_context():
        uid = _make_user()
        _activate(uid, "p1", last_daily_completion_date=TODAY, daily_completion_streak=1)
        q = _make_question("p1")
        _make_due_card(uid, q)
        client = app.test_client()
        _login(client, uid)

        data = _answer(client, q)
        assert data["daily_bonus"] == 0, data


def test_streak_increments_from_yesterday():
    app = _fresh_app()
    with app.app_context():
        uid = _make_user()
        _activate(uid, "p1", last_daily_completion_date=TODAY - timedelta(days=1),
                  daily_completion_streak=3)
        q = _make_question("p1")
        _make_due_card(uid, q)
        client = app.test_client()
        _login(client, uid)

        data = _answer(client, q)
        # 150 + 20 × (streak 4 − 1)
        assert data["daily_bonus"] == 150 + 20 * 3, data
        row = StudentParcours.query.filter_by(user_id=uid, parcours="p1").first()
        assert row.daily_completion_streak == 4


def test_exam_pressure_uses_parcours_date():
    app = _fresh_app()
    with app.app_context():
        uid = _make_user()
        _activate(uid, "p1", exam_date=TODAY + timedelta(days=10))
        _activate(uid, "p2")  # sans date : aucune pression
        q1 = _make_question("p1")
        q2 = _make_question("p2", siman=2)
        # stabilité élevée → sans pression l'intervalle dépasserait 10 jours
        _make_due_card(uid, q1, stability=100.0)
        _make_due_card(uid, q2, stability=100.0)
        client = app.test_client()
        _login(client, uid)

        _answer(client, q1)
        _answer(client, q2)
        c1 = FsrsCard.query.filter_by(user_id=uid, question_id=q1.id).first()
        c2 = FsrsCard.query.filter_by(user_id=uid, question_id=q2.id).first()
        assert (c1.due_date - TODAY).days <= 10, c1.due_date  # plafonné par le מבחן de p1
        assert (c2.due_date - TODAY).days > 10, c2.due_date   # p2 sans date, pas de plafond


def test_revision_jour_selector_and_sessions():
    app = _fresh_app()
    with app.app_context():
        uid = _make_user()
        _activate(uid, "p1")
        _activate(uid, "p2")
        q1 = _make_question("p1")
        q2 = _make_question("p2", siman=2)
        _make_due_card(uid, q1)
        _make_due_card(uid, q2)
        client = app.test_client()
        _login(client, uid)

        # Deux parcours actifs → écran sélecteur avec les deux + הכל.
        html = client.get("/app/revision/jour").get_data(as_text=True)
        assert "מה נחזור היום?" in html
        assert "p1" in html and "p2" in html
        assert "הכל" in html

        # Session restreinte à p1 : la question p2 n'y figure pas.
        html_p1 = client.get("/app/revision/jour/p1").get_data(as_text=True)
        assert q1.id in html_p1
        assert q2.id not in html_p1

        # « הכל » mélange les deux parcours.
        html_all = client.get("/app/revision/jour/all").get_data(as_text=True)
        assert q1.id in html_all and q2.id in html_all

        # Parcours non activé → retour au sélecteur.
        resp = client.get("/app/revision/jour/inconnu")
        assert resp.status_code == 302


def test_revision_jour_single_parcours_goes_straight_to_session():
    app = _fresh_app()
    with app.app_context():
        uid = _make_user()
        _activate(uid, "p1")
        q1 = _make_question("p1")
        _make_due_card(uid, q1)
        client = app.test_client()
        _login(client, uid)

        html = client.get("/app/revision/jour").get_data(as_text=True)
        assert "מה נחזור היום?" not in html
        assert q1.id in html


def test_sync_student_parcours_upsert_and_delete():
    app = _fresh_app()
    with app.app_context():
        from blueprints.student import sync_student_parcours

        uid = _make_user()
        _activate(uid, "p1", exam_date=TODAY + timedelta(days=30))
        _activate(uid, "p2")

        # p1 mis à jour, p2 supprimé, p3 créé.
        sync_student_parcours(uid, {
            "p1": TODAY + timedelta(days=60),
            "p3": None,
        })
        db.session.commit()

        rows = {r.parcours: r for r in StudentParcours.query.filter_by(user_id=uid).all()}
        assert set(rows) == {"p1", "p3"}
        assert rows["p1"].exam_date == TODAY + timedelta(days=60)
        assert rows["p3"].exam_date is None


def test_legacy_fallback_creates_default_parcours():
    app = _fresh_app()
    with app.app_context():
        from blueprints.student import get_active_parcours

        uid = _make_user()
        sp = StudentProfile.query.get(uid)
        sp.exam_date = TODAY + timedelta(days=45)
        sp.daily_completion_streak = 7
        sp.last_daily_completion_date = TODAY - timedelta(days=1)
        db.session.commit()

        actifs = get_active_parcours(uid)
        assert [r.parcours for r in actifs] == ["bassar_bechalav"]
        assert actifs[0].exam_date == TODAY + timedelta(days=45)
        assert actifs[0].daily_completion_streak == 7
        assert actifs[0].last_daily_completion_date == TODAY - timedelta(days=1)


def test_content_hidden_for_inactive_parcours():
    app = _fresh_app()
    with app.app_context():
        uid = _make_user()
        _activate(uid, "p1")
        _make_question("p1")
        _make_question("p2", siman=2)  # non activé → masqué partout
        client = app.test_client()
        _login(client, uid)

        html = client.get("/app/parcours").get_data(as_text=True)
        assert "נושא p1" in html
        assert "נושא p2" not in html

        # Accès URL directe à un sujet d'un parcours non activé → redirection.
        resp = client.get("/app/chapitre/נושא p2/2")
        assert resp.status_code == 302


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
