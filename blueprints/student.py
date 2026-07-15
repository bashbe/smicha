"""Student-facing routes: onboarding, home, parcours, chapter player, profile."""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import date, datetime, timedelta

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from sqlalchemy import distinct, func

from auth_helpers import current_user, login_required
from chapter_topics import siman_topic
from models import FsrsCard, Progression, Question, QuestionReport, StudentParcours, StudentProfile, UserAnswer, db
from question_types import PARCOURS_DESCRIPTIONS, PARCOURS_LABELS, VALID_PARCOURS, normalize_db_question

bp = Blueprint("student", __name__, url_prefix="/app")


def _tag_counts(qs: list) -> dict[str, int]:
    """Count occurrences of each free-text tag among the given questions."""
    counts: dict[str, int] = {}
    for q in qs:
        for t in (q.tags or []):
            if t:
                counts[t] = counts.get(t, 0) + 1
    return counts


def _hidden_question_ids(user_id: str) -> set[str]:
    """IDs des questions que l'utilisateur a lui-même signalées et qui sont
    encore "open" — retirées uniquement pour lui tant qu'un validateur ne les
    a pas confirmées (retrait global) ou modifiées (signalement classé)."""
    rows = (
        db.session.query(QuestionReport.question_id)
        .filter(QuestionReport.reporter_id == user_id, QuestionReport.status == "open")
        .all()
    )
    return {r[0] for r in rows}


