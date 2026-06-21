"""Session-based auth helpers and decorators (replaces Supabase auth)."""

from __future__ import annotations

from functools import wraps

from flask import g, redirect, session, url_for

from models import User


def current_user() -> User | None:
    if "user" in g:
        return g.user
    user_id = session.get("user_id")
    g.user = db_get_user(user_id) if user_id else None
    return g.user


def db_get_user(user_id: str) -> User | None:
    return User.query.get(user_id) if user_id else None


def login_user(user: User) -> None:
    session["user_id"] = user.id
    g.user = user


def logout_user() -> None:
    session.pop("user_id", None)
    g.pop("user", None)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("admin.login"))
        if not user.is_staff():
            return redirect(url_for("admin.denied"))
        return view(*args, **kwargs)

    return wrapped
