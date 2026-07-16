"""Idempotent migration for the `Subject` table (sujets référencés par ID).

Avant cette migration, `questions.subject` et `progression.subject` étaient du
texte brut — un renommage de sujet devait chercher/remplacer sur toutes les
lignes qui le partageaient. Ce script :

1. crée la table `subjects` (nouvelle table — `db.create_all()` s'en charge) ;
2. ajoute la colonne `subject_id` à `questions` et `progression` ;
3. crée un `Subject` par (parcours, siman, texte) distinct rencontré dans
   `questions.subject`, et backfill `questions.subject_id` en conséquence ;
4. backfill `progression.subject_id` par correspondance (siman, texte) — sans
   colonne `parcours` sur `progression`, c'est la seule clé disponible, ce qui
   est sans ambiguïté tant qu'un seul parcours existe (`VALID_PARCOURS`
   aujourd'hui) ;
5. tente de supprimer les anciennes colonnes texte (`questions.subject`,
   `progression.subject`, `progression.siman`) — best-effort : ignoré si le
   moteur SQL ne supporte pas DROP COLUMN (SQLite < 3.35).

Run once against an existing database (dev SQLite you don't want to wipe, or
prod Postgres):

    python -m scripts.migrate_subjects

Fresh installs don't need it — `python seed.py` builds the full schema
directly with `subject_id`.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text  # noqa: E402

from app import create_app  # noqa: E402
from models import db  # noqa: E402
from subjects import get_or_create_subject  # noqa: E402


def migrate() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()  # creates `subjects` (new table, no ALTER needed)

        insp = inspect(db.engine)
        for table in ("questions", "progression"):
            existing = {c["name"] for c in insp.get_columns(table)}
            if "subject_id" in existing:
                print(f"ok   {table}.subject_id already present")
                continue
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN subject_id VARCHAR(36)"))
            print(f"add  {table}.subject_id VARCHAR(36)")
        db.session.commit()

        insp = inspect(db.engine)  # refresh after the ALTERs above
        q_cols = {c["name"] for c in insp.get_columns("questions")}
        if "subject" not in q_cols:
            print("skip backfill: questions.subject already absent — nothing left to migrate")
            return

        # 1. one Subject per distinct (parcours, siman, subject text), backfill questions
        rows = db.session.execute(
            text("SELECT id, subject, siman, parcours FROM questions WHERE subject_id IS NULL")
        ).fetchall()
        subject_id_by_key: dict[tuple, str] = {}
        subject_id_by_siman_title: dict[tuple, str] = {}
        updated = 0
        for qid, subject_text, siman, parcours in rows:
            if not subject_text or siman is None or not parcours:
                continue
            key = (parcours, siman, subject_text)
            if key not in subject_id_by_key:
                subj = get_or_create_subject(parcours, siman, subject_text)
                subject_id_by_key[key] = subj.id
                subject_id_by_siman_title.setdefault((siman, subject_text), subj.id)
            db.session.execute(
                text("UPDATE questions SET subject_id = :sid WHERE id = :qid"),
                {"sid": subject_id_by_key[key], "qid": qid},
            )
            updated += 1
        db.session.commit()
        print(f"backfilled {updated} questions.subject_id ({len(subject_id_by_key)} subjects created/reused)")

        # 2. progression backfill — no parcours column there, match by (siman, title)
        prog_cols = {c["name"] for c in insp.get_columns("progression")}
        if "subject" in prog_cols:
            prog_rows = db.session.execute(
                text("SELECT id, subject, siman FROM progression WHERE subject_id IS NULL")
            ).fetchall()
            prog_updated = prog_missing = 0
            for pid, subject_text, siman in prog_rows:
                sid = subject_id_by_siman_title.get((siman, subject_text))
                if sid is None:
                    prog_missing += 1
                    continue
                db.session.execute(
                    text("UPDATE progression SET subject_id = :sid WHERE id = :pid"),
                    {"sid": sid, "pid": pid},
                )
                prog_updated += 1
            db.session.commit()
            print(f"backfilled {prog_updated} progression.subject_id ({prog_missing} unmatched, left NULL)")
            if prog_missing:
                print(f"WARNING: {prog_missing} progression row(s) unmatched — orphaned, will be "
                      f"recreated on next answer (see blueprints/api.py progression upsert)")

        # 3. best-effort: drop the now-unused legacy text columns
        for table, column in (("questions", "subject"), ("progression", "subject"), ("progression", "siman")):
            try:
                db.session.execute(text(f"ALTER TABLE {table} DROP COLUMN {column}"))
                db.session.commit()
                print(f"drop {table}.{column}")
            except Exception as e:  # noqa: BLE001
                db.session.rollback()
                print(f"WARNING: could not drop {table}.{column} ({e}) — "
                      f"drop it manually if your DB engine supports it; harmless to leave in place")

        print("migration complete")


if __name__ == "__main__":
    migrate()
