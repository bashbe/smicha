"""Session-based auth helpers and decorators (replaces Supabase auth)."""

from __future__ import annotations

from functools import wraps

from flask import g, redirect, session, url_for

from models import User


def current_user() -> User | None:
    """Get the authenticated user from the Flask context, or None if not logged in.

    User is cached in g.user after first access to avoid repeated DB lookups.
    """
    if "user" in g:
        return g.user
    user_id = session.get("user_id")
    g.user = db_get_user(user_id) if user_id else None
    return g.user


def db_get_user(user_id: str) -> User | None:
    """Fetch a user by ID from the database, or None if not found."""
    return User.query.get(user_id) if user_id else None


def login_user(user: User, remember: bool = False) -> None:
    """Record a user login: store user_id in the session and cache in g."""
    session["user_id"] = user.id
    session.permanent = remember
    g.user = user


def logout_user() -> None:
    """Clear the user session and context cache."""
    session.pop("user_id", None)
    g.pop("user", None)


def login_required(view):
    """Decorator: redirect to /auth/login if the user is not authenticated."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def staff_required(view):
    """Decorator: redirect to /admin/denied if the user lacks staff roles.

    Checks in order: authentication (redirects to /admin/login if not logged in),
    then staff role membership (redirects to /admin/denied if user exists but has no staff role).
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("admin.login"))
        if not user.is_staff():
            return redirect(url_for("admin.denied"))
        return view(*args, **kwargs)

    return wrapped
