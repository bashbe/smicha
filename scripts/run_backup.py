"""Scheduled-task entrypoint. PythonAnywhere: run daily at 00:00 Europe/Paris."""
from app import app
from backup_service import create_backup

with app.app_context():
    backup = create_backup()
    print(f"Backup created: {backup.filename}")
