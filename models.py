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
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def role_names(self) -> list[str]:
        return [r.role for r in self.roles]

    def has_role(self, role: str) -> bool:
        return role in self.role_names()

    def is_staff(self) -> bool:
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
    exam_date = db.Column(db.Date)
    section = db.Column(db.JSON, default=list)  # list of section strings
    total_points = db.Column(db.Integer, default=0, nullable=False)
    streak_days = db.Column(db.Integer, default=0, nullable=False)
    last_activity_date = db.Column(db.Date)
    onboarded = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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
    status = db.Column(db.String(16), default="pending", nullable=False, index=True)
    created_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    validated_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    validator_note = db.Column(db.Text)
    # second-migration fields
    subject = db.Column(db.String(255), index=True)
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

    def section_list(self) -> list[str]:
        """Always returns section as a list, regardless of how it's stored."""
        if isinstance(self.section, list):
            return self.section
        if isinstance(self.section, str) and self.section:
            return [self.section]
        return ["shulchan_aruch"]

    def as_dict(self) -> dict:
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
            "subject": self.subject,
            "siman": self.siman,
            "seif": self.seif,
            "hint": self.hint,
            "parcours": self.parcours,
            "question_type": self.question_type,
            "payload": self.payload,
            "source_ref": self.source_ref,
        }


class QuestionEdit(db.Model):
    __tablename__ = "question_edits"

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    question_id = db.Column(db.String(36), db.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    editor_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"))
    action = db.Column(db.String(16), nullable=False)  # approved | corrected | rejected
    previous_content = db.Column(db.JSON)
    new_content = db.Column(db.JSON)
    note = db.Column(db.Text)
    edited_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Progression(db.Model):
    __tablename__ = "progression"
    __table_args__ = (
        db.UniqueConstraint("user_id", "subject", "siman", name="uq_progression_user_subject_siman"),
    )

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    subject = db.Column(db.String(255), default="", nullable=False)
    siman = db.Column(db.Integer, default=0, nullable=False)
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
