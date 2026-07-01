"""Student-facing routes: onboarding, home, parcours, chapter player, profile."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import distinct, func

from auth_helpers import current_user, login_required
from models import FsrsCard, Progression, Question, StudentProfile, UserAnswer, db
from question_types import normalize_db_question

bp = Blueprint("student", __name__, url_prefix="/app")


def _to_section_list(section) -> list[str]:
    """Normalize a section value (str or list) to a list."""
    if isinstance(section, list):
        return section or ["shulchan_aruch"]
    if isinstance(section, str) and section:
        return [section]
    return ["shulchan_aruch"]


def allowed_sections(sections) -> set[str]:
    """Return the set of section values the student has access to.
    shulchan_aruch is always included.
    """
    if not sections:
        sections = ["shulchan_aruch"]
    if isinstance(sections, str):
        sections = [sections]
    allowed: set[str] = {"shulchan_aruch"}
    for s in sections:
        allowed.add(s)
    return allowed


def question_in_sections(q, allowed: set[str]) -> bool:
    """Return True if any of the question's sections is in the allowed set."""
    return bool(set(_to_section_list(q.section)) & allowed)


def get_profile() -> StudentProfile:
    user = current_user()
    sp = StudentProfile.query.get(user.id)
    if sp is None:
        sp = StudentProfile(id=user.id, full_name=user.full_name)
        db.session.add(sp)
        db.session.commit()
    return sp


def days_to_exam(exam_date) -> int | None:
    if not exam_date:
        return None
    return max(0, (exam_date - date.today()).days)


@bp.route("/")
@login_required
def index():
    sp = get_profile()
    if not sp.onboarded:
        return redirect(url_for("student.onboarding"))
    return redirect(url_for("student.home"))


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    sp = get_profile()
    if request.method == "POST":
        exam = request.form.get("exam_date") or None
        sp.exam_date = datetime.strptime(exam, "%Y-%m-%d").date() if exam else None
        stability = request.form.get("target_stability")
        sp.target_stability = float(stability) if stability else 0.9
        sp.section = request.form.getlist("section")
        sp.onboarded = True
        db.session.commit()
        flash("הכל מוכן — בהצלחה!", "success")
        return redirect(url_for("student.home"))
    return render_template("student/onboarding.html")


@bp.route("/home")
@login_required
def home():
    sp = get_profile()
    if not sp.onboarded:
        return redirect(url_for("student.onboarding"))

    allowed = allowed_sections(sp.section)
    all_qs = (
        Question.query.filter(Question.status == "approved")
        .with_entities(Question.subject, Question.siman, Question.section)
        .all()
    )
    qs = [(subject, siman) for subject, siman, section in all_qs
          if set(_to_section_list(section)) & allowed]
    prog = {f"{p.subject}|{p.siman}": p for p in Progression.query.filter_by(user_id=sp.id).all()}

    seen, unique = set(), []
    for subject, siman in qs:
        if not subject or siman is None:
            continue
        key = f"{subject}|{siman}"
        if key in seen:
            continue
        seen.add(key)
        unique.append({"subject": subject, "siman": siman})
    unique.sort(key=lambda u: (u["subject"], u["siman"]))
    next_chapter = next(
        (u for u in unique if not prog.get(f"{u['subject']}|{u['siman']}") or prog[f"{u['subject']}|{u['siman']}"].status != "completed"),
        unique[0] if unique else None,
    )

    today = date.today()
    due_count = FsrsCard.query.filter(FsrsCard.user_id == sp.id, FsrsCard.due_date <= today).count()

    # Next scheduled revision: earliest future due_date and how many cards are due that day
    next_due_row = (
        db.session.query(FsrsCard.due_date, func.count(FsrsCard.id))
        .filter(FsrsCard.user_id == sp.id, FsrsCard.due_date > today)
        .group_by(FsrsCard.due_date)
        .order_by(FsrsCard.due_date.asc())
        .first()
    )
    next_due_date = next_due_row[0] if next_due_row else None
    next_due_count = next_due_row[1] if next_due_row else 0
    next_due_days = (next_due_date - today).days if next_due_date else None

    prep_pct = 0
    if sp.exam_date and sp.created_at:
        total = (datetime.combine(sp.exam_date, datetime.min.time()) - sp.created_at).total_seconds()
        done = (datetime.utcnow() - sp.created_at).total_seconds()
        prep_pct = min(100, max(0, (done / total) * 100)) if total > 0 else 0

    # last 7 days streak markers
    streak = sp.streak_days or 0
    last_active = sp.last_activity_date
    days7 = []
    for i in range(7):
        d = today.fromordinal(today.toordinal() - (6 - i))
        diff = (d - last_active).days if last_active else -999
        days7.append(diff <= 0 and diff > -streak)

    return render_template(
        "student/home.html",
        profile=sp,
        next_chapter=next_chapter,
        due_count=due_count,
        next_due_days=next_due_days,
        next_due_count=next_due_count,
        days_to_exam=days_to_exam(sp.exam_date),
        prep_pct=prep_pct,
        days7=days7,
    )


