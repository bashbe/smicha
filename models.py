"""SQLAlchemy models mirroring the original Supabase/Postgres schema."""

from __future__ import annotations

import uuid
from datetime import datetime, date

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# Roles available in the system (was the app_role Postgres enum).
APP_ROLES = ("super_admin", "importer", "validator", "student")
STAFF_ROLES = ("super_admin", "validator", "importer")


def _uuid() -> str:
    return str(uuid.uuid4())


class User(db.Model):
    """Auth user + profile (merges Supabase auth.users and public.profiles)."""

    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    roles = db.relationship("UserRole", backref="user", cascade="all, delete-orphan")
    student_profile = db.relationship(
        "StudentProfile", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        """Hash and store a plaintext password (PBKDF2 via Werkzeug)."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    def role_names(self) -> list[str]:
        """Return the list of role strings assigned to this user."""
        return [r.role for r in self.roles]

    def has_role(self, role: str) -> bool:
        """Check whether this user has a specific role."""
        return role in self.role_names()

    def is_staff(self) -> bool:
        """Check whether this user is a staff member (has any staff role)."""
        return any(r in STAFF_ROLES for r in self.role_names())


class UserRole(db.Model):
    __tablename__ = "user_roles"
    __table_args__ = (db.UniqueConstraint("user_id", "role", name="uq_user_role"),)

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class StudentProfile(db.Model):
    __tablename__ = "student_profiles"

    id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    full_name = db.Column(db.String(255))
    preparation_goal = db.Column(db.String(32))  # discovery | serious | intensive
    target_stability = db.Column(db.Float, default=0.95)
    # DEPRECATED (multi-parcours) — remplacé par StudentParcours.exam_date.
    # Conservé en base pour la migration/rollback, plus jamais lu ni écrit.
    exam_date = db.Column(db.Date)
    section = db.Column(db.JSON, default=list)  # list of section strings
    total_points = db.Column(db.Integer, default=0, nullable=False)
    streak_days = db.Column(db.Integer, default=0, nullable=False)
    last_activity_date = db.Column(db.Date)
    # DEPRECATED (multi-parcours) — remplacés par StudentParcours.daily_completion_streak
    # et StudentParcours.last_daily_completion_date (série par parcours).
    # Conservés en base pour la migration/rollback, plus jamais lus ni écrits.
    daily_completion_streak = db.Column(db.Integer, default=0, nullable=False)
    last_daily_completion_date = db.Column(db.Date)
    onboarded = db.Column(db.Boolean, default=False, nullable=False)
    # Collective calibration (Phase 2): learner ability estimate, counterpart of
    # ItemStats.elo_difficulty. Higher = stronger learner.
    elo_ability = db.Column(db.Float, default=0.0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class StudentParcours(db.Model):
    """Parcours activé par un étudiant — une ligne = parcours actif.

    Porte la date de מבחן et la série de complétion quotidienne PAR parcours.
    La désactivation supprime la ligne (date + série perdues, assumé) ; les
    FsrsCard du parcours restent en base, simplement masquées du parcours
    étudiant tant qu'il n'est pas réactivé.
    """

    __tablename__ = "student_parcours"
    __table_args__ = (db.UniqueConstraint("user_id", "parcours", name="uq_student_parcours"),)

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parcours = db.Column(db.String(64), nullable=False, index=True)  # valeur de VALID_PARCOURS
    exam_date = db.Column(db.Date)  # nullable = pas de date fixée (pas de pression examen)
    daily_completion_streak = db.Column(db.Integer, default=0, nullable=False)
    last_daily_completion_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Subject(db.Model):
    """Sujet : regroupe les questions d'un même thème à l'intérieur d'un siman.

    L'ID est la clé stable référencée par `Question.subject_id` et
    `Progression.subject_id` ; `title` est le seul champ affiché à l'étudiant
    et peut être renommé indépendamment (voir /admin/subjects/rename) sans
    avoir à toucher chaque question qui le partage.
    """

    __tablename__ = "subjects"
    __table_args__ = (
        db.UniqueConstraint("parcours", "siman", "title", name="uq_subject_parcours_siman_title"),
    )

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    parcours = db.Column(db.String(64), nullable=False, index=True)
    siman = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    text = db.Column(db.Text)
    choices = db.Column(db.JSON)
    correct_answer = db.Column(db.Text)
    explanation = db.Column(db.Text)
    difficulty = db.Column(db.Integer, default=2, nullable=False)
    section = db.Column(db.JSON, default=lambda: ["shulchan_aruch"], nullable=False)
    tags = db.Column(db.JSON, default=list)
    # Toute question est acceptée par défaut ("approved"). Elle ne repasse en
    # "pending" que si un étudiant la signale (bouton "signaler" côté player) ;
    # l'admin la traite alors dans /admin/questions (filtre statut "pending").
    status = db.Column(db.String(16), default="approved", nullable=False, index=True)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    validated_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    validator_note = db.Column(db.Text)
    # second-migration fields
    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="SET NULL"), index=True)
    siman = db.Column(db.Integer, index=True)
    seif = db.Column(db.Integer)
    hint = db.Column(db.Text)
    parcours = db.Column(db.String(64), index=True)
    # third-migration fields
    question_type = db.Column(db.String(48), index=True)
    payload = db.Column(db.JSON)
    source_ref = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    subject = db.relationship("Subject")

    def section_list(self) -> list[str]:
        """Return the question's exam sections as a normalized list.

        Handles both list and string storage formats; defaults to shulchan_aruch.
        """
        if isinstance(self.section, list):
            return self.section
        if isinstance(self.section, str) and self.section:
            return [self.section]
        return ["shulchan_aruch"]

    def as_dict(self) -> dict:
        """Serialize the question to a dictionary (used by admin preview/editing)."""
        return {
            "id": self.id,
            "text": self.text,
            "choices": self.choices,
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
            "difficulty": self.difficulty,
            "section": self.section,
            "tags": self.tags or [],
            "status": self.status,
            "subject_id": self.subject_id,
            "subject": self.subject.title if self.subject else None,
            "siman": self.siman,
            "seif": self.seif,
            "hint": self.hint,
            "parcours": self.parcours,
            "question_type": self.question_type,
            "payload": self.payload,
            "source_ref": self.source_ref,
        }


class QuestionReport(db.Model):
    """Signalement d'une question par un étudiant simple (rôle `student` sans
    rôle staff). Tant que le signalement est "open", la question est retirée
    UNIQUEMENT pour ce `reporter_id` (Question.status global n'est pas touché).
    Un validateur/super_admin peut "confirmer" (retire la question pour tout
    le monde, Question.status -> "pending") ou "rejeter" (le signalement est
    injustifié, la question redevient visible pour ce seul étudiant).
    """

    __tablename__ = "question_reports"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reason = db.Column(db.Text)
    status = db.Column(db.String(16), default="open", nullable=False, index=True)  # open | confirmed | dismissed
    resolved_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class QuestionEdit(db.Model):
    __tablename__ = "question_edits"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    editor_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(16), nullable=False)  # approved | corrected | rejected | reported
    previous_content = db.Column(db.JSON)
    new_content = db.Column(db.JSON)
    note = db.Column(db.Text)
    edited_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Progression(db.Model):
    __tablename__ = "progression"
    __table_args__ = (
        db.UniqueConstraint("user_id", "subject_id", name="uq_progression_user_subject"),
    )

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    # Le siman est porté par Subject (subject_id l'implique déjà) — plus de
    # colonne siman séparée ici.
    subject_id = db.Column(db.String(36), db.ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    status = db.Column(db.String(16), default="in_progress", nullable=False)
    average_score = db.Column(db.Float, default=0)
    questions_answered = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserAnswer(db.Model):
    __tablename__ = "user_answers"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    given_answer = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    response_time_ms = db.Column(db.Integer, default=0, nullable=False)
    points_earned = db.Column(db.Integer, default=0, nullable=False)
    combo_at_time = db.Column(db.Integer, default=0, nullable=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # Collective calibration (Phase 2) — append-only enrichment, never rewritten.
    z_item = db.Column(db.Float)     # (log rt - mu_item) / sigma_item
    z_user = db.Column(db.Float)     # normalised for the user's reading speed
    auto_grade = db.Column(db.Float)  # continuous 1.0..4.0 grade derived from latency
    # Retention instrumentation — R predicted by FSRS at the moment of this
    # review (from the card's pre-update stability + elapsed days). NULL when
    # the card was not yet engaged by FSRS (no prediction to score). Compared
    # against is_correct to measure true retention / log loss.
    predicted_r = db.Column(db.Float)


class FsrsCard(db.Model):
    __tablename__ = "fsrs_cards"
    __table_args__ = (db.UniqueConstraint("user_id", "question_id", name="uq_fsrs_user_question"),)

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    due_date = db.Column(db.Date, default=date.today, nullable=False, index=True)
    stability = db.Column(db.Float, default=0.5, nullable=False)
    fsrs_difficulty = db.Column(db.Float, default=5, nullable=False)
    elapsed_days = db.Column(db.Integer, default=0, nullable=False)
    scheduled_days = db.Column(db.Integer, default=1, nullable=False)
    reps = db.Column(db.Integer, default=0, nullable=False)
    lapses = db.Column(db.Integer, default=0, nullable=False)
    state = db.Column(db.String(16), default="new", nullable=False)
    last_review = db.Column(db.DateTime)
    avg_response_time_ms = db.Column(db.Integer, default=0, nullable=False)
    target_stability = db.Column(db.Float, default=0.95, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ItemStats(db.Model):
    """Collective per-item aggregates driving the difficulty prior (Phase 2).

    Only aggregates are stored here — no cross-user identification. Raw
    response times stay on UserAnswer under the user_id.
    """

    __tablename__ = "item_stats"

    question_id = db.Column(
        db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True
    )
    question_type = db.Column(db.String(48))
    hidden_difficulty = db.Column(db.Integer)  # questions.difficulty (1..3) content prior
    n_responses = db.Column(db.Integer, default=0, nullable=False)
    n_correct = db.Column(db.Integer, default=0, nullable=False)
    accuracy = db.Column(db.Float, default=0.0, nullable=False)
    log_rt_mean = db.Column(db.Float)  # mean of log(rt) over CORRECT responses
    log_rt_sd = db.Column(db.Float)    # sd of log(rt) over CORRECT responses
    elo_difficulty = db.Column(db.Float, default=0.0, nullable=False)
    elo_n_updates = db.Column(db.Integer, default=0, nullable=False)
    d0_prior = db.Column(db.Float)        # derived FSRS initial difficulty (1..10)
    s0_prior_good = db.Column(db.Float)   # derived per-item S0 for a "Good" first answer
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class UserSpeed(db.Model):
    """Per-user reading-speed distribution used to normalise latency (Phase 2)."""

    __tablename__ = "user_speed"

    user_id = db.Column(
        db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    log_rt_mean = db.Column(db.Float)
    log_rt_sd = db.Column(db.Float)
    n_responses = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
