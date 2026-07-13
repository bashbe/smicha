"""JSON API consumed by the chapter player (answer submission)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request

from auth_helpers import current_user
from fsrs import (
    FIRST_CONTACT_POINTS,
    FsrsCardState,
    personal_bucket,
    rating_for,
    retrievability,
    roll_avg,
    schedule_next,
    RATING_LABEL,
)
import calibration
from models import (
    FsrsCard,
    ItemStats,
    Progression,
    Question,
    QuestionEdit,
    QuestionReport,
    StudentParcours,
    StudentProfile,
    UserAnswer,
    UserSpeed,
    db,
)
from points import compute_daily_points, compute_points, compute_stability_points
from question_types import PARCOURS_LABELS, is_correct_answer, normalize_db_question


def _due_count_for_parcours(user_id: str, parcours: str, today) -> int:
    """Cartes dues du parcours donné — même périmètre que la file servie par
    la révision du jour : questions approuvées, signalements "open" de
    l'utilisateur exclus (sans cette exclusion, une carte due mais signalée
    rendrait la file impossible à vider et le bonus inatteignable)."""
    hidden_subq = (
        db.session.query(QuestionReport.question_id)
        .filter(QuestionReport.reporter_id == user_id, QuestionReport.status == "open")
    )
    return (
        FsrsCard.query.join(Question, Question.id == FsrsCard.question_id)
        .filter(
            FsrsCard.user_id == user_id,
            FsrsCard.due_date <= today,
            Question.status == "approved",
            Question.parcours == parcours,
            Question.id.notin_(hidden_subq),
        )
        .count()
    )


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
    # Ligne du parcours activé par l'étudiant pour cette question — porte la
    # date de מבחן (pression FSRS) et la série de complétion quotidienne.
    spq = (
        StudentParcours.query.filter_by(user_id=user.id, parcours=q.parcours).first()
        if q.parcours else None
    )
    nq = normalize_db_question(q.as_dict())

    is_correct = is_correct_answer(nq, given_answer)

    # Cycle de vie d'une carte du point de vue du scheduling FSRS :
    #  - is_never_succeeded : aucune FsrsCard n'existe encore — l'élève n'a
    #    encore jamais répondu juste à cette question, quel que soit le
    #    nombre d'essais.
    #  - is_pre_engage : la carte existe (le premier succès a eu lieu) mais
    #    schedule_next() n'a encore jamais tourné dessus.
    #  - is_engaged : schedule_next() a déjà tourné au moins une fois —
    #    comportement FSRS normal.
    card = FsrsCard.query.filter_by(user_id=user.id, question_id=q.id).first()
    is_engaged = card is not None and (card.state != "new" or card.reps > 0)
    is_pre_engage = card is not None and not is_engaged
    is_never_succeeded = card is None

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

    # Calibration collective (Phase 2) — conservée en arrière-plan (Elo,
    # distributions log-RT par item/utilisateur, priors des nouvelles cartes)
    # mais ne pilote plus ni le rating FSRS ni le bonus de points : c'est le
    # bucket personnel ci-dessous qui s'en charge désormais.
    z_item, z_user = calibration.normalize_latency(response_time_ms, item_stats, user_speed)
    z_eff = z_item if z_item is not None else z_user
    collective_bucket = calibration.bucket_from_z(z_item, z_user, q.difficulty, response_time_ms)
    auto_grade = calibration.auto_grade_from_latency(is_correct, z_eff, collective_bucket)
    new_combo = combo + 1 if is_correct else 0

    # Bucket de vitesse personnel : comparaison au propre temps de référence
    # de l'élève sur cette carte (temps du premier succès tant que FSRS n'est
    # pas engagé, puis moyenne glissante `avg_response_time_ms`).
    bucket = personal_bucket(card.avg_response_time_ms if card else None, response_time_ms)
    rating = rating_for(is_correct, bucket)

    # Nombre de cartes dues du parcours de cette question AVANT ce traitement
    # (utilisé pour le bonus de complétion quotidienne PAR parcours — capturé
    # avant l'upsert FSRS qui va déplacer due_date de cette carte).
    due_before = 0
    if mode == "revision_daily" and spq is not None:
        due_before = _due_count_for_parcours(user.id, q.parcours, date.today())

    if is_never_succeeded and is_correct:
        # Premier succès : points fixes, aucun calcul FSRS pour l'instant
        # (voir bloc 2 plus bas).
        breakdown = {"total": FIRST_CONTACT_POINTS}
    elif (is_never_succeeded or is_pre_engage) and not is_correct:
        # Échec avant que FSRS n'ait jamais été engagé sur cette carte :
        # aucun point, comme une mauvaise réponse partout ailleurs dans
        # l'app.
        breakdown = {"total": 0}
    elif mode == "revision_daily":
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
    if is_never_succeeded and not is_correct:
        # Jamais de succès, encore raté : aucune carte créée, la question
        # reste librement accessible depuis /app/parcours (le réaffichage
        # dans la session en cours est déjà géré côté front par
        # chapitre.js : queue.push(q) sur une réponse fausse).
        label = RATING_LABEL[1]
    elif is_never_succeeded:
        # Premier succès : on crée la carte sans jamais appeler
        # schedule_next — le temps de réponse devient la référence pour
        # l'activation FSRS du prochain passage.
        card = FsrsCard(
            user_id=user.id,
            question_id=q.id,
            due_date=date.today() + timedelta(days=1),
            avg_response_time_ms=response_time_ms,
            target_stability=sp.target_stability or 0.95,
            last_review=datetime.utcnow(),
        )
        db.session.add(card)
        label = {"emoji": "🆕", "label": "היכרות ראשונה", "tone": "tone-info"}
    elif is_pre_engage and not is_correct:
        # Activée mais pas encore engagée, nouvel échec : replanifiée pour
        # demain, aucun calcul FSRS, référence de vitesse inchangée.
        card.due_date = date.today() + timedelta(days=1)
        card.last_review = datetime.utcnow()
        label = RATING_LABEL[1]
    else:
        # Activation FSRS (state encore "new", premier appel réel à
        # schedule_next) ou carte déjà engagée : scheduling FSRS-6 normal.
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
        # Pression examen : date du מבחן du parcours de la question (pas de
        # parcours activé ou pas de date fixée = aucune pression).
        exam = spq.exam_date.isoformat() if spq is not None and spq.exam_date else None
        # Collective per-item prior — blended (never substituted) into S0/D0,
        # only on the first-ever real schedule_next call for this card.
        prior = calibration.build_prior(q.difficulty, item_stats) if card.state == "new" else None
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

        label = RATING_LABEL[rating]

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

    # 5. bonus de complétion quotidienne PAR parcours — uniquement pour le
    # mode "Révision du jour", et seulement quand cette réponse fait tomber
    # à 0 le nombre de cartes dues DU PARCOURS de la question (autoflush : la
    # requête voit déjà le card.due_date mis à jour en mémoire au step 2 du
    # FSRS upsert). En mode « הכל », chaque parcours vidé déclenche son
    # propre bonus, cumulables le même jour (série et garde par parcours).
    daily_bonus = 0
    if (
        mode == "revision_daily"
        and spq is not None
        and due_before > 0
        and spq.last_daily_completion_date != today
    ):
        due_after = _due_count_for_parcours(user.id, q.parcours, today)
        if due_after == 0:
            yesterday = today - timedelta(days=1)
            new_daily_streak = (
                (spq.daily_completion_streak or 0) + 1
                if spq.last_daily_completion_date == yesterday
                else 1
            )
            daily_bonus = 150 + 20 * (new_daily_streak - 1)
            sp.total_points += daily_bonus
            spq.daily_completion_streak = new_daily_streak
            spq.last_daily_completion_date = today

    db.session.commit()

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
            # Libellé du parcours vidé — permet au toast de préciser quel
            # parcours a déclenché le bonus en mode « הכל ».
            "daily_bonus_parcours": (
                PARCOURS_LABELS.get(q.parcours, q.parcours) if daily_bonus > 0 else None
            ),
        }
    )


@bp.post("/report")
def report():
    """Un utilisateur signale une question douteuse.

    - Étudiant simple (aucun rôle staff) : la question est retirée
      UNIQUEMENT pour lui (QuestionReport "open"), tant qu'un validateur ne
      l'a pas confirmée (retrait global) ou modifiée (signalement classé).
    - Validateur / super_admin : retrait immédiat pour tout le monde
      (comportement historique) — Question.status repasse à "pending" pour
      retraitement dans /admin/questions.
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True)
    question_id = data.get("question_id")
    reason = (data.get("reason") or "").strip()

    q = Question.query.get(question_id)
    if q is None:
        return jsonify({"error": "question not found"}), 404

    if user.has_role("validator") or user.has_role("super_admin"):
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
    else:
        existing = QuestionReport.query.filter_by(
            question_id=q.id, reporter_id=user.id, status="open"
        ).first()
        if existing is None:
            db.session.add(
                QuestionReport(question_id=q.id, reporter_id=user.id, reason=reason or None)
            )
    db.session.commit()
    return jsonify({"ok": True})
