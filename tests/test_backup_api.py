"""Access-control tests for the remote backup endpoint."""

from __future__ import annotations

import os
import sys
import hashlib
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["AUTO_SYNC_DB"] = "0"

from app import create_app  # noqa: E402
from models import BackupApiToken, db  # noqa: E402


def test_remote_backup_requires_the_dedicated_key():
    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(BackupApiToken(
            label="test", token_hash=hashlib.sha256(b"test-backup-key").hexdigest()
        ))
        db.session.commit()
    client = app.test_client()

    assert client.post("/api/backup-db").status_code == 401
    with patch("blueprints.api.create_backup") as create:
        create.return_value = SimpleNamespace(
            filename="smiha_test.sqlite3", size_bytes=42, created_at=datetime(2026, 1, 1)
        )
        response = client.post("/api/backup-db", headers={"X-Backup-API-Key": "test-backup-key"})

    assert response.status_code == 201
    assert response.json["filename"] == "smiha_test.sqlite3"
    create.assert_called_once_with()


def test_remote_backup_rejects_requests_when_no_key_exists():
    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        db.drop_all()
        db.create_all()
    assert app.test_client().post("/api/backup-db").status_code == 401


if __name__ == "__main__":
    test_remote_backup_requires_the_dedicated_key()
    test_remote_backup_rejects_requests_when_no_key_exists()
    print("backup API tests passed")
