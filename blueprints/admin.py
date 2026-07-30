"""Admin / staff routes: login, dashboard, import, validation."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, Response, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from sqlalchemy import func, inspect, text
from sqlalchemy.orm import joinedload

import calibration
from auth_helpers import current_user, login_user, logout_user, staff_required
from blueprints.auth import create_account
from chapter_topics import save_topics
from chapter_topics import siman_topic as get_siman_topic
from models import (
    APP_ROLES,
    FsrsCard,
    HiddenTag,
    Progression,
    Question,
    QuestionEdit,
    QuestionReport,
    QuestionSuggestion,
    BackupRecord,
    BackupApiToken,
    EmergencyApiToken,
    EmergencyApiAudit,
    StudentParcours,
    StudentProfile,
    Subject,
    TagRule,
    User,
    UserAnswer,
    UserRole,
    VisibleTag,
    db,
)
from question_types import (
    PARCOURS_LABELS,
    QUESTION_TYPES,
    VALID_PARCOURS,
    normalize_imported_question,
    sync_question_row_from_payload,
)
from subjects import get_or_create_subject
from subjects import rename_subject as rename_subject_by_id
from tags import (
    get_or_create_visible_tag,
    sync_question_hidden_tags,
)
from backup_service import backup_directory, create_backup, delete_backup

bp = Blueprint("admin", __name__, url_prefix="/admin")

TYPE_LABEL = {
    "multiple_choice": "Multiple choice",
    "multiple_opinions_dropdown": "Opinion matching",
    "true_false": "True / false",
}


@bp.context_processor
def inject_reports_count():
    """Badge du nombre de signalements personnels "open" — affiché dans le nav admin."""
    user = current_user()
    if user is None or not user.is_staff():
        return {}
    return {
        "open_reports_count": QuestionReport.query.filter_by(status="open").count(),
        "open_suggestions_count": QuestionSuggestion.query.filter_by(status="open").count(),
        "pending_questions_count": Question.query.filter_by(status="pending").count(),
        "flagged_questions_count": Question.query.filter_by(status="a_revoir").count(),
        "suggested_tag_rules_count": TagRule.query.filter_by(status="suggested").count(),
    }


def _resolve_open_reports(question_id: str, resolver_id: str, resolution: str) -> None:
    """Classe tous les signalements "open" d'une question.

    resolution="confirmed" — la question est retirée pour tout le monde (le
    signalement était justifié). resolution="dismissed" — l'admin a modifié
    ou ré-approuvé la question, elle redevient visible pour chaque étudiant
    qui l'avait signalée.
    """
    now = datetime.utcnow()
    for r in QuestionReport.query.filter_by(question_id=question_id, status="open").all():
        r.status = resolution
        r.resolved_by = resolver_id
        r.resolved_at = now


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Staff login/signup page. Requires staff role to access the rest of /admin."""
    if request.method == "POST":
        mode = request.form.get("mode", "login")
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        try:
            if mode == "signup":
                if User.query.filter_by(email=email).first():
                    raise ValueError("This email address is already registered.")
                if len(password) < 6:
                    raise ValueError("The password must contain at least 6 characters.")
                user = create_account(email, password, None)
            else:
                user = User.query.filter_by(email=email).first()
                if not user or not user.check_password(password):
                    raise ValueError("Incorrect email or password.")
            login_user(user)
            return redirect(url_for("admin.dashboard"))
        except ValueError as e:
            flash(str(e), "error")
    return render_template("admin/login.html")


@bp.route("/denied")
def denied():
    """Display a "forbidden" page when a non-staff user tries to access /admin."""
    return render_template("admin/denied.html")


@bp.route("/")
@bp.route("/dashboard")
@staff_required
def dashboard():
    """Focused admin overview: editorial work, learner activity and health."""
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    counts = {
        status: Question.query.filter_by(status=status).count()
        for status in ("pending", "approved", "a_revoir", "rejected")
    }
    answers_30d = UserAnswer.query.filter(UserAnswer.answered_at >= month_ago)
    answer_count_30d = answers_30d.count()
    correct_30d = answers_30d.filter_by(is_correct=True).count()
    metrics = {
        "active_students_7d": db.session.query(func.count(func.distinct(UserAnswer.user_id))).filter(UserAnswer.answered_at >= week_ago).scalar() or 0,
        "answers_30d": answer_count_30d,
        "accuracy_30d": round(correct_30d * 100 / answer_count_30d) if answer_count_30d else None,
        "total_questions": Question.query.count(),
    }
    work = {
        "pending": counts["pending"],
        "flagged": counts["a_revoir"],
        "reports": QuestionReport.query.filter_by(status="open").count(),
        "suggestions": QuestionSuggestion.query.filter_by(status="open").count(),
    }
    recent_edits = (
        db.session.query(QuestionEdit, Question, User)
        .join(Question, Question.id == QuestionEdit.question_id)
        .outerjoin(User, User.id == QuestionEdit.editor_id)
        .order_by(QuestionEdit.edited_at.desc()).limit(6).all()
    )
    last_backup = BackupRecord.query.order_by(BackupRecord.created_at.desc()).first()
    return render_template("admin/dashboard.html", counts=counts, metrics=metrics, work=work,
                           recent_edits=recent_edits, last_backup=last_backup)


