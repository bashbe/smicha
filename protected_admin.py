"""Invariants for the non-removable owner account."""

from __future__ import annotations

from flask import current_app
from sqlalchemy import func, text

from models import StudentProfile, User, UserRole, db


def protected_admin_email() -> str:
    return current_app.config["PROTECTED_SUPER_ADMIN_EMAIL"].strip().lower()


def is_protected_admin(user_or_email) -> bool:
    email = getattr(user_or_email, "email", user_or_email)
    return isinstance(email, str) and email.strip().lower() == protected_admin_email()


def ensure_protected_admin_invariants() -> bool:
    """Repair the owner role and install DB guards when the account exists.

    A blank database is allowed so the protected owner can create the initial
    account through signup/seed. Once present, its super_admin role is repaired
    at every application start.
    """
    email = protected_admin_email()
    user = User.query.filter(func.lower(User.email) == email).first()
    repaired = False
    if user and not UserRole.query.filter_by(user_id=user.id, role="super_admin").first():
        db.session.add(UserRole(user_id=user.id, role="super_admin"))
        db.session.commit()
        repaired = True

    _install_sqlite_guards()
    return repaired


def _install_sqlite_guards() -> None:
    """Protect the owner row and role against direct SQLite writes."""
    if db.engine.dialect.name != "sqlite":
        return

    email = protected_admin_email().replace("'", "''")
    statements = (
        f"""
        CREATE TRIGGER IF NOT EXISTS protect_owner_user_delete
        BEFORE DELETE ON users
        WHEN lower(OLD.email) = '{email}'
        BEGIN
            SELECT RAISE(ABORT, 'protected owner account cannot be deleted');
        END
        """,
        f"""
        CREATE TRIGGER IF NOT EXISTS protect_owner_email_update
        BEFORE UPDATE OF email ON users
        WHEN lower(OLD.email) = '{email}' AND lower(NEW.email) <> '{email}'
        BEGIN
            SELECT RAISE(ABORT, 'protected owner email cannot be changed');
        END
        """,
        f"""
        CREATE TRIGGER IF NOT EXISTS protect_owner_role_delete
        BEFORE DELETE ON user_roles
        WHEN OLD.role = 'super_admin'
          AND EXISTS (
              SELECT 1 FROM users
              WHERE users.id = OLD.user_id AND lower(users.email) = '{email}'
          )
        BEGIN
            SELECT RAISE(ABORT, 'protected owner role cannot be removed');
        END
        """,
        f"""
        CREATE TRIGGER IF NOT EXISTS protect_owner_role_update
        BEFORE UPDATE OF user_id, role ON user_roles
        WHEN OLD.role = 'super_admin'
          AND EXISTS (
              SELECT 1 FROM users
              WHERE users.id = OLD.user_id AND lower(users.email) = '{email}'
          )
          AND (NEW.user_id <> OLD.user_id OR NEW.role <> 'super_admin')
        BEGIN
            SELECT RAISE(ABORT, 'protected owner role cannot be changed');
        END
        """,
    )
    for statement in statements:
        db.session.execute(text(statement))
    db.session.commit()


def snapshot_protected_admin() -> dict | None:
    """Capture the credentials/identity needed to survive a full reset."""
    user = User.query.filter(func.lower(User.email) == protected_admin_email()).first()
    if not user:
        return None
    return {
        "id": user.id,
        "email": user.email,
        "password_hash": user.password_hash,
        "full_name": user.full_name,
        "created_at": user.created_at,
    }


def restore_protected_admin(snapshot: dict | None) -> None:
    """Restore the protected identity after tables have been recreated."""
    if snapshot is None:
        ensure_protected_admin_invariants()
        return

    user = User(**snapshot)
    db.session.add(user)
    db.session.add(UserRole(user_id=user.id, role="super_admin"))
    db.session.add(StudentProfile(id=user.id, full_name=user.full_name or ""))
    db.session.commit()
    ensure_protected_admin_invariants()
