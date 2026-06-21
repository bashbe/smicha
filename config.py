import os


class Config:
    """Application configuration. Override via environment variables."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-change-me-in-production")

    # SQL database. Defaults to a local SQLite file; set DATABASE_URL to point
    # at Postgres/MySQL in production (e.g. postgresql+psycopg://user:pw@host/db).
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(os.path.dirname(__file__), "smiha.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email auto-promoted to super_admin on first signup (mirrors the original
    # handle_new_user trigger).
    SUPER_ADMIN_EMAIL = os.environ.get("SUPER_ADMIN_EMAIL", "bcbeneghmos@gmail.com")
