"""Portable database backups and retention policy.

SQLite is copied through its online backup API; PostgreSQL is delegated to
pg_dump, which is the only consistent physical export available to a web app.
"""
from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from flask import current_app
from models import BackupRecord, db


def backup_directory() -> Path:
    directory = Path(current_app.config["BACKUP_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def create_backup(created_by: str | None = None) -> BackupRecord:
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S_%f")
    target_dir = backup_directory()
    if current_app.config.get("ATTACHED_QUESTIONS_DB"):
        import sqlite3

        filename = f"smiha_{stamp}.zip"
        target = target_dir / filename
        # Pin both snapshots in a single read transaction before copying either file.
        with TemporaryDirectory(dir=target_dir) as temporary, db.engine.connect() as connection:
            source = connection.connection.driver_connection
            source.execute("BEGIN")
            files = {"main": "users.sqlite3", "catalog": "questions.sqlite3"}
            for schema in files:
                source.execute(f"SELECT count(*) FROM {schema}.sqlite_master").fetchone()
            archive = Path(temporary) / filename
            with ZipFile(archive, "w", ZIP_DEFLATED) as bundle:
                for schema, name in files.items():
                    path = Path(temporary) / name
                    destination = sqlite3.connect(path)
                    try:
                        source.backup(destination, name=schema)
                    finally:
                        destination.close()
                    bundle.write(path, name)
            archive.replace(target)
    elif uri.startswith("sqlite"):
        import sqlite3
        source_path = db.engine.url.database
        filename = f"smiha_{stamp}.sqlite3"
        target = target_dir / filename
        source = sqlite3.connect(source_path)
        destination = sqlite3.connect(target)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
    else:
        filename = f"smiha_{stamp}.sql"
        target = target_dir / filename
        subprocess.run(["pg_dump", "--no-owner", "--file", str(target), uri], check=True, timeout=300)
    record = BackupRecord(filename=filename, size_bytes=target.stat().st_size, created_by=created_by)
    db.session.add(record)
    db.session.commit()
    enforce_retention()
    return record


def enforce_retention() -> None:
    """Remove ordinary backups older than seven days; never remove pinned ones."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    removable = (
        BackupRecord.query
        .filter(BackupRecord.keep_forever.is_(False), BackupRecord.created_at < cutoff)
        .all()
    )
    for record in removable:
        path = backup_directory() / record.filename
        if path.is_file():
            path.unlink()
        db.session.delete(record)
    db.session.commit()


def delete_backup(record: BackupRecord) -> None:
    path = backup_directory() / record.filename
    if path.is_file():
        path.unlink()
    db.session.delete(record)
    db.session.commit()