@bp.route("/analytics")
@staff_required
def analytics():
    """Global reporting with optional path → siman → subject aggregation."""
    # Individual question statistics belong in the question editor, not here.
    if request.args.get("scope") == "question" and request.args.get("id"):
        return redirect(url_for("admin.questions", id=request.args["id"]))

    parcours = request.args.get("parcours", "")
    siman_raw = request.args.get("siman", "")
    subject_id = request.args.get("subject", "")
    try:
        siman = int(siman_raw) if siman_raw else None
    except ValueError:
        siman = None

    scoped_questions = Question.query
    if parcours:
        scoped_questions = scoped_questions.filter(Question.parcours == parcours)
    if siman is not None:
        scoped_questions = scoped_questions.filter(Question.siman == siman)
    if subject_id:
        scoped_questions = scoped_questions.filter(Question.subject_id == subject_id)
    question_rows = scoped_questions.all()
    question_ids = [question.id for question in question_rows]

    now = datetime.utcnow()
    seven_days = now - timedelta(days=7)
    thirty_days = now - timedelta(days=30)
    answers = UserAnswer.query.filter(UserAnswer.question_id.in_(question_ids)) if question_ids else UserAnswer.query.filter(False)
    answers_7d = answers.filter(UserAnswer.answered_at >= seven_days)
    answers_30d = answers.filter(UserAnswer.answered_at >= thirty_days)
    answers_30d_count = answers_30d.count()
    correct_30d = answers_30d.filter_by(is_correct=True).count()

    aggregate = {
        "questions": len(question_ids),
        "published": sum(question.status == "approved" for question in question_rows),
        "pending": sum(question.status == "pending" for question in question_rows),
        "flagged": sum(question.status == "a_revoir" for question in question_rows),
        "active_7d": db.session.query(func.count(func.distinct(UserAnswer.user_id))).filter(
            UserAnswer.question_id.in_(question_ids) if question_ids else False,
            UserAnswer.answered_at >= seven_days,
        ).scalar() or 0,
        "active_30d": db.session.query(func.count(func.distinct(UserAnswer.user_id))).filter(
            UserAnswer.question_id.in_(question_ids) if question_ids else False,
            UserAnswer.answered_at >= thirty_days,
        ).scalar() or 0,
        "answers_7d": answers_7d.count(),
        "answers_30d": answers_30d_count,
        "accuracy_30d": round(correct_30d * 100 / answers_30d_count) if answers_30d_count else None,
        "avg_time_30d": int(answers_30d.with_entities(func.avg(UserAnswer.response_time_ms)).scalar() or 0),
        "reports": QuestionReport.query.filter(
            QuestionReport.question_id.in_(question_ids) if question_ids else False,
            QuestionReport.status == "open",
        ).count(),
        "suggestions": QuestionSuggestion.query.filter(
            QuestionSuggestion.question_id.in_(question_ids) if question_ids else False,
            QuestionSuggestion.status == "open",
        ).count(),
    }

    activity_by_day: dict[str, dict] = {}
    for offset in range(29, -1, -1):
        day = (now - timedelta(days=offset)).date()
        activity_by_day[day.isoformat()] = {"label": day.strftime("%d %b"), "answers": 0, "users": set()}
    for answer in answers_30d.with_entities(UserAnswer.user_id, UserAnswer.answered_at).all():
        day_key = answer.answered_at.date().isoformat()
        if day_key in activity_by_day:
            activity_by_day[day_key]["answers"] += 1
            activity_by_day[day_key]["users"].add(answer.user_id)
    activity = [{"label": item["label"], "answers": item["answers"], "users": len(item["users"])} for item in activity_by_day.values()]
    chart_max = max([point["answers"] for point in activity] or [1])

    all_subjects = Subject.query.order_by(Subject.parcours, Subject.siman, Subject.created_at).all()
    scope_catalog = {
        "simanim": [
            {"parcours": path, "siman": number}
            for path, number in db.session.query(Question.parcours, Question.siman)
            .filter(Question.parcours.isnot(None), Question.siman.isnot(None)).distinct().all()
        ],
        "subjects": [
            {"id": item.id, "parcours": item.parcours, "siman": item.siman, "title": item.title}
            for item in all_subjects
        ],
    }
    siman_options = sorted({item["siman"] for item in scope_catalog["simanim"] if not parcours or item["parcours"] == parcours})
    subject_options = [
        item for item in all_subjects
        if (not parcours or item.parcours == parcours) and (siman is None or item.siman == siman)
    ]

    scope_parts = []
    if parcours:
        scope_parts.append(PARCOURS_LABELS.get(parcours, parcours))
    if siman is not None:
        scope_parts.append(f"Siman {siman}")
    if subject_id:
        subject = next((item for item in subject_options if item.id == subject_id), Subject.query.get(subject_id))
        if subject:
            scope_parts.append(subject.title)
    scope_label = " · ".join(scope_parts) if scope_parts else "All learning paths"

    platform = {
        "registered": User.query.count(),
        "new_7d": User.query.filter(User.created_at >= seven_days).count(),
        "new_30d": User.query.filter(User.created_at >= thirty_days).count(),
        "onboarded": StudentProfile.query.filter_by(onboarded=True).count(),
        "last_backup": BackupRecord.query.order_by(BackupRecord.created_at.desc()).first(),
    }
    return render_template(
        "admin/analytics.html", aggregate=aggregate, platform=platform, activity=activity,
        chart_max=chart_max, parcours_labels=PARCOURS_LABELS, siman_options=siman_options,
        subject_options=subject_options, selected_parcours=parcours, selected_siman=siman,
        selected_subject=subject_id, scope_label=scope_label,
        scope_catalog=scope_catalog,
    )


