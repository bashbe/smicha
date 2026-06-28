"""Admin / staff routes: login, dashboard, import, validation."""

from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, request, url_for

from auth_helpers import current_user, login_user, logout_user, staff_required
from blueprints.auth import create_account
from models import FsrsCard, Question, QuestionEdit, StudentProfile, User, UserAnswer, db
from question_types import (
    QUESTION_TYPES,
    normalize_imported_question,
    sync_question_row_from_payload,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

TYPE_LABEL = {
    "multiple_choice": "רב-ברירה",
    "multiple_opinions_dropdown": "התאמת פוסקים",
    "practical_scenario": "מקרה מעשי",
    "true_false": "נכון/לא נכון",
}


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mode = request.form.get("mode", "login")
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        try:
            if mode == "signup":
                if User.query.filter_by(email=email).first():
                    raise ValueError("כתובת הדוא\"ל כבר רשומה")
                if len(password) < 6:
                    raise ValueError("הסיסמה חייבת להכיל לפחות 6 תווים")
                user = create_account(email, password, None)
            else:
                user = User.query.filter_by(email=email).first()
                if not user or not user.check_password(password):
                    raise ValueError("דוא\"ל או סיסמה שגויים")
            login_user(user)
            return redirect(url_for("admin.dashboard"))
        except ValueError as e:
            flash(str(e), "error")
    return render_template("admin/login.html")


@bp.route("/denied")
def denied():
    return render_template("admin/denied.html")


@bp.route("/")
@bp.route("/dashboard")
@staff_required
def dashboard():
    qs = Question.query.with_entities(Question.status, Question.subject).all()
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    by_subject: dict[str, int] = {}
    for status, subject in qs:
        if status in counts:
            counts[status] += 1
        name = subject or "— ללא נושא —"
        by_subject[name] = by_subject.get(name, 0) + 1
    by_subject_sorted = sorted(by_subject.items(), key=lambda kv: -kv[1])
    return render_template("admin/dashboard.html", counts=counts, by_subject=by_subject_sorted)


@bp.route("/users")
@staff_required
def users():
    from sqlalchemy import func
    profiles = (
        db.session.query(StudentProfile, User)
        .join(User, User.id == StudentProfile.id)
        .order_by(StudentProfile.created_at.desc())
        .all()
    )
    card_counts = dict(
        db.session.query(FsrsCard.user_id, func.count(FsrsCard.id))
        .group_by(FsrsCard.user_id)
        .all()
    )
    return render_template("admin/users.html", profiles=profiles, card_counts=card_counts)


@bp.route("/users/<user_id>")
@staff_required
def user_detail(user_id):
    from datetime import date
    from sqlalchemy import func
    user = User.query.get_or_404(user_id)
    profile = StudentProfile.query.get(user_id)
    cards = (
        FsrsCard.query
        .filter_by(user_id=user_id)
        .join(Question, Question.id == FsrsCard.question_id)
        .add_entity(Question)
        .order_by(FsrsCard.stability.desc())
        .all()
    )
    total_answers = UserAnswer.query.filter_by(user_id=user_id).count()
    correct_answers = UserAnswer.query.filter_by(user_id=user_id, is_correct=True).count()
    today = date.today()
    due_today = sum(1 for c, _ in cards if c.due_date <= today)
    avg_stability = (
        db.session.query(func.avg(FsrsCard.stability))
        .filter_by(user_id=user_id)
        .scalar() or 0
    )
    return render_template(
        "admin/user_detail.html",
        user=user,
        profile=profile,
        cards=cards,
        total_answers=total_answers,
        correct_answers=correct_answers,
        due_today=due_today,
        avg_stability=avg_stability,
        today=today,
    )


def _extract_questions(parsed):
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
        return parsed["questions"]
    return [parsed]


@bp.route("/import", methods=["GET", "POST"])
@staff_required
def import_questions():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "preview":
            file = request.files.get("file")
            if not file:
                flash("לא נבחר קובץ", "error")
                return render_template("admin/import.html", rows=None)
            try:
                parsed = json.loads(file.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                flash("קובץ JSON שגוי: " + str(e), "error")
                return render_template("admin/import.html", rows=None)
            arr = _extract_questions(parsed)
            rows = [normalize_imported_question(q) for q in arr]
            valid_count = sum(1 for r in rows if r["valid"])
            return render_template(
                "admin/import.html",
                rows=rows,
                raw_json=json.dumps(arr, ensure_ascii=False),
                valid_count=valid_count,
                invalid_count=len(rows) - valid_count,
                type_label=TYPE_LABEL,
            )

        if action == "import":
            user = current_user()
            arr = json.loads(request.form.get("raw_json") or "[]")
            inserted = failed = 0
            for raw in arr:
                norm = normalize_imported_question(raw)
                if not norm["valid"]:
                    continue
                ins = norm["insert"]
                try:
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
                            subject=ins.get("subject"),
                            siman=ins.get("siman"),
                            seif=ins.get("seif"),
                            parcours=ins.get("parcours"),
                            status="pending",
                            created_by=user.id,
                        )
                    )
                    db.session.flush()
                    inserted += 1
                except Exception:  # noqa: BLE001
                    db.session.rollback()
                    failed += 1
            db.session.commit()
            flash(f"יובאו {inserted} שאלות" + (f" ({failed} נכשלו)" if failed else ""), "success")
            return redirect(url_for("admin.import_questions"))

    return render_template("admin/import.html", rows=None)


