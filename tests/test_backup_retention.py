"""Regression tests for the seven-day backup retention window."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTO_SYNC_DB"] = "0"

from app import create_app  # noqa: E402
from backup_service import enforce_retention  # noqa: E402
from models import BackupRecord, db  # noqa: E402


def test_retention_uses_age_not_file_count():
    app = create_app()
    app.config.update(TESTING=True)
    with tempfile.TemporaryDirectory() as backup_dir, app.app_context():
        app.config["BACKUP_DIR"] = backup_dir
        db.drop_all()
        db.create_all()
        now = datetime.now()
        records = [
            BackupRecord(filename="old.sqlite3", created_at=now - timedelta(days=8)),
            BackupRecord(filename="recent.sqlite3", created_at=now - timedelta(days=6)),
            BackupRecord(filename="pinned.sqlite3", created_at=now - timedelta(days=8), keep_forever=True),
        ]
        for record in records:
            db.session.add(record)
            with open(os.path.join(backup_dir, record.filename), "wb") as file:
                file.write(b"backup")
        db.session.commit()

        enforce_retention()

        assert BackupRecord.query.filter_by(filename="old.sqlite3").first() is None
        assert BackupRecord.query.filter_by(filename="recent.sqlite3").first() is not None
        assert BackupRecord.query.filter_by(filename="pinned.sqlite3").first() is not None
        assert not os.path.exists(os.path.join(backup_dir, "old.sqlite3"))
        assert os.path.exists(os.path.join(backup_dir, "recent.sqlite3"))
        assert os.path.exists(os.path.join(backup_dir, "pinned.sqlite3"))


if __name__ == "__main__":
    test_retention_uses_age_not_file_count()
    print("backup retention tests passed")