@bp.route("/suggestions")
@staff_required
def suggestions():
    entries = (db.session.query(QuestionSuggestion, Question, User)
        .join(Question, Question.id == QuestionSuggestion.question_id)
        .join(User, User.id == QuestionSuggestion.author_id)
        .filter(QuestionSuggestion.status == "open").order_by(QuestionSuggestion.created_at.desc()).all())
    return render_template("admin/suggestions.html", suggestions=entries)


@bp.route("/suggestions/<suggestion_id>/<action>", methods=["POST"])
@staff_required
def resolve_suggestion(suggestion_id, action):
    actor = current_user()
    if not actor.has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    suggestion = QuestionSuggestion.query.get_or_404(suggestion_id)
    if action not in {"applied", "dismissed"}:
        return redirect(url_for("admin.suggestions"))
    suggestion.status, suggestion.resolved_by, suggestion.resolved_at = action, actor.id, datetime.utcnow()
    db.session.commit()
    flash("Suggestion updated.", "success")
    return redirect(url_for("admin.questions", id=suggestion.question_id)) if action == "applied" else redirect(url_for("admin.suggestions"))


@bp.route("/data")
@staff_required
def data_explorer():
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    inspector = inspect(db.engine)
    tables = sorted(inspector.get_table_names())
    selected = request.args.get("table", tables[0] if tables else "")
    if selected not in tables:
        selected = tables[0] if tables else ""
    columns, rows = [], []
    if selected:
        columns = [col["name"] for col in inspector.get_columns(selected)]
        page = max(int(request.args.get("page", 1)), 1)
        search = (request.args.get("q") or "").strip()
        statement = text(f'SELECT * FROM "{selected}"')
        raw_rows = db.session.execute(statement).mappings().all()
        if search:
            raw_rows = [r for r in raw_rows if search.lower() in " ".join(str(v) for v in r.values()).lower()]
        start = (page - 1) * 50
        rows = raw_rows[start:start + 50]
    return render_template("admin/data.html", tables=tables, selected=selected, columns=columns, rows=rows)


@bp.route("/backups", methods=["GET", "POST"])
@staff_required
def backups():
    actor = current_user()
    if not actor.has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    if request.method == "POST":
        try:
            create_backup(actor.id)
            flash("Backup created successfully.", "success")
        except Exception as exc:
            current_app.logger.exception("Backup failed")
            flash(f"Backup failed: {exc}", "error")
        return redirect(url_for("admin.backups"))
    return _render_backups()


def _render_backups(plaintext_backup_api_key=None):
    return render_template(
        "admin/backups.html",
        backups=BackupRecord.query.order_by(BackupRecord.created_at.desc()).all(),
        backup_api_tokens=BackupApiToken.query.order_by(BackupApiToken.created_at.desc()).all(),
        plaintext_backup_api_key=plaintext_backup_api_key,
    )


@bp.route("/backup-api-keys", methods=["POST"])
@staff_required
def create_backup_api_key():
    actor = current_user()
    if not actor.has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    label = (request.form.get("label") or "Remote scheduler").strip()[:100]
    plaintext_key = secrets.token_urlsafe(32)
    db.session.add(BackupApiToken(
        label=label or "Remote scheduler",
        token_hash=hashlib.sha256(plaintext_key.encode()).hexdigest(),
        created_by=actor.id,
    ))
    db.session.commit()
    return _render_backups(plaintext_backup_api_key=plaintext_key)


@bp.route("/backup-api-keys/<token_id>/revoke", methods=["POST"])
@staff_required
def revoke_backup_api_key(token_id):
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    token = BackupApiToken.query.get_or_404(token_id)
    if not token.revoked_at:
        token.revoked_at = datetime.utcnow()
        db.session.commit()
    return redirect(url_for("admin.backups"))


@bp.route("/backups/<backup_id>/keep", methods=["POST"])
@staff_required
def toggle_backup_keep(backup_id):
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    backup = BackupRecord.query.get_or_404(backup_id)
    backup.keep_forever = not backup.keep_forever
    db.session.commit()
    return redirect(url_for("admin.backups"))


@bp.route("/backups/<backup_id>/delete", methods=["POST"])
@staff_required
def remove_backup(backup_id):
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    delete_backup(BackupRecord.query.get_or_404(backup_id))
    return redirect(url_for("admin.backups"))


@bp.route("/backups/<backup_id>/download")
@staff_required
def download_backup(backup_id):
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    backup = BackupRecord.query.get_or_404(backup_id)
    return send_from_directory(backup_directory(), backup.filename, as_attachment=True)


