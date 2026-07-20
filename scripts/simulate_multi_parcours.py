"""Simulation « multi-parcours » — génère une base de démonstration montrant à
quoi ressemble l'app quand un étudiant a **plusieurs parcours entamés** en
parallèle, puis sert l'application sur cette base pour capture d'écran.

Ce script est **isolé** : il écrit dans sa propre base SQLite (``sim_multi.db``)
et n'altère jamais la base réelle ni le catalogue de production. Les parcours
supplémentaires (au-delà de ``bassar_bechalav``) sont injectés à l'exécution
dans les dictionnaires d'affichage — ils ne sont pas ajoutés à ``VALID_PARCOURS``
pour ne pas polluer l'onboarding réel.

Usage :
    python -m scripts.simulate_multi_parcours build   # (re)génère sim_multi.db
    python -m scripts.simulate_multi_parcours serve   # sert l'app sur sim_multi.db
"""

from __future__ import annotations

import math
import os
import random
import sys
from datetime import date, datetime, timedelta

# --- Base de simulation dédiée : fixer AVANT d'importer l'app/les modèles ---
SIM_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sim_multi.db")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + SIM_DB_PATH)

import question_types as qt  # noqa: E402

# Parcours de démonstration ajoutés au-dessus de bassar_bechalav (affichage seul).
SIM_PARCOURS = {
    "taarovot": {
        "label": "תערובות",
        "description": "הלכות תערובות איסור והיתר",
    },
    "melicha": {
        "label": "מליחה",
        "description": "הלכות מליחת הבשר והכשרתו",
    },
}
# Injection runtime des libellés/descriptions + VALID_PARCOURS (pour la
# validation à l'import). Uniquement dans ce processus de simulation isolé —
# le catalogue de production (question_types.py) reste inchangé.
qt.PARCOURS_LABELS.update({k: v["label"] for k, v in SIM_PARCOURS.items()})
qt.PARCOURS_DESCRIPTIONS.update({k: v["description"] for k, v in SIM_PARCOURS.items()})
qt.VALID_PARCOURS = tuple(qt.VALID_PARCOURS) + tuple(SIM_PARCOURS)

from app import create_app  # noqa: E402
from models import (  # noqa: E402
    FsrsCard,
    ItemStats,
    Progression,
    Question,
    StudentParcours,
    StudentProfile,
    User,
    UserRole,
    db,
)
from subjects import get_or_create_subject  # noqa: E402

SIM_EMAIL = "demo-multi@example.com"
SIM_PASSWORD = "password123"
SIM_NAME = "יוסף כהן"