def _payload_from_form(form, question_type: str) -> dict:
    """Reconstruct the question payload dict from the validation form."""
    payload: dict = {
        "type": question_type,
        "difficulty_level": int(form.get("difficulty") or 2),
        "exam_section": form.getlist("section") or ["shulchan_aruch"],
        "explanation": form.get("explanation") or "",
        "tags": [t.strip() for t in (form.get("tags") or "").split(",") if t.strip()],
    }
    if form.get("source_id"):
        payload["id"] = form.get("source_id")

    if question_type in ("multiple_choice", "practical_scenario"):
        payload["question_text"] = form.get("question_text") or ""
        if question_type == "practical_scenario":
            payload["scenario_text"] = form.get("scenario_text") or ""
        correct = form.get("correct_option")
        payload["options"] = [
            {
                "number": n,
                "text": form.get(f"option_text_{n}") or "",
                "is_correct": str(n) == str(correct),
            }
            for n in (1, 2, 3, 4)
        ]
    elif question_type == "multiple_opinions_dropdown":
        payload["question_text"] = form.get("question_text") or ""
        choices = [c for c in form.getlist("dropdown_choice") if c.strip()]
        payload["dropdown_choices"] = choices
        ids = form.getlist("decisor_id")
        names = form.getlist("decisor_name")
        corrects = form.getlist("decisor_correct")
        payload["decisors"] = [
            {"id": ids[i], "name": names[i], "correct_choice": corrects[i]}
            for i in range(len(ids))
            if ids[i].strip()
        ]
    elif question_type == "true_false":
        payload["statement_text"] = form.get("statement_text") or ""
        payload["correct_answer"] = form.get("correct_answer") == "true"

    return payload


@bp.route("/validate", methods=["GET", "POST"])
@staff_required
def validate():
    if request.method == "POST":
        user = current_user()
        action = request.form.get("action")
        qid = request.form.get("question_id")
        note = (request.form.get("note") or "").strip()
        q = Question.query.get(qid)
        if q is None:
            flash("השאלה לא נמצאה", "error")
            return redirect(url_for("admin.validate"))

        previous = q.as_dict()

        if action == "reject":
            if not note:
                flash("הערה דרושה לדחייה", "error")
                return redirect(url_for("admin.validate", status="pending", q=qid))
            q.status = "rejected"
            q.validated_by = user.id
            q.validator_note = note
            db.session.add(
                QuestionEdit(question_id=q.id, editor_id=user.id, action="rejected", note=note,
                             previous_content=previous)
            )
            db.session.commit()
            flash("נדחתה", "success")
            return redirect(url_for("admin.validate", status="pending"))

        if action == "approve":
            question_type = request.form.get("question_type") or q.question_type
            payload = _payload_from_form(request.form, question_type)
            draft = {
                "payload": payload,
                "question_type": question_type,
                "difficulty": payload["difficulty_level"],
                "section": payload["exam_section"],
                "explanation": payload["explanation"],
                "tags": payload["tags"],
                "subject": (request.form.get("subject") or "").strip() or None,
                "siman": request.form.get("siman"),
                "seif": request.form.get("seif"),
                "parcours": (request.form.get("parcours") or "").strip() or q.parcours,
                "hint": request.form.get("hint"),
                "source_ref": q.source_ref,
            }
            synced = sync_question_row_from_payload(draft)
            if synced["error"]:
                flash(synced["error"], "error")
                return redirect(url_for("admin.validate", status="pending", q=qid))
            row = synced["row"]

            q.text = row["text"]
            q.question_type = row["question_type"]
            q.payload = row["payload"]
            q.choices = row["choices"]
            q.correct_answer = row["correct_answer"]
            q.explanation = row.get("explanation")
            q.hint = draft["hint"] or None
            q.subject = row.get("subject")
            q.siman = row.get("siman")
            q.seif = row.get("seif")
            q.parcours = row.get("parcours")
            q.difficulty = int(row.get("difficulty") or 2)
            q.section = row.get("section") or ["shulchan_aruch"]
            q.tags = row.get("tags") or []
            q.status = "approved"
            q.validated_by = user.id
            q.validator_note = note or None
            db.session.add(
                QuestionEdit(
                    question_id=q.id, editor_id=user.id, action="approved",
                    previous_content=previous, new_content=q.as_dict(), note=note or None,
                )
            )
            db.session.commit()
            flash("השאלה אושרה", "success")
            return redirect(url_for("admin.validate", status="pending"))

    status = request.args.get("status", "pending")
    selected_id = request.args.get("q")
    questions = (
        Question.query.filter_by(status=status).order_by(Question.created_at.asc()).all()
    )
    selected = None
    if questions:
        selected = next((q for q in questions if q.id == selected_id), questions[0])

    return render_template(
        "admin/validate.html",
        questions=questions,
        selected=selected,
        status=status,
        question_types=QUESTION_TYPES,
        type_label=TYPE_LABEL,
    )


@bp.route("/reset-db", methods=["POST"])
@staff_required
def reset_db():
    user = current_user()
    if not user.has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    confirm = (request.form.get("confirm") or "").strip()
    if confirm != "RESET":
        flash("הקלד RESET כדי לאשר את האיפוס", "error")
        return redirect(url_for("admin.dashboard"))
    db.drop_all()
    db.create_all()
    logout_user()
    flash("בסיס הנתונים אופס לחלוטין. יש להתחבר מחדש.", "success")
    return redirect(url_for("admin.login"))