@bp.route("/api-security", methods=["GET", "POST"])
@staff_required
def api_security():
    actor = current_user()
    if not actor.has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    plaintext_token = None
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            if request.form.get("confirm") != "EMERGENCY":
                flash("Type EMERGENCY to create a SQL token.", "error")
                return redirect(url_for("admin.api_security"))
            ttl = min(max(int(request.form.get("ttl_minutes", 15)), 5), current_app.config["EMERGENCY_SQL_API_MAX_TTL_MINUTES"])
            plaintext_token = secrets.token_urlsafe(48)
            db.session.add(EmergencyApiToken(label=(request.form.get("label") or "Accès d'urgence")[:100], token_hash=hashlib.sha256(plaintext_token.encode()).hexdigest(), expires_at=datetime.utcnow() + timedelta(minutes=ttl), created_by=actor.id))
            db.session.commit()
        elif action == "revoke":
            token = EmergencyApiToken.query.get_or_404(request.form.get("token_id"))
            token.revoked_at = datetime.utcnow(); db.session.commit()
    tokens = EmergencyApiToken.query.order_by(EmergencyApiToken.created_at.desc()).all()
    audits = EmergencyApiAudit.query.order_by(EmergencyApiAudit.created_at.desc()).limit(30).all()
    return render_template("admin/api_security.html", tokens=tokens, audits=audits, plaintext_token=plaintext_token, enabled=current_app.config["EMERGENCY_SQL_API_ENABLED"], max_ttl=current_app.config["EMERGENCY_SQL_API_MAX_TTL_MINUTES"])


@bp.route("/subjects/rename", methods=["POST"])
@staff_required
def rename_subject():
    """Renomme le titre affiché d'un sujet, par ID.

    Si le nouveau titre entre en collision avec un autre sujet du même siman,
    les deux sont fusionnés (questions + progression réassignées, l'ancien
    sujet supprimé) — même résultat qu'avant, quand deux textes différents
    étaient renommés vers la même valeur.
    """
    user = current_user()
    subject_id = request.form.get("subject_id") or ""
    new_title = (request.form.get("new_title") or "").strip()

    subj = Subject.query.get(subject_id)
    if subj is None:
        flash("Subject not found.", "error")
        return redirect(url_for("admin.dashboard"))
    if not new_title:
        flash("Enter a new subject name.", "error")
        return redirect(url_for("admin.dashboard"))
    if new_title == subj.title:
        flash("The new name is identical to the current name.", "error")
        return redirect(url_for("admin.dashboard"))

    result = rename_subject_by_id(subject_id, new_title)
    old_title = result["old_title"]
    target = result["subject"]
    note = (
        f'Subject merge: "{old_title}" merged into "{new_title}"'
        if result["merged_into"] else f'Subject renamed: "{old_title}" to "{new_title}"'
    )
    for q in result["questions"]:
        previous = result["previous"][q.id]
        new_content = dict(previous, subject_id=target.id, subject=target.title)
        db.session.add(
            QuestionEdit(
                question_id=q.id, editor_id=user.id, action="edited",
                previous_content=previous, new_content=new_content, note=note,
            )
        )

    db.session.commit()
    if result["merged_into"]:
        flash(f'{len(result["questions"])} questions merged into "{new_title}".', "success")
    else:
        flash(f'{len(result["questions"])} questions updated.', "success")
    return redirect(url_for("admin.dashboard"))


@bp.route("/users")
@staff_required
def users():
    """List all student profiles with their card counts."""
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
    # Date de מבחן la plus proche parmi les parcours activés de chaque étudiant.
    exam_dates = dict(
        db.session.query(StudentParcours.user_id, func.min(StudentParcours.exam_date))
        .filter(StudentParcours.exam_date.isnot(None))
        .group_by(StudentParcours.user_id)
        .all()
    )
    roles_by_user: dict[str, list[str]] = {}
    for user_id, role in db.session.query(UserRole.user_id, UserRole.role).all():
        roles_by_user.setdefault(user_id, []).append(role)

    return render_template(
        "admin/users.html",
        profiles=profiles,
        card_counts=card_counts,
        exam_dates=exam_dates,
        roles_by_user=roles_by_user,
        app_roles=APP_ROLES,
        is_super_admin=current_user().has_role("super_admin"),
        protected_admin_email=current_app.config["PROTECTED_SUPER_ADMIN_EMAIL"],
    )


@bp.route("/users/<user_id>/roles", methods=["POST"])
@staff_required
def update_user_role(user_id):
    """Grant or revoke an app role for a user — reserved to super_admin.

    The protected owner's super_admin role can never be removed, including by
    another super-admin.
    """
    actor = current_user()
    if not actor.has_role("super_admin"):
        return redirect(url_for("admin.denied"))

    target = User.query.get_or_404(user_id)
    role = request.form.get("role", "")
    action = request.form.get("action", "")

    if role not in APP_ROLES:
        flash("Invalid role.", "error")
        return redirect(url_for("admin.users"))

    if action == "add":
        if not UserRole.query.filter_by(user_id=target.id, role=role).first():
            db.session.add(UserRole(user_id=target.id, role=role))
            db.session.commit()
        flash(f'Role "{role}" added to {target.email}.', "success")
    elif action == "remove":
        from protected_admin import is_protected_admin
        if role == "super_admin" and is_protected_admin(target):
            flash("The protected owner must remain a super-admin.", "error")
            return redirect(url_for("admin.users"))
        if target.id == actor.id and role == "super_admin":
            flash("You cannot remove your own super-admin role.", "error")
            return redirect(url_for("admin.users"))
        UserRole.query.filter_by(user_id=target.id, role=role).delete()
        db.session.commit()
        flash(f'Role "{role}" removed from {target.email}.', "success")
    else:
        flash("Invalid action.", "error")

    return redirect(url_for("admin.users"))