# ---------------------------------------------------------------------------
# Contenu : chaque parcours = quelques simanim, chacun avec des sujets et des
# questions à choix multiple en hébreu (format d'import, validé à la volée).
# ---------------------------------------------------------------------------
CONTENT = {
    "bassar_bechalav": {
        "sections": ["shulchan_aruch"],
        "simanim": {
            89: {
                "משך ההמתנה בין בשר לחלב": [
                    ("כמה שעות נהגו בני אשכנז להמתין בין בשר לחלב?", ["שעה", "שלוש שעות", "שש שעות", "אין צורך"], 2, ["המתנה"]),
                    ("מה מקור מנהג ההמתנה שש שעות?", ["מהתורה", "מדברי חכמים", "ממנהג", "מהגאונים"], 1, ["המתנה"]),
                    ("האם ממתינים גם לאחר עוף?", ["כן", "לא", "רק לספרדים", "מחלוקת"], 0, ["עוף"]),
                ],
                "בשר שנתעכל": [
                    ("מי שנשאר לו בשר בין השיניים, עד מתי נחשב בשר?", ["עד שעה", "עד שש שעות", "כל היום", "עד שיסירנו"], 3, ["שיניים"]),
                ],
            },
            91: {
                "אכילת גבינה אחר בשר": [
                    ("מהו הדין באכילת גבינה קשה מיד לאחר בשר?", ["מותר", "אסור עד המתנה", "רק בהדחה", "מחלוקת"], 1, ["גבינה"]),
                    ("האם צריך קינוח והדחה בין בשר לגבינה רכה?", ["כן", "לא", "רק קינוח", "רק הדחה"], 0, ["קינוח"]),
                ],
            },
        },
    },
    "taarovot": {
        "sections": ["shulchan_aruch"],
        "simanim": {
            98: {
                "ביטול בשישים": [
                    ("איסור שנתערב בהיתר מתבטל ביחס של?", ["אחד בשניים", "אחד בשישים", "אחד במאה", "אינו מתבטל"], 1, ["ביטול"]),
                    ("האם טעם כעיקר מהתורה או מדרבנן?", ["מהתורה", "מדרבנן", "מחלוקת", "מנהג"], 2, ["טעם"]),
                    ("מין במינו לפי מה מתבטל לרוב הפוסקים?", ["בשישים", "ברוב", "במאה", "אינו בטל"], 0, ["מין במינו"]),
                ],
                "דבר שיש לו מתירין": [
                    ("דבר שיש לו מתירין מתבטל?", ["בשישים", "ברוב", "אפילו באלף לא בטל", "במאה"], 2, ["מתירין"]),
                ],
            },
            99: {
                "חתיכה הראויה להתכבד": [
                    ("חתיכה הראויה להתכבד מתבטלת?", ["בשישים", "ברוב", "אינה בטלה", "במאה"], 2, ["חתיכה"]),
                    ("האם ביטול חל על דבר חשוב?", ["כן", "לא, חשיבותו מונעת", "רק בלח", "מחלוקת"], 1, ["חשוב"]),
                ],
            },
        },
    },
    "melicha": {
        "sections": ["shulchan_aruch"],
        "simanim": {
            69: {
                "שיעור מליחה": [
                    ("כמה זמן משהים הבשר במלח להוצאת הדם?", ["רגע", "כשיעור מיל", "שעה", "יום"], 1, ["מליחה"]),
                    ("האם מדיחים הבשר לפני המליחה?", ["כן", "לא", "רק בקיץ", "מחלוקת"], 0, ["הדחה"]),
                    ("מלח גס או דק עדיף למליחה?", ["דק", "גס", "אין הבדל", "תלוי"], 1, ["מלח"]),
                ],
            },
            70: {
                "מליחת דגים ובשר יחד": [
                    ("האם מולחים דג ובשר יחד?", ["כן", "לא, בולע", "רק בכלי נפרד", "מחלוקת"], 1, ["דגים"]),
                ],
                "כבד וצליה": [
                    ("כיצד מכשירים כבד מן הדם?", ["מליחה", "צליה על האש", "הדחה", "בישול"], 1, ["כבד"]),
                    ("מדוע אין די במליחה לכבד?", ["ריבוי דם", "טעם", "מנהג", "גזירה"], 0, ["כבד"]),
                ],
            },
        },
    },
}


# Nombre minimal de questions par parcours dans la démo : garantit assez de
# cartes apprises pour dépasser le palier d'affichage des stats (STATS_MIN_CARDS).
MIN_Q_PER_PARCOURS = 16
_FILLER_OPTS = ["תשובה ראשונה", "תשובה שנייה", "תשובה שלישית", "תשובה רביעית"]


def _insert_mc(parcours, subject, siman, seif, difficulty, sections, text, opts, correct_idx, tags):
    """Valide (format d'import) puis insère une question à choix multiple."""
    raw = {
        "type": "multiple_choice", "parcours": parcours, "sujet": subject,
        "siman": siman, "seif": seif, "difficulty_level": difficulty,
        "exam_section": sections, "question_text": text,
        "options": [{"number": i + 1, "text": o, "is_correct": i == correct_idx}
                    for i, o in enumerate(opts)],
        "explanation": "הסבר לדוגמה עבור " + subject + ".", "tags": tags,
    }
    norm = qt.normalize_imported_question(raw)
    if not norm["valid"]:
        raise SystemExit(f"question invalide ({parcours} {siman}): {norm['issue']}")
    ins = norm["insert"]
    subj = get_or_create_subject(ins.get("parcours"), ins.get("siman"), ins.get("subject"))
    q = Question(
        question_type=ins["question_type"], text=ins["text"], payload=ins["payload"],
        choices=ins["choices"], correct_answer=ins["correct_answer"],
        explanation=ins["explanation"], difficulty=ins["difficulty"],
        section=ins["section"], tags=ins["tags"], source_ref=ins["source_ref"],
        subject_id=subj.id, siman=ins.get("siman"), seif=ins.get("seif"),
        parcours=ins.get("parcours"), status="approved",
    )
    db.session.add(q)
    db.session.flush()
    db.session.add(ItemStats(question_id=q.id, question_type=q.question_type,
                             hidden_difficulty=q.difficulty))
    return q


