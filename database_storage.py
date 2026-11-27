"""Keep the writable SQLite catalog in a separate file on each connection."""

from pathlib import Path

from flask import current_app
from sqlalchemy import event

from models import CATALOG_SCHEMA, db


def configure_storage():
    engine = db.engine
    configured_path = current_app.config.get("QUESTIONS_DB_PATH")
    if engine.dialect.name != "sqlite" or engine.url.database in (None, "", ":memory:"):
        if configured_path:
            raise RuntimeError("QUESTIONS_DB_PATH requires a file-based SQLite DATABASE_URL.")
        # Preserve the existing schema for in-memory tests and other backends.
        engine.update_execution_options(schema_translate_map={CATALOG_SCHEMA: None})
        return

    private_path = Path(engine.url.database).resolve()
    catalog_path = (
        Path(configured_path).expanduser().resolve()
        if configured_path
        else private_path.with_name(f"{private_path.stem}.questions.sqlite3")
    )
    if catalog_path == private_path or (
        private_path.exists() and catalog_path.exists() and private_path.samefile(catalog_path)
    ):
        raise RuntimeError("The private database and the question database must be different files.")
    private_path.parent.mkdir(parents=True, exist_ok=True)
    catalog_path.parent.mkdir(parents=True, exist_ok=True)

    @event.listens_for(engine, "connect")
    def attach_catalog(connection, _record):
        if connection.execute(
            "SELECT 1 FROM main.sqlite_master WHERE type = 'table' AND name = 'questions'"
        ).fetchone():
            raise RuntimeError("DATABASE_URL points to the old mixed database. Use a new private SQLite file.")
        connection.execute("ATTACH DATABASE ? AS catalog", (str(catalog_path),))
        if connection.execute(
            "SELECT 1 FROM catalog.sqlite_master WHERE type = 'table' AND name = 'users'"
        ).fetchone():
            raise RuntimeError("QUESTIONS_DB_PATH points to a database containing accounts.")
        # SQLite can commit changes to both files atomically using rollback journals.
        for schema in ("main", CATALOG_SCHEMA):
            mode = connection.execute(f"PRAGMA {schema}.journal_mode").fetchone()[0]
            if mode != "delete":
                mode = connection.execute(f"PRAGMA {schema}.journal_mode=DELETE").fetchone()[0]
                if mode != "delete":
                    raise RuntimeError("The split SQLite databases require DELETE journal mode.")

    current_app.config["ATTACHED_QUESTIONS_DB"] = str(catalog_path)