def _learned_question_ids(user_id: str) -> list[str]:
    """IDs des questions pour lesquelles l'utilisateur a au moins une réponse
    enregistrée (peu importe si correcte), tous modes de révision non-"jour"
    confondus — "déjà apprise" = au moins une tentative.
    """
    rows = (
        db.session.query(UserAnswer.question_id)
        .filter(UserAnswer.user_id == user_id)
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def _to_section_list(section) -> list[str]:
    """Normalize a section value (str or list) to a list, defaulting to shulchan_aruch."""
    if isinstance(section, list):
        return section or ["shulchan_aruch"]
    if isinstance(section, str) and section:
        return [section]
    return ["shulchan_aruch"]


def allowed_sections(sections) -> set[str]:
    """Return the set of section values the student has access to.

    shulchan_aruch is always included (mandatory baseline).
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
    """Return True if ALL of the question's sections are in the allowed set.

    A question is only shown if its section list is a subset of the student's allowed sections.
    """
    return set(_to_section_list(q.section)) <= allowed


def get_profile() -> StudentProfile:
    """Get or create the StudentProfile for the current user."""
    user = current_user()
    sp = StudentProfile.query.get(user.id)
    if sp is None:
        sp = StudentProfile(id=user.id, full_name=user.full_name)
        db.session.add(sp)
        db.session.commit()
    return sp


def days_to_exam(exam_date) -> int | None:
    """Return the number of days from today to the exam date, or None if no exam date set.

    Returned value is always >= 0 (past exam dates become 0).
    """
    if not exam_date:
        return None
    return max(0, (exam_date - date.today()).days)


def get_active_parcours(user_id: str) -> list[StudentParcours]:
    """Parcours activés par l'étudiant, triés par date d'activation.

    Fallback legacy : un profil déjà onboardé sans aucune ligne (compte
    d'avant le multi-parcours, base migrée à moitié) est automatiquement
    rattaché à bassar_bechalav en reprenant la date d'examen et la série
    quotidienne de l'ancien modèle global."""
    rows = (
        StudentParcours.query.filter_by(user_id=user_id)
        .order_by(StudentParcours.created_at.asc())
        .all()
    )
    if rows:
        return rows
    sp = StudentProfile.query.get(user_id)
    if sp is None or not sp.onboarded:
        return []
    row = StudentParcours(
        user_id=user_id,
        parcours="bassar_bechalav",
        exam_date=sp.exam_date,
        daily_completion_streak=sp.daily_completion_streak or 0,
        last_daily_completion_date=sp.last_daily_completion_date,
        created_at=sp.created_at,
    )
    db.session.add(row)
    db.session.commit()
    return [row]


def active_parcours_codes(user_id: str) -> list[str]:
    return [r.parcours for r in get_active_parcours(user_id)]


def sync_student_parcours(user_id: str, selected: dict) -> None:
    """Upsert des parcours activés : crée les manquants, met à jour la date
    d'examen des existants, supprime les lignes désélectionnées (date et
    série quotidienne perdues — les FsrsCard restent, simplement masquées).
    Ne commit pas — le caller commit."""
    existing = {r.parcours: r for r in StudentParcours.query.filter_by(user_id=user_id).all()}
    for code, exam_date in selected.items():
        row = existing.pop(code, None)
        if row is None:
            db.session.add(StudentParcours(user_id=user_id, parcours=code, exam_date=exam_date))
        else:
            row.exam_date = exam_date
    for row in existing.values():
        db.session.delete(row)


def _due_counts_by_parcours(user_id: str, codes: list[str], hidden_ids: set[str]) -> dict[str, int]:
    """Cartes dues aujourd'hui par parcours actif — même périmètre que la
    file servie par la révision du jour (questions approuvées, signalements
    "open" de l'utilisateur exclus)."""
    if not codes:
        return {}
    q = (
        db.session.query(Question.parcours, func.count(FsrsCard.id))
        .join(FsrsCard, FsrsCard.question_id == Question.id)
        .filter(
            FsrsCard.user_id == user_id,
            FsrsCard.due_date <= date.today(),
            Question.status == "approved",
            Question.parcours.in_(codes),
        )
    )
    if hidden_ids:
        q = q.filter(Question.id.notin_(hidden_ids))
    return {r[0]: r[1] for r in q.group_by(Question.parcours).all()}


def _exam_cards(actifs: list[StudentParcours]) -> list[dict]:
    """Compte à rebours + barre de préparation par parcours actif. `pct`
    court depuis l'activation du parcours (created_at), pas depuis la
    création du profil."""
    cards = []
    for r in actifs:
        pct = 0
        if r.exam_date and r.created_at:
            total = (datetime.combine(r.exam_date, datetime.min.time()) - r.created_at).total_seconds()
            done = (datetime.utcnow() - r.created_at).total_seconds()
            pct = min(100, max(0, (done / total) * 100)) if total > 0 else 0
        cards.append({
            "code": r.parcours,
            "label": PARCOURS_LABELS.get(r.parcours, r.parcours),
            "exam_date": r.exam_date,
            "days": days_to_exam(r.exam_date),
            "pct": pct,
        })
    return cards


@bp.route("/")
@login_required
def index():
    """Redirect to onboarding (if needed) or the home dashboard."""
    sp = get_profile()
    if not sp.onboarded:
        return redirect(url_for("student.onboarding"))
    return redirect(url_for("student.home"))


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    """Initial setup: student sets exam date, target stability, and study sections."""
    sp = get_profile()
    ctx = dict(
        valid_parcours=VALID_PARCOURS,
        parcours_labels=PARCOURS_LABELS,
        parcours_descriptions=PARCOURS_DESCRIPTIONS,
    )
    if request.method == "POST":
        selected = [p for p in request.form.getlist("parcours") if p in VALID_PARCOURS]
        if not selected:
            flash("יש לבחור לפחות מסלול אחד", "error")
            return render_template("student/onboarding.html", **ctx)
        dates = {}
        for code in selected:
            raw = request.form.get(f"exam_date_{code}") or None
            dates[code] = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None
        sync_student_parcours(sp.id, dates)
        stability = request.form.get("target_stability")
        sp.target_stability = float(stability) if stability else 0.95
        sp.section = request.form.getlist("section")
        sp.onboarded = True
        db.session.commit()
        flash("הכל מוכן — בהצלחה!", "success")
        return redirect(url_for("student.home"))
    return render_template("student/onboarding.html", **ctx)


def _home_greeting(due_count: int, nearest: dict | None, streak: int) -> str:
    """Message contextuel affiché sous le prénom, selon la situation de
    l'étudiant : examen imminent > cartes en attente > série active > défaut."""
    if nearest and nearest.get("days") is not None and nearest["days"] <= 7:
        return "המבחן מתקרב — הגיע הזמן להתמקד!"
    if due_count > 0:
        return "הגיע הזמן לחזור על החומר"
    if streak > 0:
        return "כל הכבוד — בואו נמשיך את ההתקדמות!"
    return "מוכנים להתחיל?"


@bp.route("/home")
@login_required
def home():
    sp = get_profile()
    if not sp.onboarded:
        return redirect(url_for("student.onboarding"))

    allowed = allowed_sections(sp.section)
    hidden_ids = _hidden_question_ids(sp.id)
    actifs = get_active_parcours(sp.id)
    codes = [r.parcours for r in actifs]
    today = date.today()

    all_qs = (
        Question.query.filter(Question.status == "approved", Question.parcours.in_(codes))
        .with_entities(Question.id, Question.parcours, Question.subject, Question.siman, Question.section)
        .all()
    )
    prog = {f"{p.subject}|{p.siman}": p for p in Progression.query.filter_by(user_id=sp.id).all()}

    # Sujets/simanim uniques par parcours (mêmes règles que /app/parcours : sections
    # autorisées + signalements personnels exclus), pour déterminer le prochain
    # chapitre à étudier PAR parcours.
    unique_by_code: dict[str, list[dict]] = {c: [] for c in codes}
    seen_by_code: dict[str, set] = {c: set() for c in codes}
    for qid, code, subject, siman, section in all_qs:
        if not subject or siman is None:
            continue
        if not (set(_to_section_list(section)) & allowed) or qid in hidden_ids:
            continue
        key = f"{subject}|{siman}"
        if key in seen_by_code[code]:
            continue
        seen_by_code[code].add(key)
        unique_by_code[code].append({"subject": subject, "siman": siman})

    # Précision / volume de réponses par parcours — quelques stats rapides par section.
    answer_rows = (
        db.session.query(Question.parcours, UserAnswer.is_correct)
        .join(UserAnswer, UserAnswer.question_id == Question.id)
        .filter(UserAnswer.user_id == sp.id, Question.parcours.in_(codes))
        .all()
        if codes else []
    )
    stats_by_code: dict[str, dict] = {c: {"total": 0, "correct": 0} for c in codes}
    for code, is_correct in answer_rows:
        stats_by_code[code]["total"] += 1
        if is_correct:
            stats_by_code[code]["correct"] += 1

    due_by_code = _due_counts_by_parcours(sp.id, codes, hidden_ids)
    exam_cards = _exam_cards(actifs)
    exam_by_code = {c["code"]: c for c in exam_cards}

    parcours_sections = []
    for r in actifs:
        code = r.parcours
        unique = sorted(unique_by_code.get(code, []), key=lambda u: (u["subject"], u["siman"]))
        next_chapter = next(
            (u for u in unique if not prog.get(f"{u['subject']}|{u['siman']}") or prog[f"{u['subject']}|{u['siman']}"].status != "completed"),
            unique[0] if unique else None,
        )
        stat = stats_by_code.get(code, {"total": 0, "correct": 0})
        accuracy = round((stat["correct"] / stat["total"]) * 100) if stat["total"] else None
        exam = exam_by_code.get(code, {})
        parcours_sections.append({
            "code": code,
            "label": PARCOURS_LABELS.get(code, code),
            "exam_date": r.exam_date,
            "days": exam.get("days"),
            "pct": exam.get("pct", 0),
            "due_count": due_by_code.get(code, 0),
            "next_chapter": next_chapter,
            "answered": stat["total"],
            "accuracy": accuracy,
        })

    due_count = sum(due_by_code.values())
    dated = [c for c in exam_cards if c["days"] is not None]
    nearest = min(dated, key=lambda c: c["days"]) if dated else None

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
        parcours_sections=parcours_sections,
        due_count=due_count,
        greeting=_home_greeting(due_count, nearest, streak),
        days7=days7,
    )


@bp.route("/parcours")
@login_required
def parcours():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    hidden_ids = _hidden_question_ids(sp.id)
    codes = active_parcours_codes(sp.id)
    qs = [q for q in Question.query.filter(
        Question.status == "approved",
        Question.parcours.in_(codes),
    ).all() if question_in_sections(q, allowed) and q.id not in hidden_ids]

    # Hiérarchie de contenu : parcours → siman → sujet (le sujet regroupe les
    # questions à l'intérieur du siman ; le seif reste indicatif).
    # by_parcours[parcours][siman][subject] = {"count", "seifim"}
    by_parcours: dict[str, dict[int, dict[str, dict]]] = {}
    for q in qs:
        if not q.parcours or not q.subject or q.siman is None:
            continue
        bucket = (
            by_parcours.setdefault(q.parcours, {})
            .setdefault(q.siman, {})
            .setdefault(q.subject, {"count": 0, "seifim": set()})
        )
        bucket["count"] += 1
        if q.seif is not None:
            bucket["seifim"].add(q.seif)

    # IDs of questions in allowed sections (Python-side filter for JSON column)
    allowed_q_ids = [q.id for q in qs]
    correct_rows = (
        db.session.query(Question.parcours, Question.siman, Question.subject,
                         func.count(distinct(UserAnswer.question_id)))
        .join(UserAnswer, UserAnswer.question_id == Question.id)
        .filter(UserAnswer.user_id == sp.id, Question.id.in_(allowed_q_ids),
                UserAnswer.is_correct == True)
        .group_by(Question.parcours, Question.siman, Question.subject)
        .all()
    )
    correct_map = {f"{r[0]}|{r[1]}|{r[2]}": r[3] for r in correct_rows}

    groups = []
    for parcours_code in sorted(by_parcours.keys()):
        simanim = []
        for siman, subjects_map in sorted(by_parcours[parcours_code].items()):
            # sujets ordonnés selon le texte : par premier seif croissant
            ordered_subjects = sorted(
                subjects_map.items(),
                key=lambda kv: (min(kv[1]["seifim"]) if kv[1]["seifim"] else 10**6, kv[0]),
            )
            sujets = []
            for subject, data in ordered_subjects:
                answered = correct_map.get(f"{parcours_code}|{siman}|{subject}", 0)
                seifim_sorted = sorted(data["seifim"])
                sujets.append({
                    "subject": subject,
                    "count": data["count"],
                    "answered": answered,
                    "completed": answered >= data["count"] and data["count"] > 0,
                    "seif_min": seifim_sorted[0] if seifim_sorted else None,
                    "seif_max": seifim_sorted[-1] if seifim_sorted else None,
                })
            count = sum(s["count"] for s in sujets)
            correct = sum(s["answered"] for s in sujets)
            simanim.append({
                "siman": siman, "count": count, "answered": correct,
                "pct": min(100, round((correct / count) * 100)) if count > 0 else 0,
                "completed": correct >= count and count > 0,
                "sujets": sujets, "topic": siman_topic(parcours_code, siman),
            })
        groups.append({
            "parcours": parcours_code,
            "label": PARCOURS_LABELS.get(parcours_code, parcours_code),
            "simanim": simanim,
            "total": sum(s["count"] for s in simanim),
        })

    # Un seul parcours affiché à la fois : le parcours actif est choisi par ?p=<code>
    # (icône de bascule en tête de page), sinon le premier groupe. Un code inconnu
    # retombe sur le premier groupe disponible.
    active_group = None
    if groups:
        requested = request.args.get("p")
        active_group = next((g for g in groups if g["parcours"] == requested), groups[0])

    return render_template(
        "student/parcours.html", groups=groups, active_group=active_group, profile=sp
    )


def _load_chapitre(sp, base_filters: list, allowed: set[str] | None = None) -> list | None:
    """Shared helper: fetch unanswered questions matching base_filters.
    Restreint aux parcours activés — bloque aussi l'accès par URL directe à
    un sujet d'un parcours non activé."""
    codes = active_parcours_codes(sp.id)
    rows = (
        Question.query.filter(Question.parcours.in_(codes), *base_filters)
        .order_by(Question.seif.asc())
        .all()
    )
    if allowed:
        rows = [q for q in rows if question_in_sections(q, allowed)]
    hidden_ids = _hidden_question_ids(sp.id)
    if hidden_ids:
        rows = [q for q in rows if q.id not in hidden_ids]
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
            "subject": q.subject, "siman": q.siman, "parcours": q.parcours, "tags": q.tags or [],
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
    codes = active_parcours_codes(sp.id)
    hidden_ids = _hidden_question_ids(sp.id)

    due_count = sum(_due_counts_by_parcours(sp.id, codes, hidden_ids).values())
    learned_ids = _learned_question_ids(sp.id)

    # Compteurs alignés sur ce que les sessions servent réellement :
    # cartes apprises restreintes aux parcours actifs / sections / signalements.
    learned_count = 0
    eligible_tags = 0
    if learned_ids:
        allowed = allowed_sections(sp.section)
        qs = [q for q in Question.query.filter(
            Question.status == "approved", Question.id.in_(learned_ids),
            Question.parcours.in_(codes),
        ).all() if question_in_sections(q, allowed) and q.id not in hidden_ids]
        learned_count = len(qs)
        counts = _tag_counts(qs)
        eligible_tags = sum(1 for c in counts.values() if c >= 3)

    return render_template(
        "student/revision_hub.html",
        profile=sp,
        due_count=due_count,
        learned_count=learned_count,
        random_count=min(10, learned_count),
        eligible_tags=eligible_tags,
    )


@bp.route("/revision/jour")
@login_required
def revision_jour():
    """Dispatcheur : session directe s'il n'y a qu'un parcours actif, sinon
    écran de choix du parcours à réviser (avec option « הכל »)."""
    sp = get_profile()
    actifs = get_active_parcours(sp.id)
    if len(actifs) <= 1:
        return _render_revision_jour(sp, actifs)

    hidden_ids = _hidden_question_ids(sp.id)
    counts = _due_counts_by_parcours(sp.id, [r.parcours for r in actifs], hidden_ids)
    items = [
        {
            "code": r.parcours,
            "label": PARCOURS_LABELS.get(r.parcours, r.parcours),
            "due": counts.get(r.parcours, 0),
        }
        for r in actifs
    ]
    return render_template(
        "student/revision_jour_select.html",
        items=items,
        total=sum(i["due"] for i in items),
        profile=sp,
    )


@bp.route("/revision/jour/<parcours_code>")
@login_required
def revision_jour_session(parcours_code: str):
    """Session de révision du jour restreinte à un parcours actif, ou à tous
    les parcours actifs avec la valeur spéciale « all »."""
    sp = get_profile()
    actifs = get_active_parcours(sp.id)
    if parcours_code == "all":
        return _render_revision_jour(sp, actifs)
    match = [r for r in actifs if r.parcours == parcours_code]
    if not match:
        return redirect(url_for("student.revision_jour"))
    return _render_revision_jour(sp, match)


def _render_revision_jour(sp, actifs: list[StudentParcours]):
    today = date.today()
    hidden_ids = _hidden_question_ids(sp.id)
    codes = [r.parcours for r in actifs]

    due_query = (
        db.session.query(FsrsCard, Question)
        .join(Question, Question.id == FsrsCard.question_id)
        .filter(
            FsrsCard.user_id == sp.id,
            FsrsCard.due_date <= today,
            Question.status == "approved",
            Question.parcours.in_(codes),
        )
    )
    if hidden_ids:
        due_query = due_query.filter(Question.id.notin_(hidden_ids))
    due_cards = due_query.order_by(FsrsCard.stability.asc()).all()

    questions = []
    for card, q in due_cards:
        nq = normalize_db_question(q.as_dict())
        questions.append({
            "id": q.id,
            "difficulty": q.difficulty,
            "seif": q.seif,
            "subject": q.subject,
            "siman": q.siman,
            "parcours": q.parcours,
            "tags": q.tags or [],
            "normalized": nq,
        })

    next_due_q = (
        db.session.query(FsrsCard.due_date, func.count(FsrsCard.id))
        .join(Question, Question.id == FsrsCard.question_id)
        .filter(
            FsrsCard.user_id == sp.id,
            FsrsCard.due_date > today,
            Question.status == "approved",
            Question.parcours.in_(codes),
        )
    )
    if hidden_ids:
        next_due_q = next_due_q.filter(Question.id.notin_(hidden_ids))
    next_due_row = next_due_q.group_by(FsrsCard.due_date).order_by(FsrsCard.due_date.asc()).first()
    next_due_date = next_due_row[0] if next_due_row else None
    next_due_count = next_due_row[1] if next_due_row else 0
    next_due_days = (next_due_date - today).days if next_due_date else None

    if len(codes) == 1:
        mode_scope_label = PARCOURS_LABELS.get(codes[0], codes[0])
    else:
        mode_scope_label = "כל המסלולים"

    return render_template(
        "student/revision_jour.html",
        questions=questions,
        profile=sp,
        next_due_days=next_due_days,
        next_due_count=next_due_count,
        mode_scope_label=mode_scope_label,
    )


@bp.route("/revision/siman")
@login_required
def revision_siman():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)
    hidden_ids = _hidden_question_ids(sp.id)
    codes = active_parcours_codes(sp.id)

    groups = []
    if learned_ids:
        qs = [q for q in Question.query.filter(
            Question.status == "approved", Question.id.in_(learned_ids),
            Question.parcours.in_(codes),
        ).all() if question_in_sections(q, allowed) and q.id not in hidden_ids]

        # Même regroupement que le sélecteur : parcours → siman → sujet
        by_parcours: dict[str, dict[int, dict[str, dict]]] = {}
        for q in qs:
            if not q.parcours or not q.subject or q.siman is None:
                continue
            bucket = (
                by_parcours.setdefault(q.parcours, {})
                .setdefault(q.siman, {})
                .setdefault(q.subject, {"count": 0, "seifim": set()})
            )
            bucket["count"] += 1
            if q.seif is not None:
                bucket["seifim"].add(q.seif)

        for parcours_code in sorted(by_parcours.keys()):
            simanim = []
            for siman, subjects_map in sorted(by_parcours[parcours_code].items()):
                ordered_subjects = sorted(
                    subjects_map.items(),
                    key=lambda kv: (min(kv[1]["seifim"]) if kv[1]["seifim"] else 10**6, kv[0]),
                )
                sujets = []
                for subject, data in ordered_subjects:
                    seifim_sorted = sorted(data["seifim"])
                    sujets.append({
                        "subject": subject,
                        "count": data["count"],
                        "seif_min": seifim_sorted[0] if seifim_sorted else None,
                        "seif_max": seifim_sorted[-1] if seifim_sorted else None,
                    })
                simanim.append({
                    "siman": siman,
                    "count": sum(s["count"] for s in sujets),
                    "sujets": sujets,
                    "topic": siman_topic(parcours_code, siman),
                })
            groups.append({
                "parcours": parcours_code,
                "label": PARCOURS_LABELS.get(parcours_code, parcours_code),
                "simanim": simanim,
            })

    return render_template("student/revision_siman_list.html", groups=groups, profile=sp)