def _build_questions() -> dict[str, list[dict]]:
    """Insère les questions de CONTENT (+ complément de tirage pour atteindre
    MIN_Q_PER_PARCOURS), retourne les Question par parcours."""
    by_parcours: dict[str, list[dict]] = {c: [] for c in CONTENT}
    for parcours, cfg in CONTENT.items():
        for siman, subjects in cfg["simanim"].items():
            for _, (subject, items) in enumerate(subjects.items(), start=1):
                for q_seif, (text, opts, correct_idx, tags) in enumerate(items, start=1):
                    by_parcours[parcours].append(_insert_mc(
                        parcours, subject, siman, q_seif, (q_seif % 3) + 1,
                        cfg["sections"], text, opts, correct_idx, tags))
        # Complément générique (« חזרה ותרגול ») pour avoir un socle de cartes.
        extra = 1
        while len(by_parcours[parcours]) < MIN_Q_PER_PARCOURS:
            by_parcours[parcours].append(_insert_mc(
                parcours, "חזרה ותרגול", 100, extra, (extra % 3) + 1,
                cfg["sections"], f"שאלת תרגול מספר {extra} לחזרה על החומר",
                _FILLER_OPTS, extra % 4, ["תרגול"]))
            extra += 1
    db.session.commit()
    return by_parcours


# Profil de progression par parcours : (fraction de cartes engagées, jours d'ancienneté).
# Le premier parcours est le plus avancé, le dernier vient d'être entamé.
PARCOURS_PROGRESS = {
    "bassar_bechalav": {"exam_in": 42, "engaged": 1.0, "maturity": "high"},
    "taarovot": {"exam_in": 6, "engaged": 0.75, "maturity": "mid"},   # examen imminent
    "melicha": {"exam_in": 90, "engaged": 0.4, "maturity": "low"},    # tout juste commencé
}


def _card_profile(maturity: str, idx: int, total: int):
    """Retourne (state, stability, reps, lapses, due_offset_days) pour varier
    les cartes de façon crédible selon la maturité globale du parcours."""
    r = (idx + 1) / max(total, 1)
    if maturity == "high":
        if r < 0.55:
            return "review", random.uniform(30, 120), random.randint(4, 9), random.randint(0, 1), random.randint(2, 21)
        if r < 0.8:
            return "review", random.uniform(12, 28), random.randint(3, 5), 0, random.randint(0, 5)
        return "learning", random.uniform(1, 6), random.randint(1, 2), 0, 0
    if maturity == "mid":
        if r < 0.35:
            return "review", random.uniform(22, 60), random.randint(3, 6), 0, random.randint(1, 10)
        if r < 0.7:
            return "review", random.uniform(6, 18), random.randint(2, 4), random.randint(0, 1), random.randint(0, 3)
        if r < 0.9:
            return "learning", random.uniform(1, 5), 1, 0, 0
        return "relearning", random.uniform(0.5, 2), random.randint(2, 3), random.randint(1, 2), 0
    # low
    if r < 0.5:
        return "learning", random.uniform(1, 4), 1, 0, 0
    if r < 0.85:
        return "review", random.uniform(4, 14), 2, 0, random.randint(0, 4)
    return "relearning", random.uniform(0.4, 1.5), 2, 1, 0


