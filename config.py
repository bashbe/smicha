import os
from datetime import timedelta


class Config:
    """Application configuration. Override via environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")

    # Durée de vie du cookie de session quand l'utilisateur coche « rester connecté »
    # (auth.py met session.permanent = True dans ce cas uniquement).
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)

    # SQL database. Defaults to a local SQLite file; set DATABASE_URL to point
    # at Postgres/MySQL in production (e.g. postgresql+psycopg://user:pw@host/db).
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.path.dirname(__file__), "smiha.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email auto-promoted to super_admin on first signup (mirrors the original
    # handle_new_user trigger).
    SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "bcbeneghmos@gmail.com")

    # Restriction temporaire de l'inscription (/auth, mode=signup) : liste blanche
    # d'emails séparés par des virgules. Non défini/vide => seul SUPER_ADMIN_EMAIL
    # peut créer un compte. Ne s'applique pas aux comptes créés par seed.py.
    ALLOWED_SIGNUP_EMAILS = (
        {e.strip().lower() for e in os.environ.get("ALLOWED_SIGNUP_EMAILS", "").split(",") if e.strip()}
        or {SUPER_ADMIN_EMAIL.lower()}
    )

    # Secret partagé avec le webhook GitHub (POST /webhook/deploy) pour vérifier
    # la signature HMAC-SHA256 de chaque requête. None = endpoint désactivé (401/500).
    GITHUB_WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")