@bp.route("/revision/siman/<path:subject>/<int:siman>")
@login_required
def revision_siman_detail(subject: str, siman: int):
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)
    hidden_ids = _hidden_question_ids(sp.id)

    codes = active_parcours_codes(sp.id)
    rows = [q for q in Question.query.filter(
        Question.subject == subject, Question.siman == siman,
        Question.status == "approved", Question.id.in_(learned_ids),
        Question.parcours.in_(codes),
    ).order_by(Question.seif.asc()).all() if question_in_sections(q, allowed) and q.id not in hidden_ids]

    if not rows:
        flash("אין עדיין כרטיסים שנלמדו בסימן זה.", "info")
        return redirect(url_for("student.revision_siman"))

    questions = [
        {
            "id": q.id, "difficulty": q.difficulty, "seif": q.seif,
            "subject": q.subject, "siman": q.siman, "parcours": q.parcours, "tags": q.tags or [],
            "normalized": normalize_db_question(q.as_dict()),
        }
        for q in rows
    ]
    return render_template(
        "student/chapitre.html", subject=subject, siman=siman, questions=questions, profile=sp,
        mode="revision_siman", mode_label="חזרה לפי סימן", is_revision=True,
        back_url=url_for("student.revision_siman"),
    )


@bp.route("/revision/sujet")
@login_required
def revision_sujet():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)
    hidden_ids = _hidden_question_ids(sp.id)

    tags = []
    if learned_ids:
        codes = active_parcours_codes(sp.id)
        qs = [q for q in Question.query.filter(
            Question.status == "approved", Question.id.in_(learned_ids),
            Question.parcours.in_(codes),
        ).all() if question_in_sections(q, allowed) and q.id not in hidden_ids]
        counts = _tag_counts(qs)
        tags = sorted(
            ({"tag": t, "count": c} for t, c in counts.items() if c >= 3),
            key=lambda x: -x["count"],
        )

    return render_template("student/revision_sujet_list.html", tags=tags, profile=sp)