CURRENT_STREAK = 6   # série de jours consécutifs se terminant aujourd'hui
RECORD_STREAK = 11   # plus longue série passée (record historique)


def _activity_plan(today: date) -> dict[date, int]:
    """Journal d'activité (jour → nombre de réponses). Chaque jour de série a au
    moins une réponse pour que la série calculée corresponde à l'affichage :
    série courante (6 j consécutifs), record passé (11 j), et jours épars."""
    plan: dict[date, int] = {}
    # Série courante : CURRENT_STREAK derniers jours consécutifs (dont aujourd'hui)
    for i in range(CURRENT_STREAK):
        plan[today - timedelta(days=i)] = random.randint(2, 6)
    # Record : série de RECORD_STREAK jours consécutifs il y a ~3-4 semaines
    for i in range(RECORD_STREAK):
        plan[today - timedelta(days=20 + i)] = random.randint(3, 7)
    # Jours épars sur les 10 dernières semaines
    for d in (9, 11, 14, 15, 16, 38, 40, 45, 46, 52, 58, 60, 63):
        plan[today - timedelta(days=d)] = random.randint(1, 3)
    return plan


def _mk_answer(user_id, question_id, correct, rt, pts, answered_at):
    """Fabrique un UserAnswer (helper compact pour la lisibilité de la boucle)."""
    from models import UserAnswer
    return UserAnswer(
        user_id=user_id, question_id=question_id, given_answer="—",
        is_correct=correct, response_time_ms=rt, points_earned=pts,
        combo_at_time=0, answered_at=answered_at,
    )


