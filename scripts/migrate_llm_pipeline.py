"""Idempotent migration creating the LLM-pipeline tables.

New tables (all created by `db.create_all()`, no ALTER needed since none of
them existed before):

- `llm_pipeline_runs`      — one row per `/llm-pipeline` skill execution
- `llm_reviews`            — one row per (run, question, agent persona, iteration) vote
- `llm_coherence_reports`  — one row per coherence report (inter-question analysis)

The LLM provider is the agent running the skill — there is no external API
call, so no config/secret is involved here.

Run once against an existing database:

    python -m scripts.migrate_llm_pipeline

Fresh installs don't need it — `python seed.py` builds the full schema directly.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import db  # noqa: E402


def migrate() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()  # creates llm_pipeline_runs / llm_reviews / llm_coherence_reports
        print("OK: llm_pipeline_runs, llm_reviews, llm_coherence_reports ready")


if __name__ == "__main__":
    migrate()