@bp.route("/revision/sujet/<path:tag>")
@login_required
def revision_sujet_detail(tag: str):
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)
    hidden_ids = _hidden_question_ids(sp.id)

    codes = active_parcours_codes(sp.id)
    rows = [
        q for q in Question.query.filter(
            Question.status == "approved", Question.id.in_(learned_ids),
            Question.parcours.in_(codes),
        ).order_by(Question.subject.asc(), Question.siman.asc(), Question.seif.asc()).all()
        if question_in_sections(q, allowed) and tag in (q.tags or []) and q.id not in hidden_ids
    ]

    if not rows:
        flash("אין עדיין כרטיסים שנלמדו בנושא זה.", "info")
        return redirect(url_for("student.revision_sujet"))

    questions = [
        {
            "id": q.id, "difficulty": q.difficulty, "seif": q.seif,
            "subject": q.subject, "siman": q.siman, "parcours": q.parcours, "tags": q.tags or [],
            "normalized": normalize_db_question(q.as_dict()),
        }
        for q in rows
    ]
    return render_template(
        "student/chapitre.html", subject=tag, siman=rows[0].siman, questions=questions, profile=sp,
        mode="revision_sujet", mode_label="חזרה לפי נושא", is_revision=True,
        back_url=url_for("student.revision_sujet"),
    )