def _seed_student(by_parcours: dict[str, list[dict]]) -> None:
    today = date.today()
    now = datetime.utcnow()

    user = User(email=SIM_EMAIL, full_name=SIM_NAME)
    user.set_password(SIM_PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(UserRole(user_id=user.id, role="student"))

    profile = StudentProfile(
        id=user.id, full_name=SIM_NAME, onboarded=True, target_stability=0.95,
        section=["shulchan_aruch"], streak_days=6, last_activity_date=today,
        total_points=0,
    )
    db.session.add(profile)

    # Parcours actifs (dates d'activation échelonnées : le 1er est le plus ancien).
    for offset, (code, prog) in zip((70, 30, 9), PARCOURS_PROGRESS.items()):
        db.session.add(StudentParcours(
            user_id=user.id, parcours=code,
            exam_date=today + timedelta(days=prog["exam_in"]),
            daily_completion_streak=6 if code == "bassar_bechalav" else 0,
            last_daily_completion_date=today if code == "bassar_bechalav" else None,
            created_at=now - timedelta(days=offset),
        ))

    total_points = 0
    completed_by_parcours: dict[str, set] = {}

    # --- Cartes FSRS : une par question engagée, état/stabilité variés ---
    engaged_pool: list[dict] = []  # {q, state} pour tirer les réponses ensuite
    for code, prog in PARCOURS_PROGRESS.items():
        questions = by_parcours[code]
        n_engaged = max(1, math.floor(len(questions) * prog["engaged"]))
        engaged = questions[:n_engaged]
        for idx, q in enumerate(engaged):
            state, stability, reps, lapses, due_off = _card_profile(prog["maturity"], idx, len(engaged))
            rt = random.randint(4000, 16000)
            db.session.add(FsrsCard(
                user_id=user.id, question_id=q.id, state=state,
                stability=round(stability, 2), fsrs_difficulty=round(random.uniform(3, 8), 2),
                reps=reps, lapses=lapses, due_date=today + timedelta(days=due_off),
                last_review=now - timedelta(days=random.randint(0, 5)),
                avg_response_time_ms=rt, target_stability=0.95,
            ))
            engaged_pool.append({"q": q, "state": state})
            # Sujets complétés (les cartes matures du parcours le plus avancé).
            if state == "review" and stability > 25:
                completed_by_parcours.setdefault(code, set()).add(q.subject_id)

    # --- Réponses réparties selon le journal d'activité (couvre chaque jour de
    # série pour que rצף שיא ≥ rצף נוכחי et que le heatmap soit crédible) ---
    for d, n in _activity_plan(today).items():
        for _ in range(n):
            pick = random.choice(engaged_pool)
            q, state = pick["q"], pick["state"]
            rt = random.randint(4000, 16000)
            correct = random.random() < (0.85 if state == "review" else 0.6)
            pts = random.randint(12, 28) if correct else 0
            total_points += pts
            db.session.add(_mk_answer(user.id, q.id, correct, rt, pts,
                                      datetime.combine(d, datetime.min.time())
                                      + timedelta(hours=random.randint(7, 22))))

    # Progression "completed" pour quelques sujets bien ancrés.
    for code, subject_ids in completed_by_parcours.items():
        for subject_id in subject_ids:
            db.session.add(Progression(
                user_id=user.id, subject_id=subject_id, status="completed",
                questions_answered=3, average_score=0.9,
            ))

    profile.total_points = total_points
    db.session.commit()
    print(f"seeded student {SIM_EMAIL} / {SIM_PASSWORD} — {total_points} points, "
          f"{len(PARCOURS_PROGRESS)} parcours actifs")


NEW_EMAIL = "demo-new@example.com"
NEW_NAME = "אברהם לוי"
NEW_CARDS = 8  # < STATS_MIN_CARDS (30) → profil en état « stats verrouillées »


def _seed_new_student(by_parcours: dict[str, list[dict]]) -> None:
    """Débutant : un seul parcours, quelques cartes seulement (< palier de
    stats) — sert à illustrer le profil quand le tableau de bord est verrouillé."""
    today = date.today()
    now = datetime.utcnow()
    user = User(email=NEW_EMAIL, full_name=NEW_NAME)
    user.set_password(SIM_PASSWORD)
    db.session.add(user)
    db.session.flush()
    db.session.add(UserRole(user_id=user.id, role="student"))
    db.session.add(StudentProfile(
        id=user.id, full_name=NEW_NAME, onboarded=True, target_stability=0.95,
        section=["shulchan_aruch"], streak_days=2, last_activity_date=today, total_points=0,
    ))
    db.session.add(StudentParcours(
        user_id=user.id, parcours="bassar_bechalav",
        exam_date=today + timedelta(days=60), created_at=now - timedelta(days=4),
    ))
    total_points = 0
    for i, q in enumerate(by_parcours["bassar_bechalav"][:NEW_CARDS]):
        state = "review" if i < 3 else "learning"
        rt = random.randint(5000, 15000)
        db.session.add(FsrsCard(
            user_id=user.id, question_id=q.id, state=state,
            stability=round(random.uniform(1, 8), 2), fsrs_difficulty=round(random.uniform(4, 7), 2),
            reps=random.randint(1, 3), lapses=0, due_date=today + timedelta(days=random.randint(0, 3)),
            last_review=now - timedelta(days=random.randint(0, 3)),
            avg_response_time_ms=rt, target_stability=0.95,
        ))
        for d in range(min(3, i + 1)):  # activité sur les derniers jours
            correct = random.random() < 0.7
            pts = random.randint(12, 24) if correct else 0
            total_points += pts
            db.session.add(_mk_answer(user.id, q.id, correct, rt, pts,
                                      datetime.combine(today - timedelta(days=d), datetime.min.time())
                                      + timedelta(hours=random.randint(8, 21))))
    db.session.query(StudentProfile).filter_by(id=user.id).update({"total_points": total_points})
    db.session.commit()
    print(f"seeded débutant {NEW_EMAIL} / {SIM_PASSWORD} — {NEW_CARDS} cartes (stats verrouillées)")


def build() -> None:
    random.seed(42)
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        by_parcours = _build_questions()
        _seed_student(by_parcours)
        _seed_new_student(by_parcours)
        print(f"base de simulation prête : {SIM_DB_PATH}")


def serve() -> None:
    app = create_app()
    port = int(os.environ.get("FLASK_PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "build":
        build()
    elif cmd == "serve":
        serve()
    else:
        raise SystemExit("usage: simulate_multi_parcours.py [build|serve]")