@bp.route("/parcours")
@login_required
def parcours():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    qs = [q for q in Question.query.filter(
        Question.status == "approved",
    ).all() if question_in_sections(q, allowed)]

    # subject → siman → seif → count
    by_subject: dict[str, dict[int, dict]] = {}
    for q in qs:
        if not q.subject or q.siman is None:
            continue
        by_subject.setdefault(q.subject, {})
        by_subject[q.subject].setdefault(q.siman, {})
        by_subject[q.subject][q.siman][q.seif] = by_subject[q.subject][q.siman].get(q.seif, 0) + 1

    _correct_filters = [
        UserAnswer.is_correct == True,
    ]
    # IDs of questions in allowed sections (Python-side filter for JSON column)
    allowed_q_ids = [q.id for q in qs]
    correct_rows = (
        db.session.query(Question.subject, Question.siman,
                         func.count(distinct(UserAnswer.question_id)))
        .join(UserAnswer, UserAnswer.question_id == Question.id)
        .filter(UserAnswer.user_id == sp.id, Question.id.in_(allowed_q_ids), *_correct_filters)
        .group_by(Question.subject, Question.siman)
        .all()
    )
    correct_map = {f"{r[0]}|{r[1]}": r[2] for r in correct_rows}

    correct_seif_rows = (
        db.session.query(Question.subject, Question.siman, Question.seif,
                         func.count(distinct(UserAnswer.question_id)))
        .join(UserAnswer, UserAnswer.question_id == Question.id)
        .filter(UserAnswer.user_id == sp.id, Question.id.in_(allowed_q_ids), *_correct_filters)
        .group_by(Question.subject, Question.siman, Question.seif)
        .all()
    )
    correct_seif_map = {f"{r[0]}|{r[1]}|{r[2]}": r[3] for r in correct_seif_rows}

    groups = []
    for subject in sorted(by_subject.keys()):
        simanim_map = by_subject[subject]
        simanim = []
        ordered = sorted(simanim_map.items())
        for idx, (siman, seif_counts) in enumerate(ordered):
            count = sum(seif_counts.values())
            correct = correct_map.get(f"{subject}|{siman}", 0)
            completed = correct >= count and count > 0
            pct = min(100, round((correct / count) * 100)) if count > 0 else 0
            locked = False
            seifim = [
                {
                    "seif": seif,
                    "count": sc,
                    "answered": correct_seif_map.get(f"{subject}|{siman}|{seif}", 0),
                    "completed": correct_seif_map.get(f"{subject}|{siman}|{seif}", 0) >= sc and sc > 0,
                }
                for seif, sc in sorted((k, v) for k, v in seif_counts.items() if k is not None)
            ]
            simanim.append({
                "siman": siman, "count": count, "answered": correct,
                "locked": locked, "pct": pct, "completed": completed,
                "seifim": seifim,
            })
        groups.append({"subject": subject, "simanim": simanim, "total": sum(s["count"] for s in simanim)})

    return render_template("student/parcours.html", groups=groups, profile=sp)


def _load_chapitre(sp, base_filters: list, allowed: set[str] | None = None) -> list | None:
    """Shared helper: fetch unanswered questions matching base_filters."""
    rows = Question.query.filter(*base_filters).order_by(Question.seif.asc()).all()
    if allowed:
        rows = [q for q in rows if question_in_sections(q, allowed)]
    if rows:
        correct_ids = {
            r[0] for r in
            db.session.query(UserAnswer.question_id)
            .filter(
                UserAnswer.user_id == sp.id,
                UserAnswer.is_correct == True,
                UserAnswer.question_id.in_([q.id for q in rows]),
            )
            .distinct()
            .all()
        }
        rows = [q for q in rows if q.id not in correct_ids]
    if not rows:
        return None
    return [
        {
            "id": q.id, "difficulty": q.difficulty, "seif": q.seif,
            "subject": q.subject, "siman": q.siman,
            "normalized": normalize_db_question(q.as_dict()),
        }
        for q in rows
    ]


@bp.route("/chapitre/<path:subject>/<int:siman>/<int:seif>")
@login_required
def chapitre_seif(subject: str, siman: int, seif: int):
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    questions = _load_chapitre(sp, [
        Question.subject == subject,
        Question.siman == siman,
        Question.seif == seif,
        Question.status == "approved",
    ], allowed)
    if questions is None:
        flash("כל השאלות בסעיף זה הושלמו! עברו לחזרות 🎓", "success")
        return redirect(url_for("student.revision"))
    return render_template(
        "student/chapitre.html",
        subject=subject,
        siman=siman,
        questions=questions,
        profile=sp,
    )