@bp.route("/revision/aleatoire")
@login_required
def revision_aleatoire():
    sp = get_profile()
    allowed = allowed_sections(sp.section)
    learned_ids = _learned_question_ids(sp.id)
    hidden_ids = _hidden_question_ids(sp.id)

    codes = active_parcours_codes(sp.id)
    rows = [q for q in Question.query.filter(
        Question.status == "approved", Question.id.in_(learned_ids),
        Question.parcours.in_(codes),
    ).all() if question_in_sections(q, allowed) and q.id not in hidden_ids]

    if not rows:
        flash("עדיין אין כרטיסים שנלמדו לחזרה אקראית.", "info")
        return redirect(url_for("student.revision"))

    sample = random.sample(rows, min(10, len(rows)))
    questions = [
        {
            "id": q.id, "difficulty": q.difficulty, "seif": q.seif,
            "subject": q.subject, "siman": q.siman, "parcours": q.parcours, "tags": q.tags or [],
            "normalized": normalize_db_question(q.as_dict()),
        }
        for q in sample
    ]
    return render_template(
        "student/chapitre.html", subject="חזרה אקראית", siman=sample[0].siman, questions=questions,
        profile=sp, mode="revision_random", mode_label="חזרה אקראית", is_revision=True,
        back_url=url_for("student.revision"),
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
    # Les parcours restent activés (dates conservées), seule la série de
    # complétion quotidienne repart de zéro.
    for row in StudentParcours.query.filter_by(user_id=user.id).all():
        row.daily_completion_streak = 0
        row.last_daily_completion_date = None
    db.session.commit()
    flash("הפרוגרס אופס בהצלחה.", "success")
    return redirect(url_for("student.profil"))


# Seuil de « maturité » d'une carte, à la manière d'Anki (intervalle ≥ 21 jours) :
# une carte dont la stabilité FSRS dépasse ce seuil est considérée bien ancrée.
MATURE_STABILITY_DAYS = 21

# Libellés hébreux des états FSRS pour la barre de maturité du profil.
STATE_LABELS = {
    "new": "חדש",
    "learning": "בלמידה",
    "review": "בשליטה",
    "relearning": "חזרה מחדש",
}
STATE_ORDER = ["review", "learning", "relearning", "new"]


def _heatmap_level(count: int) -> int:
    """Intensité 0..4 d'une case du calendrier d'activité (nb de réponses/jour)."""
    if count <= 0:
        return 0
    if count <= 2:
        return 1
    if count <= 5:
        return 2
    if count <= 10:
        return 3
    return 4


def _activity_heatmap(day_counts: dict, today: date, weeks: int = 12) -> list:
    """Grille type « contributions » : `weeks` colonnes (semaines dim.→sam.),
    la plus récente en premier (côté départ en RTL). Chaque case = un jour."""
    offset = (today.weekday() + 1) % 7  # jours écoulés depuis le dernier dimanche
    this_sunday = today - timedelta(days=offset)
    start = this_sunday - timedelta(weeks=weeks - 1)
    cols = []
    for w in range(weeks):
        col_start = start + timedelta(weeks=w)
        days = []
        for d in range(7):
            day = col_start + timedelta(days=d)
            if day > today:
                days.append({"date": None, "count": 0, "level": -1})
            else:
                c = day_counts.get(day, 0)
                days.append({"date": day.isoformat(), "count": c, "level": _heatmap_level(c)})
        cols.append(days)
    cols.reverse()  # semaine courante en premier → à droite en RTL
    return cols


def _revision_forecast(user_id: str, codes: list[str], hidden_ids: set, today: date) -> dict:
    """Prévision des cartes à réviser par jour à venir (type « Future Due »
    d'Anki). Même périmètre que la file de révision (approuvées, parcours
    actifs, signalements "open" exclus). Les cartes en retard (due ≤ aujourd'hui)
    sont regroupées sur le jour 0. Retourne le nombre de cartes dues par offset
    de jour (`daily[i]` = cartes dues dans i jours) ; le client en tire le cumul
    sur les fenêtres 7 / 30 / toute la période."""
    if not codes:
        return {"daily": [], "max_offset": 0, "overdue": 0}
    q = (
        db.session.query(FsrsCard.due_date, func.count(FsrsCard.id))
        .join(Question, Question.id == FsrsCard.question_id)
        .filter(
            FsrsCard.user_id == user_id,
            Question.status == "approved",
            Question.parcours.in_(codes),
        )
    )
    if hidden_ids:
        q = q.filter(Question.id.notin_(hidden_ids))
    rows = q.group_by(FsrsCard.due_date).all()

    counts: dict[int, int] = defaultdict(int)
    overdue = 0
    max_offset = 0
    for due, n in rows:
        if not due:
            continue
        off = (due - today).days
        if off <= 0:
            overdue += n
            off = 0
        counts[off] += n
        max_offset = max(max_offset, off)
    daily = [counts.get(i, 0) for i in range(0, max_offset + 1)]
    return {"daily": daily, "max_offset": max_offset, "overdue": overdue}


def _profile_stats(sp, codes: list[str]) -> dict:
    """Agrège les statistiques de type Anki affichées sur le profil :
    maturité des cartes, force de mémoire, activité, records de série,
    échéances, et un récapitulatif par parcours."""
    user_id = sp.id
    today = date.today()

    # --- Réponses : précision, activité quotidienne, volumes ---
    answers = (
        UserAnswer.query.filter_by(user_id=user_id)
        .with_entities(UserAnswer.is_correct, UserAnswer.answered_at)
        .all()
    )
    total_reviews = len(answers)
    correct = sum(1 for a in answers if a.is_correct)
    accuracy = round((correct / total_reviews) * 100) if total_reviews else 0

    day_counts: dict = defaultdict(int)
    for a in answers:
        if a.answered_at:
            day_counts[a.answered_at.date()] += 1
    reviews_today = day_counts.get(today, 0)
    week_start = today - timedelta(days=6)
    reviews_week = sum(c for d, c in day_counts.items() if d >= week_start)
    active_days = len(day_counts)

    # Plus longue série de jours consécutifs d'activité (record historique).
    longest_streak = 0
    if day_counts:
        days_sorted = sorted(day_counts.keys())
        run = longest_streak = 1
        for prev, cur in zip(days_sorted, days_sorted[1:]):
            run = run + 1 if (cur - prev).days == 1 else 1
            longest_streak = max(longest_streak, run)

    # --- Cartes FSRS : maturité, force de mémoire, échéances ---
    cards = (
        db.session.query(FsrsCard.state, FsrsCard.stability, FsrsCard.due_date, Question.parcours)
        .join(Question, Question.id == FsrsCard.question_id)
        .filter(FsrsCard.user_id == user_id, Question.parcours.in_(codes))
        .all()
        if codes else []
    )
    state_counts = {"new": 0, "learning": 0, "review": 0, "relearning": 0}
    stabilities = []
    mature = due_today = due_week = 0
    per_parcours_cards: dict = defaultdict(int)
    for state, stability, due, parcours in cards:
        state_counts[state] = state_counts.get(state, 0) + 1
        per_parcours_cards[parcours] += 1
        if stability:
            stabilities.append(stability)
            if stability >= MATURE_STABILITY_DAYS:
                mature += 1
        if due:
            if due <= today:
                due_today += 1
            elif due <= today + timedelta(days=7):
                due_week += 1
    total_cards = len(cards)
    avg_stability = round(sum(stabilities) / len(stabilities)) if stabilities else 0

    total_state = sum(state_counts.values()) or 1
    maturity = [
        {
            "state": s,
            "label": STATE_LABELS.get(s, s),
            "count": state_counts.get(s, 0),
            "pct": round(state_counts.get(s, 0) / total_state * 100, 1),
        }
        for s in STATE_ORDER
    ]

    completed_subjects = (
        Progression.query.filter_by(user_id=user_id, status="completed").count()
    )

    # --- Précision par parcours (récap' par מסלול) ---
    acc_rows = (
        db.session.query(Question.parcours, UserAnswer.is_correct)
        .join(UserAnswer, UserAnswer.question_id == Question.id)
        .filter(UserAnswer.user_id == user_id, Question.parcours.in_(codes))
        .all()
        if codes else []
    )
    acc_by_code: dict = defaultdict(lambda: {"total": 0, "correct": 0})
    for parcours, is_correct in acc_rows:
        acc_by_code[parcours]["total"] += 1
        if is_correct:
            acc_by_code[parcours]["correct"] += 1

    hidden_ids = _hidden_question_ids(user_id)
    due_by_code = _due_counts_by_parcours(user_id, codes, hidden_ids)
    per_parcours = []
    for code in codes:
        a = acc_by_code.get(code, {"total": 0, "correct": 0})
        per_parcours.append({
            "code": code,
            "label": PARCOURS_LABELS.get(code, code),
            "cards": per_parcours_cards.get(code, 0),
            "answered": a["total"],
            "accuracy": round((a["correct"] / a["total"]) * 100) if a["total"] else None,
            "due": due_by_code.get(code, 0),
        })

    return {
        "accuracy": accuracy,
        "total_reviews": total_reviews,
        "reviews_today": reviews_today,
        "reviews_week": reviews_week,
        "active_days": active_days,
        "longest_streak": longest_streak,
        "total_cards": total_cards,
        "mature_cards": mature,
        "avg_stability": avg_stability,
        "due_today": due_today,
        "due_week": due_week,
        "completed_subjects": completed_subjects,
        "maturity": maturity,
        "per_parcours": per_parcours,
        "heatmap": _activity_heatmap(day_counts, today),
        "forecast": _revision_forecast(user_id, codes, hidden_ids, today),
    }


@bp.route("/profil")
@login_required
def profil():
    sp = get_profile()
    actifs = get_active_parcours(sp.id)
    codes = [r.parcours for r in actifs]
    stats = _profile_stats(sp, codes)
    return render_template(
        "student/profil.html",
        profile=sp,
        total=stats["total_reviews"],
        accuracy=stats["accuracy"],
        stats=stats,
        exam_cards=_exam_cards(actifs),
    )


@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    sp = get_profile()
    if not sp.onboarded:
        return redirect(url_for("student.onboarding"))
    if request.method == "POST":
        selected = [p for p in request.form.getlist("parcours") if p in VALID_PARCOURS]
        if not selected:
            flash("יש לבחור לפחות מסלול אחד", "error")
        else:
            dates = {}
            for code in selected:
                raw = request.form.get(f"exam_date_{code}") or None
                dates[code] = datetime.strptime(raw, "%Y-%m-%d").date() if raw else None
            sync_student_parcours(sp.id, dates)
            stability = request.form.get("target_stability")
            sp.target_stability = float(stability) if stability else sp.target_stability
            sections = request.form.getlist("section")
            if sections:
                sp.section = sections
            db.session.commit()
            flash("ההגדרות נשמרו בהצלחה.", "success")
            return redirect(url_for("student.profil"))
    active_map = {r.parcours: r for r in get_active_parcours(sp.id)}
    return render_template(
        "student/settings.html",
        profile=sp,
        valid_parcours=VALID_PARCOURS,
        parcours_labels=PARCOURS_LABELS,
        parcours_descriptions=PARCOURS_DESCRIPTIONS,
        active_map=active_map,
    )


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
