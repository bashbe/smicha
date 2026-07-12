"""Admin / staff routes: login, dashboard, import, validation."""

from __future__ import annotations

import json

from flask import Blueprint, Response, flash, redirect, render_template, request, url_for

from auth_helpers import current_user, login_user, logout_user, staff_required
from blueprints.auth import create_account
from chapter_topics import save_topics
from chapter_topics import seif_topic as get_seif_topic
from chapter_topics import siman_topic as get_siman_topic
from models import FsrsCard, Progression, Question, QuestionEdit, StudentProfile, User, UserAnswer, db
from question_types import (
    PARCOURS_LABELS,
    QUESTION_TYPES,
    normalize_imported_question,
    sync_question_row_from_payload,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")

TYPE_LABEL = {
    "multiple_choice": "רב-ברירה",
    "multiple_opinions_dropdown": "התאמת פוסקים",
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


@bp.route("/subjects/rename", methods=["POST"])
@staff_required
def rename_subject():
    """Renames a subject (`sujet`) across every card sharing that exact title.

    Acts as a search-and-replace on Question.subject; matching Progression
    rows are updated in tandem so existing student progress stays linked to
    the renamed subject instead of silently orphaning.
    """
    user = current_user()
    old_subject = (request.form.get("old_subject") or "").strip()
    new_subject = (request.form.get("new_subject") or "").strip()

    if not old_subject or not new_subject:
        flash("יש להזין שם נושא חדש", "error")
        return redirect(url_for("admin.dashboard"))
    if old_subject == new_subject:
        flash("השם החדש זהה לשם הקיים", "error")
        return redirect(url_for("admin.dashboard"))

    matching = Question.query.filter_by(subject=old_subject).all()
    if not matching:
        flash(f'לא נמצאו שאלות עם הנושא "{old_subject}"', "error")
        return redirect(url_for("admin.dashboard"))

    note = f'שינוי שם נושא: "{old_subject}" ← "{new_subject}"'
    for q in matching:
        previous = q.as_dict()
        q.subject = new_subject
        db.session.add(
            QuestionEdit(
                question_id=q.id, editor_id=user.id, action="edited",
                previous_content=previous, new_content=q.as_dict(), note=note,
            )
        )

    Progression.query.filter_by(subject=old_subject).update({"subject": new_subject})

    db.session.commit()
    flash(f'{len(matching)} שאלות עודכנו: "{old_subject}" ← "{new_subject}"', "success")
    return redirect(url_for("admin.dashboard"))


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
                            status="approved",
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

    if question_type == "multiple_choice":
        payload["question_text"] = form.get("question_text") or ""
        try:
            correct_indices = set(json.loads(form.get("correct_options") or "[]"))
        except (ValueError, TypeError):
            correct_indices = set()
        payload["options"] = [
            {
                "number": i,
                "text": text,
                "is_correct": i in correct_indices,
            }
            for i, text in enumerate(form.getlist("option_text"), start=1)
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


@bp.route("/validate")
@staff_required
def validate_redirect():
    """Legacy bookmarks/links: /admin/validate now lives in the unified /admin/questions tab."""
    return redirect(url_for("admin.questions", status=request.args.get("status", "pending")))


@bp.route("/validate/approve-all", methods=["POST"])
@staff_required
def approve_all_pending():
    user = current_user()
    pending = Question.query.filter_by(status="pending").all()
    for q in pending:
        previous = q.as_dict()
        q.status = "approved"
        q.validated_by = user.id
        db.session.add(
            QuestionEdit(
                question_id=q.id, editor_id=user.id, action="approved",
                previous_content=previous, new_content=q.as_dict(),
                note="אישור גורף של כל השאלות הממתינות",
            )
        )
    db.session.commit()
    flash(f"{len(pending)} שאלות אושרו", "success")
    return redirect(url_for("admin.questions", status="pending"))


@bp.route("/export/rejected")
@staff_required
def export_rejected():
    questions = Question.query.filter_by(status="rejected").order_by(Question.created_at.desc()).all()
    data = []
    for q in questions:
        d = q.as_dict()
        d["validator_note"] = q.validator_note
        data.append(d)
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(
        payload,
        mimetype="application/json",
        headers={"Content-Disposition": "attachment; filename=rejected_questions.json"},
    )


@bp.route("/questions")
@staff_required
def questions():
    from sqlalchemy import or_

    status = request.args.get("status", "")
    qtype = request.args.get("type", "")
    parcours_filter = request.args.get("parcours", "")
    search = request.args.get("q", "").strip()
    siman_filter = request.args.get("siman", "").strip()
    seif_filter = request.args.get("seif", "").strip()
    tag_filter = request.args.get("tag", "").strip()
    selected_id = request.args.get("id", "")

    query = Question.query
    if status:
        query = query.filter_by(status=status)
    if qtype:
        query = query.filter_by(question_type=qtype)
    if parcours_filter:
        query = query.filter_by(parcours=parcours_filter)
    if siman_filter:
        try:
            query = query.filter_by(siman=int(siman_filter))
        except ValueError:
            flash("סימן חייב להיות מספר", "error")
            siman_filter = ""
    if seif_filter:
        try:
            query = query.filter_by(seif=int(seif_filter))
        except ValueError:
            flash("סעיף חייב להיות מספר", "error")
            seif_filter = ""
    if search:
        query = query.filter(
            or_(
                Question.subject.ilike(f"%{search}%"),
                Question.text.ilike(f"%{search}%"),
            )
        )
    all_questions = query.order_by(Question.created_at.desc()).all()

    if tag_filter:
        needle = tag_filter.lower()
        all_questions = [q for q in all_questions if any(needle in (t or "").lower() for t in (q.tags or []))]

    selected = None
    if all_questions:
        selected = next((q for q in all_questions if q.id == selected_id), all_questions[0])

    filters = {
        "status": status, "type": qtype, "parcours": parcours_filter,
        "q": search, "siman": siman_filter, "seif": seif_filter, "tag": tag_filter,
    }
    return render_template(
        "admin/questions.html",
        questions=all_questions,
        selected=selected,
        filters=filters,
        question_types=QUESTION_TYPES,
        type_label=TYPE_LABEL,
    )


@bp.route("/questions/<qid>/edit", methods=["POST"])
@staff_required
def edit_question(qid):
    user = current_user()
    q = Question.query.get_or_404(qid)
    action = request.form.get("action", "save")
    note = (request.form.get("note") or "").strip()
    previous = q.as_dict()

    redirect_params = {
        "status": request.form.get("filter_status", ""),
        "type": request.form.get("filter_type", ""),
        "parcours": request.form.get("filter_parcours", ""),
        "q": request.form.get("filter_q", ""),
        "siman": request.form.get("filter_siman", ""),
        "seif": request.form.get("filter_seif", ""),
        "tag": request.form.get("filter_tag", ""),
        "id": qid,
    }

    if action == "reject":
        if not note:
            flash("הערה דרושה לדחייה", "error")
            return redirect(url_for("admin.questions", **redirect_params))
        q.status = "rejected"
        q.validated_by = user.id
        q.validator_note = note
        db.session.add(
            QuestionEdit(
                question_id=q.id, editor_id=user.id, action="rejected",
                note=note, previous_content=previous,
            )
        )
        db.session.commit()
        flash("נדחתה", "success")
        return redirect(url_for("admin.questions", **redirect_params))

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
        "source_ref": (request.form.get("source_ref") or "").strip() or None,
    }
    synced = sync_question_row_from_payload(draft)
    if synced["error"]:
        flash(synced["error"], "error")
        return redirect(url_for("admin.questions", **redirect_params))

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
    q.source_ref = draft["source_ref"]
    q.validator_note = note or None

    if action == "approve":
        q.status = "approved"
        q.validated_by = user.id
        audit_action = "approved"
        flash("השאלה אושרה", "success")
    else:
        audit_action = "edited"
        flash("נשמר", "success")

    db.session.add(
        QuestionEdit(
            question_id=q.id, editor_id=user.id, action=audit_action,
            previous_content=previous, new_content=q.as_dict(), note=note or None,
        )
    )
    db.session.commit()
    return redirect(url_for("admin.questions", **redirect_params))


@bp.route("/topics", methods=["GET", "POST"])
@staff_required
def topics():
    if request.method == "POST":
        siman_rows = list(zip(
            request.form.getlist("siman_parcours"),
            request.form.getlist("siman_num"),
            request.form.getlist("siman_topic"),
        ))
        seif_rows = list(zip(
            request.form.getlist("seif_parcours"),
            request.form.getlist("seif_siman"),
            request.form.getlist("seif_num"),
            request.form.getlist("seif_topic"),
        ))
        save_topics(siman_rows, seif_rows)
        flash("הנושאים נשמרו", "success")
        return redirect(url_for("admin.topics"))

    rows = (
        Question.query.with_entities(Question.parcours, Question.siman, Question.seif)
        .filter(Question.parcours.isnot(None), Question.siman.isnot(None))
        .distinct()
        .all()
    )
    by_parcours: dict[str, dict[int, set]] = {}
    for parcours, siman, seif in rows:
        by_parcours.setdefault(parcours, {}).setdefault(siman, set())
        if seif is not None:
            by_parcours[parcours][siman].add(seif)

    groups = []
    for parcours in sorted(by_parcours.keys()):
        simanim = []
        for siman in sorted(by_parcours[parcours].keys()):
            seifim = [
                {"seif": seif, "topic": get_seif_topic(parcours, siman, seif) or ""}
                for seif in sorted(by_parcours[parcours][siman])
            ]
            simanim.append({
                "siman": siman,
                "topic": get_siman_topic(parcours, siman) or "",
                "seifim": seifim,
            })
        groups.append({
            "parcours": parcours,
            "label": PARCOURS_LABELS.get(parcours, parcours),
            "simanim": simanim,
        })

    return render_template("admin/topics.html", groups=groups)


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