@bp.route("/users/<user_id>")
@staff_required
def user_detail(user_id):
    """Display detailed progress for a specific student (cards, answers, stability)."""
    from datetime import date
    from sqlalchemy import func
    user = User.query.get_or_404(user_id)
    profile = StudentProfile.query.get(user_id)
    cards = (
        FsrsCard.query
        .filter_by(user_id=user_id)
        .join(Question, Question.id == FsrsCard.question_id)
        .add_entity(Question)
        .options(joinedload(Question.subject))
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
    nearest_exam_date = (
        db.session.query(func.min(StudentParcours.exam_date))
        .filter(StudentParcours.user_id == user_id, StudentParcours.exam_date.isnot(None))
        .scalar()
    )
    return render_template(
        "admin/user_detail.html",
        user=user,
        profile=profile,
        nearest_exam_date=nearest_exam_date,
        cards=cards,
        total_answers=total_answers,
        correct_answers=correct_answers,
        due_today=due_today,
        avg_stability=avg_stability,
        today=today,
    )


def _extract_questions(parsed):
    """Extract a list of questions from parsed JSON.

    Handles three formats:
    1. A raw list of question dicts → return as-is
    2. A dict with a "questions" key → return that list
    3. A single question dict → wrap in a list
    """
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict) and isinstance(parsed.get("questions"), list):
        return parsed["questions"]
    return [parsed]


