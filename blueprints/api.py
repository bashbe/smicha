"""JSON API consumed by the chapter player (answer submission)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from auth_helpers import current_user
from fsrs import FsrsCardState, rating_for, roll_avg, schedule_next, speed_bucket, RATING_LABEL
from models import FsrsCard, Progression, Question, StudentProfile, UserAnswer, db
from points import compute_points
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

    q = Question.query.get(question_id)
    if q is None:
        return jsonify({"error": "question not found"}), 404

    sp = StudentProfile.query.get(user.id)
    nq = normalize_db_question(q.as_dict())

    is_correct = is_correct_answer(nq, given_answer)
    bucket = speed_bucket(q.difficulty, response_time_ms)
    rating = rating_for(is_correct, bucket)
    new_combo = combo + 1 if is_correct else 0

    breakdown = compute_points(is_correct, q.difficulty, bucket, new_combo, sp.streak_days or 0)

    # 1. record the answer
    db.session.add(
        UserAnswer(
            user_id=user.id,
            question_id=q.id,
            given_answer=given_answer,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            points_earned=breakdown["total"],
            combo_at_time=new_combo,
        )
    )

    # 2. FSRS card upsert
    card = FsrsCard.query.filter_by(user_id=user.id, question_id=q.id).first()
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
            target_stability=sp.target_stability or 0.9,
            due_date=date.today().isoformat(),
        )
        db.session.add(card)

    exam = sp.exam_date.isoformat() if sp.exam_date else None
    nx = schedule_next(base, rating, exam)
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

    # 3. progression upsert — a question only counts as "validated" once it has
    # been answered correctly at least once. A wrong answer never advances
    # progress, and re-answering the same question is not double-counted.
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
        }
    )
