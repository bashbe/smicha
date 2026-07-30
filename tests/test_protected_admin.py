"""Regression tests for the permanent protected owner account."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTO_SYNC_DB"] = "0"

from app import create_app  # noqa: E402
from models import StudentProfile, User, UserRole, db  # noqa: E402
from protected_admin import ensure_protected_admin_invariants  # noqa: E402


OWNER_EMAIL = "bcbeneghmos@gmail.com"


def _fresh_app():
    app = create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    with app.app_context():
        db.drop_all()
        db.create_all()
        ensure_protected_admin_invariants()
    return app


def _add_user(email: str, role: str) -> User:
    user = User(email=email, full_name=email)
    user.set_password("secret123")
    db.session.add(user)
    db.session.flush()
    db.session.add(UserRole(user_id=user.id, role=role))
    db.session.add(StudentProfile(id=user.id, full_name=user.full_name))
    db.session.commit()
    return user


def test_startup_repairs_owner_role():
    app = _fresh_app()
    with app.app_context():
        owner = User(email=OWNER_EMAIL, full_name="owner")
        owner.set_password("secret123")
        db.session.add(owner)
        db.session.flush()
        db.session.add(StudentProfile(id=owner.id, full_name="owner"))
        db.session.commit()

        assert not owner.has_role("super_admin")
        assert ensure_protected_admin_invariants() is True
        assert db.session.get(User, owner.id).has_role("super_admin")


def test_database_guards_block_owner_and_role_deletion():
    app = _fresh_app()
    with app.app_context():
        owner = _add_user(OWNER_EMAIL, "super_admin")
        ensure_protected_admin_invariants()

        blocked = False
        try:
            UserRole.query.filter_by(user_id=owner.id, role="super_admin").delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
            blocked = True

        assert blocked, "the protected role deletion should have failed"
        assert UserRole.query.filter_by(user_id=owner.id, role="super_admin").count() == 1

        blocked = False
        try:
            User.query.filter_by(id=owner.id).delete()
            db.session.commit()
        except Exception:
            db.session.rollback()
            blocked = True

        assert blocked, "the protected user deletion should have failed"
        assert User.query.filter_by(id=owner.id).count() == 1


def test_other_super_admin_cannot_remove_owner_role():
    app = _fresh_app()
    with app.app_context():
        owner = _add_user(OWNER_EMAIL, "super_admin")
        actor = _add_user("other-admin@example.com", "super_admin")
        owner_id = owner.id
        actor_id = actor.id
        ensure_protected_admin_invariants()

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = actor_id
    response = client.post(
        f"/admin/users/{owner_id}/roles",
        data={"role": "super_admin", "action": "remove"},
    )
    assert response.status_code == 302

    with app.app_context():
        assert UserRole.query.filter_by(user_id=owner_id, role="super_admin").count() == 1


def test_full_reset_preserves_owner_identity_credentials_and_role():
    app = _fresh_app()
    with app.app_context():
        owner = _add_user(OWNER_EMAIL, "super_admin")
        owner_id = owner.id
        password_hash = owner.password_hash

    client = app.test_client()
    with client.session_transaction() as session:
        session["user_id"] = owner_id
    response = client.post("/admin/reset-db", data={"confirm": "RESET"})
    assert response.status_code == 302

    with app.app_context():
        restored = User.query.filter_by(email=OWNER_EMAIL).one()
        assert restored.id == owner_id
        assert restored.password_hash == password_hash
        assert restored.has_role("super_admin")
        assert db.session.get(StudentProfile, owner_id) is not None


if __name__ == "__main__":
    tests = [
        test_startup_repairs_owner_role,
        test_database_guards_block_owner_and_role_deletion,
        test_other_super_admin_cannot_remove_owner_role,
        test_full_reset_preserves_owner_identity_credentials_and_role,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