@bp.route("/import", methods=["GET", "POST"])
@staff_required
def import_questions():
    """Import questions from a JSON file: preview, validate, then save as approved."""
    if request.method == "POST":
        action = request.form.get("action")
        if action == "preview":
            file = request.files.get("file")
            if not file:
                flash("Choose a JSON file.", "error")
                return render_template("admin/import.html", rows=None)
            try:
                parsed = json.loads(file.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as e:
                flash("Invalid JSON file: " + str(e), "error")
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
                    subj = get_or_create_subject(ins.get("parcours"), ins.get("siman"), ins.get("subject"))
                    question = Question(
                        question_type=ins["question_type"],
                        text=ins["text"],
                        payload=ins["payload"],
                        choices=ins["choices"],
                        correct_answer=ins["correct_answer"],
                        explanation=ins["explanation"],
                        difficulty=ins["difficulty"],
                        section=ins["section"],
                        source_ref=ins["source_ref"],
                        subject_id=subj.id,
                        siman=ins.get("siman"),
                        seif=ins.get("seif"),
                        parcours=ins.get("parcours"),
                        status="pending",
                        created_by=user.id,
                    )
                    sync_question_hidden_tags(question, ins.get("parcours"), ins["tags"])
                    db.session.add(question)
                    db.session.flush()
                    inserted += 1
                except Exception:  # noqa: BLE001
                    db.session.rollback()
                    failed += 1
            db.session.commit()
            flash(f"Imported {inserted} questions" + (f" ({failed} failed)" if failed else ""), "success")
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
    if not (user.has_role("validator") or user.has_role("super_admin")):
        return redirect(url_for("admin.denied"))
    pending = Question.query.filter_by(status="pending").all()
    for q in pending:
        previous = q.as_dict()
        q.status = "approved"
        q.validated_by = user.id
        db.session.add(
            QuestionEdit(
                question_id=q.id, editor_id=user.id, action="approved",
                previous_content=previous, new_content=q.as_dict(),
                note="Bulk approval of all pending questions",
            )
        )
        _resolve_open_reports(q.id, user.id, "dismissed")
    db.session.commit()
    flash(f"Approved {len(pending)} questions.", "success")
    return redirect(url_for("admin.questions", status="pending"))


@bp.route("/reports")
@staff_required
def reports():
    """File d'attente des signalements personnels (étudiants simples) encore
    "open" — la question reste visible pour tout le monde SAUF le(s)
    signaleur(s), tant qu'un validateur ne confirme pas (retrait global) ou
    ne rejette pas (le signalement était injustifié) chaque signalement."""
    open_reports = (
        db.session.query(QuestionReport, Question, User)
        .join(Question, Question.id == QuestionReport.question_id)
        .join(User, User.id == QuestionReport.reporter_id)
        .options(joinedload(Question.subject))
        .filter(QuestionReport.status == "open")
        .order_by(QuestionReport.created_at.desc())
        .all()
    )
    return render_template("admin/reports.html", reports=open_reports, type_label=TYPE_LABEL)


@bp.route("/reports/<report_id>/confirm", methods=["POST"])
@staff_required
def confirm_report(report_id):
    """Le signalement est justifié : retrait de la question pour TOUT LE
    MONDE (status -> "a_revoir"), elle rejoint la file "à revoir" de
    /admin/questions pour correction/rejet."""
    user = current_user()
    if not (user.has_role("validator") or user.has_role("super_admin")):
        return redirect(url_for("admin.denied"))
    rep = QuestionReport.query.get_or_404(report_id)
    q = Question.query.get_or_404(rep.question_id)

    if q.status == "approved":
        previous = q.as_dict()
        q.status = "a_revoir"
        db.session.add(
            QuestionEdit(
                question_id=q.id, editor_id=user.id, action="reported",
                note=rep.reason, previous_content=previous,
            )
        )
    _resolve_open_reports(q.id, user.id, "confirmed")
    db.session.commit()
    flash("Report confirmed. The question is unpublished and flagged for review.", "success")
    return redirect(url_for("admin.reports"))


@bp.route("/reports/<report_id>/dismiss", methods=["POST"])
@staff_required
def dismiss_report(report_id):
    """Le signalement n'est pas justifié : la question redevient visible pour
    le seul étudiant qui l'avait signalée."""
    user = current_user()
    if not (user.has_role("validator") or user.has_role("super_admin")):
        return redirect(url_for("admin.denied"))
    rep = QuestionReport.query.get_or_404(report_id)
    rep.status = "dismissed"
    rep.resolved_by = user.id
    rep.resolved_at = datetime.utcnow()
    db.session.commit()
    flash("Report dismissed. The question is visible to the student again.", "success")
    return redirect(url_for("admin.reports"))


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
    grouping = request.args.get("group", "subject")
    if grouping not in {"subject", "id", "title"}:
        grouping = "subject"
    selected_id = request.args.get("id", "")

    query = Question.query.options(joinedload(Question.subject))
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
            flash("Siman must be a number.", "error")
            siman_filter = ""
    if seif_filter:
        try:
            query = query.filter_by(seif=int(seif_filter))
        except ValueError:
            flash("Seif must be a number.", "error")
            seif_filter = ""
    if search:
        query = query.outerjoin(Subject, Subject.id == Question.subject_id).filter(
            or_(
                Subject.title.ilike(f"%{search}%"),
                Question.text.ilike(f"%{search}%"),
            )
        )
    all_questions = query.order_by(Question.created_at.desc()).all()

    if tag_filter:
        needle = tag_filter.lower()
        all_questions = [q for q in all_questions if any(needle in (t or "").lower() for t in q.tag_names)]

    selected = None
    if all_questions:
        selected = next((q for q in all_questions if q.id == selected_id), all_questions[0])

    grouped: dict[str, list[Question]] = {}
    group_order: list[str] = []
    for question in all_questions:
        if grouping == "subject":
            subject_title = question.subject.title if question.subject else "Unassigned subject"
            key = f"{question.parcours or '—'} · Siman {question.siman or '—'} · {subject_title}"
        elif grouping == "id":
            key = f"ID · {question.id[:1].upper()}"
        else:
            title = (question.text or "Untitled question").strip()
            key = f"Title · {title[:1].upper() if title else '—'}"
        if key not in grouped:
            grouped[key] = []
            group_order.append(key)
        grouped[key].append(question)
    if grouping in {"id", "title"}:
        group_order.sort()
        for key in group_order:
            grouped[key].sort(key=lambda question: (question.id if grouping == "id" else (question.text or "").casefold()))
    question_groups = [{"label": key, "questions": grouped[key]} for key in group_order]

    selected_stats = None
    if selected:
        stats_query = UserAnswer.query.filter_by(question_id=selected.id)
        total = stats_query.count()
        correct = stats_query.filter_by(is_correct=True).count()
        selected_stats = {
            "answers": total,
            "accuracy": round(correct * 100 / total) if total else None,
            "avg_time": int(stats_query.with_entities(func.avg(UserAnswer.response_time_ms)).scalar() or 0),
            "reports": QuestionReport.query.filter_by(question_id=selected.id, status="open").count(),
        }

    filters = {
        "status": status, "type": qtype, "parcours": parcours_filter,
        "q": search, "siman": siman_filter, "seif": seif_filter, "tag": tag_filter,
        "group": grouping,
    }
    hidden_tag_options = []
    if selected and selected.parcours:
        hidden_tag_options = [
            t.name for t in HiddenTag.query.filter_by(parcours=selected.parcours).order_by(HiddenTag.name).all()
        ]
    return render_template(
        "admin/questions.html",
        questions=all_questions,
        question_groups=question_groups,
        selected=selected,
        filters=filters,
        question_types=QUESTION_TYPES,
        type_label=TYPE_LABEL,
        parcours_labels=PARCOURS_LABELS,
        hidden_tag_options=hidden_tag_options,
        selected_stats=selected_stats,
        work_counts={
            "pending": Question.query.filter_by(status="pending").count(),
            "flagged": Question.query.filter_by(status="a_revoir").count(),
            "reports": QuestionReport.query.filter_by(status="open").count(),
            "suggestions": QuestionSuggestion.query.filter_by(status="open").count(),
        },
        can_edit=current_user().has_role("super_admin"),
        can_review=current_user().has_role("validator") or current_user().has_role("super_admin"),
    )


@bp.route("/questions/<qid>/edit", methods=["POST"])
@staff_required
def edit_question(qid):
    user = current_user()
    q = Question.query.get_or_404(qid)
    action = request.form.get("action", "save")
    note = (request.form.get("note") or "").strip()
    previous = q.as_dict()

    if not (user.has_role("validator") or user.has_role("super_admin")):
        return redirect(url_for("admin.denied"))

    if not user.has_role("super_admin") and action == "save":
        flash("Validators can suggest changes from the student reader; only a super-admin can edit question content.", "error")
        return redirect(url_for("admin.questions", id=qid))

    if not user.has_role("super_admin") and action == "approve":
        q.status = "approved"
        q.validated_by = user.id
        db.session.add(QuestionEdit(question_id=q.id, editor_id=user.id, action="approved",
                                    previous_content=previous, new_content=q.as_dict()))
        _resolve_open_reports(q.id, user.id, "dismissed")
        db.session.commit()
        flash("Question approved.", "success")
        return redirect(url_for("admin.questions", id=qid))

    redirect_params = {
        "status": request.form.get("filter_status", ""),
        "type": request.form.get("filter_type", ""),
        "parcours": request.form.get("filter_parcours", ""),
        "q": request.form.get("filter_q", ""),
        "siman": request.form.get("filter_siman", ""),
        "seif": request.form.get("filter_seif", ""),
        "tag": request.form.get("filter_tag", ""),
        "group": request.form.get("filter_group", "subject"),
        "id": qid,
    }

    if action == "reject":
        if not note:
            flash("A review note is required to reject a question.", "error")
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
        _resolve_open_reports(q.id, user.id, "confirmed")
        db.session.commit()
        flash("Question rejected.", "success")
        return redirect(url_for("admin.questions", **redirect_params))

    if action == "flag":
        if not note:
            flash("A review note is required to flag a question.", "error")
            return redirect(url_for("admin.questions", **redirect_params))
        q.status = "a_revoir"
        q.validated_by = user.id
        q.validator_note = note
        db.session.add(
            QuestionEdit(
                question_id=q.id, editor_id=user.id, action="flagged",
                note=note, previous_content=previous, new_content=q.as_dict(),
            )
        )
        db.session.commit()
        flash("Question flagged for review.", "success")
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
    # Assigner l'objet (pas juste subject_id) : q.subject a déjà été chargé par
    # le q.as_dict() de `previous` ci-dessus, une simple mise à jour de
    # subject_id laisserait cette relation en cache avec l'ancien sujet pour
    # le q.as_dict() de new_content plus bas.
    q.subject = get_or_create_subject(row.get("parcours"), row.get("siman"), row.get("subject"))
    q.siman = row.get("siman")
    q.seif = row.get("seif")
    q.parcours = row.get("parcours")
    q.difficulty = int(row.get("difficulty") or 2)
    q.section = row.get("section") or ["shulchan_aruch"]
    sync_question_hidden_tags(q, row.get("parcours"), row.get("tags") or [])
    q.source_ref = draft["source_ref"]
    q.validator_note = note or None

    if action == "approve":
        q.status = "approved"
        q.validated_by = user.id
        audit_action = "approved"
        flash("Question published.", "success")
    else:
        audit_action = "edited"
        flash("Question saved.", "success")

    db.session.add(
        QuestionEdit(
            question_id=q.id, editor_id=user.id, action=audit_action,
            previous_content=previous, new_content=q.as_dict(), note=note or None,
        )
    )
    _resolve_open_reports(q.id, user.id, "dismissed")
    db.session.commit()
    return redirect(url_for("admin.questions", **redirect_params))


@bp.route("/subjects", methods=["GET", "POST"])
@bp.route("/topics", methods=["GET", "POST"])
@staff_required
def topics():
    actor = current_user()
    if not actor.has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    if request.method == "POST":
        siman_rows = list(zip(
            request.form.getlist("siman_parcours"),
            request.form.getlist("siman_num"),
            request.form.getlist("siman_topic"),
        ))
        save_topics(siman_rows)
        for subject_id, new_title in zip(
            request.form.getlist("subject_id"), request.form.getlist("subject_title")
        ):
            subject = Subject.query.get(subject_id)
            title = (new_title or "").strip()
            if subject is None or not title or title == subject.title:
                continue
            result = rename_subject_by_id(subject_id, title)
            if result is None:
                continue
            note = (
                f'Subject merged into "{title}"' if result["merged_into"]
                else f'Subject renamed from "{result["old_title"]}" to "{title}"'
            )
            target = result["subject"]
            for question in result["questions"]:
                previous = result["previous"][question.id]
                db.session.add(QuestionEdit(
                    question_id=question.id, editor_id=actor.id, action="edited",
                    previous_content=previous,
                    new_content=dict(previous, subject_id=target.id, subject=target.title),
                    note=note,
                ))
        db.session.commit()
        flash("Siman and subject titles saved.", "success")
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

    subjects_by_siman: dict[tuple[str, int], list[Subject]] = {}
    for subject in Subject.query.order_by(Subject.parcours, Subject.siman, Subject.created_at).all():
        subjects_by_siman.setdefault((subject.parcours, subject.siman), []).append(subject)
    groups = []
    for parcours in sorted(by_parcours.keys()):
        simanim = []
        for siman in sorted(by_parcours[parcours].keys()):
            simanim.append({
                "siman": siman,
                "topic": get_siman_topic(parcours, siman) or "",
                "seifim": sorted(by_parcours[parcours][siman]),
                "subjects": subjects_by_siman.get((parcours, siman), []),
            })
        groups.append({
            "parcours": parcours,
            "label": PARCOURS_LABELS.get(parcours, parcours),
            "simanim": simanim,
        })

    return render_template("admin/topics.html", groups=groups)


def _tags_parcours_options() -> list[str]:
    """Parcours codes that actually have hidden tags, plus every VALID_PARCOURS
    (so a brand-new parcours with no tags yet still shows up in the selector)."""
    codes = {p for (p,) in db.session.query(HiddenTag.parcours).distinct().all()}
    codes.update(VALID_PARCOURS)
    return sorted(codes)


@bp.route("/tags")
@staff_required
def tags_page():
    options = _tags_parcours_options()
    parcours = request.args.get("parcours") or (options[0] if options else "")
    visible = VisibleTag.query.filter_by(parcours=parcours).order_by(VisibleTag.name).all()
    hidden = HiddenTag.query.filter_by(parcours=parcours).order_by(HiddenTag.name).all()
    active_rules = (
        TagRule.query.join(VisibleTag)
        .filter(VisibleTag.parcours == parcours, TagRule.status == "active")
        .order_by(VisibleTag.name).all()
    )
    suggested_rules = (
        TagRule.query.join(VisibleTag)
        .filter(VisibleTag.parcours == parcours, TagRule.status == "suggested")
        .order_by(TagRule.created_at.asc()).all()
    )
    return render_template(
        "admin/tags.html",
        parcours_options=options, selected_parcours=parcours, parcours_labels=PARCOURS_LABELS,
        visible_tags=visible, hidden_tags=hidden,
        active_rules=active_rules, suggested_rules=suggested_rules,
    )


@bp.route("/tags/visible", methods=["POST"])
@staff_required
def tags_visible():
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    parcours = request.form.get("parcours") or ""
    action = request.form.get("action")
    if action == "create":
        name = (request.form.get("name") or "").strip()
        if name:
            get_or_create_visible_tag(parcours, name)
            db.session.commit()
            flash(f'Visible tag "{name}" created.', "success")
    elif action == "rename":
        tag = VisibleTag.query.get(request.form.get("visible_tag_id"))
        new_name = (request.form.get("name") or "").strip()
        if tag is not None and new_name:
            tag.name = new_name
            db.session.commit()
            flash("Visible tag renamed.", "success")
    elif action == "delete":
        tag = VisibleTag.query.get(request.form.get("visible_tag_id"))
        if tag is not None:
            TagRule.query.filter_by(visible_tag_id=tag.id).delete(synchronize_session=False)
            db.session.delete(tag)
            db.session.commit()
            flash("Visible tag deleted.", "success")
    return redirect(url_for("admin.tags_page", parcours=parcours))


@bp.route("/tags/rules", methods=["POST"])
@staff_required
def tags_rules_create():
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    actor = current_user()
    parcours = request.form.get("parcours") or ""
    visible_tag_id = request.form.get("visible_tag_id")
    hidden_tag_ids = request.form.getlist("hidden_tag_ids")
    logic = "and" if request.form.get("logic") == "and" else "or"
    visible_tag = VisibleTag.query.get(visible_tag_id)
    hidden_tags = HiddenTag.query.filter(HiddenTag.id.in_(hidden_tag_ids)).all() if hidden_tag_ids else []
    if visible_tag is None or not hidden_tags:
        flash("Choose a visible tag and at least one hidden tag.", "error")
    else:
        rule = TagRule(visible_tag_id=visible_tag.id, logic=logic, status="active",
                        source="manual", created_by=actor.id)
        rule.hidden_tags = hidden_tags
        db.session.add(rule)
        db.session.commit()
        flash("Tag association created.", "success")
    return redirect(url_for("admin.tags_page", parcours=parcours))


@bp.route("/tags/rules/<rule_id>/<action>", methods=["POST"])
@staff_required
def tags_rules_action(rule_id, action):
    if not current_user().has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    rule = TagRule.query.get_or_404(rule_id)
    parcours = rule.visible_tag.parcours
    if action == "approve":
        rule.status = "active"
        db.session.commit()
        flash("Suggestion approved.", "success")
    elif action == "reject":
        rule.status = "rejected"
        db.session.commit()
        flash("Suggestion rejected.", "success")
    elif action == "delete":
        db.session.delete(rule)
        db.session.commit()
        flash("Tag association removed.", "success")
    return redirect(url_for("admin.tags_page", parcours=parcours))


@bp.route("/reset-db", methods=["POST"])
@staff_required
def reset_db():
    user = current_user()
    if not user.has_role("super_admin"):
        return redirect(url_for("admin.denied"))
    confirm = (request.form.get("confirm") or "").strip()
    if confirm != "RESET":
        flash("Type RESET to confirm the reset.", "error")
        return redirect(url_for("admin.dashboard"))
    from protected_admin import restore_protected_admin, snapshot_protected_admin
    owner_snapshot = snapshot_protected_admin()
    db.session.remove()
    db.drop_all()
    db.create_all()
    restore_protected_admin(owner_snapshot)
    logout_user()
    flash("Database reset. The protected owner account was preserved; sign in again.", "success")
    return redirect(url_for("admin.login"))