@bp.route("/chapitre/<path:subject>/<int:siman>")
@login_required
def chapitre(subject: str, siman: int):
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    questions = _load_chapitre(sp, [
        Question.subject == subject,
        Question.siman == siman,
        Question.status == "approved",
    ], allowed)
    if questions is None:
        flash("כל השאלות בסימן זה הושלמו! עברו לחזרות 🎓", "success")
        return redirect(url_for("student.revision"))
    return render_template(
        "student/chapitre.html",
        subject=subject,
        siman=siman,
        questions=questions,
        profile=sp,
    )


@bp.route("/revision")
@login_required
def revision():
    sp = get_profile()
    today = date.today()

    due_cards = (
        db.session.query(FsrsCard, Question)
        .join(Question, Question.id == FsrsCard.question_id)
        .filter(
            FsrsCard.user_id == sp.id,
            FsrsCard.due_date <= today,
            Question.status == "approved",
            )
        .order_by(FsrsCard.due_date.asc())
        .all()
    )

    questions = []
    for card, q in due_cards:
        nq = normalize_db_question(q.as_dict())
        questions.append({
            "id": q.id,
            "difficulty": q.difficulty,
            "seif": q.seif,
            "subject": q.subject,
            "siman": q.siman,
            "normalized": nq,
        })

    next_due_row = (
        db.session.query(FsrsCard.due_date, func.count(FsrsCard.id))
        .filter(FsrsCard.user_id == sp.id, FsrsCard.due_date > today)
        .group_by(FsrsCard.due_date)
        .order_by(FsrsCard.due_date.asc())
        .first()
    )
    next_due_date = next_due_row[0] if next_due_row else None
    next_due_count = next_due_row[1] if next_due_row else 0
    next_due_days = (next_due_date - today).days if next_due_date else None

    return render_template(
        "student/revision.html",
        questions=questions,
        profile=sp,
        next_due_days=next_due_days,
        next_due_count=next_due_count,
    )


@bp.post("/advance-revisions")
@login_required
def advance_revisions():
    user = current_user()
    updated = (
        db.session.query(FsrsCard)
        .filter(FsrsCard.user_id == user.id, FsrsCard.due_date > date.today())
        .all()
    )
    for card in updated:
        card.due_date = card.due_date - timedelta(days=1)
    db.session.commit()
    flash(f"הוקדמו {len(updated)} כרטיסים ביום אחד.", "success")
    return redirect(url_for("student.profil"))


@bp.post("/reset-progress")
@login_required
def reset_progress():
    user = current_user()
    from models import FsrsCard, Progression, UserAnswer
    UserAnswer.query.filter_by(user_id=user.id).delete()
    FsrsCard.query.filter_by(user_id=user.id).delete()
    Progression.query.filter_by(user_id=user.id).delete()
    sp = get_profile()
    sp.total_points = 0
    sp.streak_days = 0
    sp.last_activity_date = None
    db.session.commit()
    flash("הפרוגרס אופס בהצלחה.", "success")
    return redirect(url_for("student.profil"))


@bp.route("/profil")
@login_required
def profil():
    sp = get_profile()
    answers = UserAnswer.query.filter_by(user_id=sp.id).with_entities(UserAnswer.is_correct).all()
    total = len(answers)
    correct = sum(1 for a in answers if a.is_correct)
    accuracy = round((correct / total) * 100) if total > 0 else 0
    return render_template(
        "student/profil.html",
        profile=sp,
        total=total,
        accuracy=accuracy,
        days_to_exam=days_to_exam(sp.exam_date),
    )


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    sp = get_profile()
    if not sp.onboarded:
        return redirect(url_for("student.onboarding"))
    if request.method == "POST":
        exam = request.form.get("exam_date") or None
        sp.exam_date = datetime.strptime(exam, "%Y-%m-%d").date() if exam else None
        stability = request.form.get("target_stability")
        sp.target_stability = float(stability) if stability else sp.target_stability
        sections = request.form.getlist("section")
        if sections:
            sp.section = sections
        db.session.commit()
        flash("ההגדרות נשמרו בהצלחה.", "success")
        return redirect(url_for("student.profil"))
    return render_template("student/settings.html", profile=sp)


@bp.get("/today-stats")
@login_required
def today_stats():
    sp = get_profile()
    today = date.today()
    answers = (
        UserAnswer.query
        .filter(
            UserAnswer.user_id == sp.id,
            func.date(UserAnswer.answered_at) == today,
        )
        .all()
    )
    # Compter les cartes uniques (pas les tentatives multiples)
    seen: dict[str, bool] = {}
    for a in answers:
        if a.question_id not in seen:
            seen[a.question_id] = a.is_correct
        elif a.is_correct:
            seen[a.question_id] = True
    cards_reviewed = len(seen)
    correct_today = sum(1 for v in seen.values() if v)
    return jsonify({
        "points_today": sum(a.points_earned for a in answers),
        "cards_reviewed": cards_reviewed,
        "correct_today": correct_today,
    })
