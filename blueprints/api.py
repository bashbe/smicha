"""JSON API consumed by the chapter player (answer submission)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from auth_helpers import current_user
from fsrs import (
    FsrsCardState,
    rating_for,
    retrievability,
    roll_avg,
    schedule_next,
    soften_first_contact,
    RATING_LABEL,
)
import calibration
from models import (
    FsrsCard,
    ItemStats,
    Progression,
    Question,
    QuestionEdit,
    StudentProfile,
    UserAnswer,
    UserSpeed,
    db,
)
from points import compute_daily_points, compute_points, compute_stability_points
from question_types import is_correct_answer, normalize_db_question

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.post("/answer")
def answer():
    user = current_user()
    if user is None:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    question_id = data.get("question_id")
    given_answer = data.get("given_answer", "")
    response_time_ms = int(data.get("response_time_ms", 0))
    combo = int(data.get("combo", 0))
    mode = data.get("mode", "study")

    q = Question.query.get(question_id)
    if q is None:
        return jsonify({"error": "question not found"}), 404

    sp = StudentProfile.query.get(user.id)
    nq = normalize_db_question(q.as_dict())

    is_correct = is_correct_answer(nq, given_answer)

    # Collective calibration (Phase 2): normalise the latency by item + user,
    # derive the speed bucket / rating from z-scores (absolute-threshold
    # fallback when uncalibrated).
    card = FsrsCard.query.filter_by(user_id=user.id, question_id=q.id).first()
    is_first_contact = card is None or card.state == "new"

    item_stats = ItemStats.query.get(q.id)
    if item_stats is None:
        item_stats = ItemStats(
            question_id=q.id,
            question_type=q.question_type,
            hidden_difficulty=q.difficulty,
        )
        db.session.add(item_stats)
    user_speed = UserSpeed.query.get(user.id)
    if user_speed is None:
        user_speed = UserSpeed(user_id=user.id)
        db.session.add(user_speed)

    z_item, z_user = calibration.normalize_latency(response_time_ms, item_stats, user_speed)
    z_eff = z_item if z_item is not None else z_user
    bucket = calibration.bucket_from_z(z_item, z_user, q.difficulty, response_time_ms)
    rating = soften_first_contact(rating_for(is_correct, bucket), is_correct, is_first_contact)
    auto_grade = calibration.auto_grade_from_latency(is_correct, z_eff, bucket)
    new_combo = combo + 1 if is_correct else 0

    # Nombre de cartes dues AVANT ce traitement (utilisé pour le bonus de
    # complétion quotidienne — capturé avant l'upsert FSRS qui va déplacer
    # due_date de cette carte).
    due_before = 0
    if mode == "revision_daily":
        due_before = (
            FsrsCard.query.join(Question, Question.id == FsrsCard.question_id)
            .filter(
                FsrsCard.user_id == user.id,
                FsrsCard.due_date <= date.today(),
                Question.status == "approved",
            )
            .count()
        )

    if mode == "revision_daily":
        days_since = (date.today() - card.last_review.date()).days if (card and card.last_review) else 0
        breakdown = compute_daily_points(is_correct, days_since, new_combo)
    elif mode in ("revision_siman", "revision_sujet", "revision_random"):
        elapsed_for_r = (date.today() - card.last_review.date()).days if (card and card.last_review) else 0
        r = retrievability(elapsed_for_r, card.stability) if card else 0.0
        breakdown = compute_stability_points(is_correct, r, new_combo)
    else:
        breakdown = compute_points(is_correct, q.difficulty, bucket, new_combo)

    # 1. record the answer (enriched with the calibration signals)
    db.session.add(
        UserAnswer(
            user_id=user.id,
            question_id=q.id,
            given_answer=given_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            points_earned=breakdown["total"],
            combo_at_time=new_combo,
            z_item=z_item,
            z_user=z_user,
            auto_grade=auto_grade,
        )
    )

    # 2. FSRS card upsert
    if card:
        base = FsrsCardState(
            stability=card.stability,
            fsrs_difficulty=card.fsrs_difficulty,
            scheduled_days=card.scheduled_days,
            elapsed_days=card.elapsed_days,
            reps=card.reps,
            lapses=card.lapses,
            state=card.state,
            due_date=card.due_date.isoformat() if card.due_date else date.today().isoformat(),
            target_stability=card.target_stability,
            avg_response_time_ms=card.avg_response_time_ms,
            last_review=card.last_review,
        )
    else:
        card = FsrsCard(user_id=user.id, question_id=q.id)
        base = FsrsCardState(
            target_stability=sp.target_stability or 0.95,
            due_date=date.today().isoformat(),
        )
        db.session.add(card)

    exam = sp.exam_date.isoformat() if sp.exam_date else None
    # Collective per-item prior — blended (never substituted) into S0/D0 for a
    # brand-new card only (schedule_next ignores it once the card has history).
    prior = calibration.build_prior(q.difficulty, item_stats) if is_first_contact else None
    nx = schedule_next(base, rating, exam, prior=prior)
    avg = roll_avg(base.avg_response_time_ms, response_time_ms)

    card.stability = nx.stability
    card.fsrs_difficulty = nx.fsrs_difficulty
    card.scheduled_days = nx.scheduled_days
    card.elapsed_days = 0
    card.reps = nx.reps
    card.lapses = nx.lapses
    card.state = nx.state
    card.due_date = datetime.strptime(nx.due_date, "%Y-%m-%d").date()
    card.target_stability = nx.target_stability
    card.avg_response_time_ms = avg
    card.last_review = datetime.utcnow()

    # 2b. collective calibration updates (online Elo + running stats).
    new_diff, new_ability = calibration.update_elo(
        item_stats.elo_difficulty or 0.0,
        item_stats.elo_n_updates or 0,
        sp.elo_ability or 0.0,
        is_correct,
        z_item,
    )
    item_stats.elo_difficulty = new_diff
    item_stats.elo_n_updates = (item_stats.elo_n_updates or 0) + 1
    sp.elo_ability = new_ability

    item_stats.n_responses = (item_stats.n_responses or 0) + 1
    if is_correct:
        item_stats.n_correct = (item_stats.n_correct or 0) + 1
        # per-item log-RT distribution is built from CORRECT responses only
        item_stats.log_rt_mean, item_stats.log_rt_sd, _ = calibration.update_running_logrt(
            item_stats.log_rt_mean, item_stats.log_rt_sd, item_stats.n_correct - 1, response_time_ms
        )
    item_stats.accuracy = item_stats.n_correct / item_stats.n_responses
    item_stats.d0_prior, item_stats.s0_prior_good = calibration.derive_priors(item_stats)

    # per-user reading-speed distribution (all valid responses)
    us_mean, us_sd, us_n = calibration.update_running_logrt(
        user_speed.log_rt_mean, user_speed.log_rt_sd, user_speed.n_responses or 0, response_time_ms
    )
    user_speed.log_rt_mean, user_speed.log_rt_sd, user_speed.n_responses = us_mean, us_sd, us_n

    # 3. progression upsert — keyed by (sujet, siman) : a question only counts as
    # "validated" once it has been answered correctly at least once. A wrong
    # answer never advances progress, and re-answering is not double-counted.
    prog = Progression.query.filter_by(user_id=user.id, subject=q.subject, siman=q.siman).first()
    total_in_siman = Question.query.filter_by(subject=q.subject, siman=q.siman, status="approved").count()
    validated = (
        db.session.query(UserAnswer.question_id)
        .join(Question, Question.id == UserAnswer.question_id)
        .filter(
            UserAnswer.user_id == user.id,
            UserAnswer.is_correct.is_(True),
            Question.subject == q.subject,
            Question.siman == q.siman,
            Question.status == "approved",
        )
        .distinct()
        .count()
    )
    if prog is None:
        prog = Progression(user_id=user.id, subject=q.subject, siman=q.siman)
        db.session.add(prog)
    prog.questions_answered = validated
    prog.average_score = (validated / total_in_siman) if total_in_siman else 0
    prog.status = "completed" if total_in_siman and validated >= total_in_siman else "in_progress"

    # 4. streak + points on the student profile
    today = date.today()
    new_streak = sp.streak_days or 0
    if sp.last_activity_date != today:
        yesterday = today - timedelta(days=1)
        new_streak = new_streak + 1 if sp.last_activity_date == yesterday else 1
    sp.total_points = (sp.total_points or 0) + breakdown["total"]
    sp.streak_days = new_streak
    sp.last_activity_date = today

    # 5. bonus de complétion quotidienne — uniquement pour le mode "Révision
    # du jour", et seulement quand cette réponse fait tomber le nombre de
    # cartes dues à 0 (autoflush : la requête ci-dessous voit déjà le
    # card.due_date mis à jour en mémoire au step 2 du FSRS upsert).
    daily_bonus = 0
    if mode == "revision_daily" and due_before > 0 and sp.last_daily_completion_date != today:
        due_after = (
            FsrsCard.query.join(Question, Question.id == FsrsCard.question_id)
            .filter(
                FsrsCard.user_id == user.id,
                FsrsCard.due_date <= today,
                Question.status == "approved",
            )
            .count()
        )
        if due_after == 0:
            yesterday = today - timedelta(days=1)
            new_daily_streak = (
                (sp.daily_completion_streak or 0) + 1
                if sp.last_daily_completion_date == yesterday
                else 1
            )
            daily_bonus = 150 + 20 * (new_daily_streak - 1)
            sp.total_points += daily_bonus
            sp.daily_completion_streak = new_daily_streak
            sp.last_daily_completion_date = today

    db.session.commit()

    label = RATING_LABEL[rating]

    return jsonify(
        {
            "is_correct": is_correct,
            "correct_key": nq["correctKey"],
            "points": breakdown["total"],
            "combo": new_combo,
            "streak": new_streak,
            "total_points": sp.total_points,
            "explanation": nq.get("explanation"),
            "seif": q.seif,
            "rating_badge": f"{label['emoji']} {label['label']}",
            "rating_tone": label["tone"],
            "daily_bonus": daily_bonus,
        }
    )


@bp.post("/report")
def report():
    """Un étudiant signale une question douteuse : elle repasse en "pending"
    pour qu'un validateur la retraite dans /admin/questions."""
    user = current_user()
    if user is None:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    question_id = data.get("question_id")
    reason = (data.get("reason") or "").strip()

    q = Question.query.get(question_id)
    if q is None:
        return jsonify({"error": "question not found"}), 404

    previous = q.as_dict()
    q.status = "pending"
    db.session.add(
        QuestionEdit(
            question_id=q.id,
            editor_id=user.id,
            action="reported",
            note=reason or None,
            previous_content=previous,
        )
    )
    db.session.commit()
    return jsonify({"ok": True})
