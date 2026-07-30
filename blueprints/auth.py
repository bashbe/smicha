"""Landing page + student authentication (login / signup)."""

from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from auth_helpers import current_user, login_user, logout_user
from models import StudentProfile, User, UserRole, db
from protected_admin import is_protected_admin

bp = Blueprint("auth", __name__)


def create_account(email: str, password: str, full_name: str | None) -> User:
    """Mirror of the handle_new_user trigger: create user, profile, and role."""
    user = User(email=email.lower().strip(), full_name=full_name or "")
    user.set_password(password)
    db.session.add(user)
    db.session.flush()  # assign user.id

    role = (
        "super_admin"
        if is_protected_admin(user) or user.email == current_app.config["SUPER_ADMIN_EMAIL"].lower()
        else "student"
    )
    db.session.add(UserRole(user_id=user.id, role=role))
    db.session.add(StudentProfile(id=user.id, full_name=full_name or ""))
    db.session.commit()
    return user


@bp.route("/")
def index():
    if current_user() is not None:
        return redirect(url_for("student.home"))
    return render_template("landing.html")


@bp.route("/auth", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        mode = request.form.get("mode", "login")
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember = request.form.get("remember") == "on"
        try:
            if mode == "signup":
                if email not in current_app.config["ALLOWED_SIGNUP_EMAILS"]:
                    raise ValueError("ההרשמה סגורה כרגע — כתובת דוא\"ל זו אינה מורשית ליצירת חשבון")
                if User.query.filter_by(email=email).first():
                    raise ValueError("כתובת הדוא\"ל כבר רשומה")
                if len(password) < 6:
                    raise ValueError("הסיסמה חייבת להכיל לפחות 6 תווים")
                user = create_account(email, password, request.form.get("name"))
                login_user(user, remember=remember)
            else:
                user = User.query.filter_by(email=email).first()
                if not user or not user.check_password(password):
                    raise ValueError("דוא\"ל או סיסמה שגויים")
                login_user(user, remember=remember)
            return redirect(url_for("student.home"))
        except ValueError as e:
            flash(str(e), "error")
            return render_template("auth.html", mode=mode)

    initial_mode = "signup" if request.args.get("mode") == "signup" else "login"
    return render_template("auth.html", mode=initial_mode)


@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.index"))
