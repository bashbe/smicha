"""Idempotent migration backfilling `HiddenTag` from the legacy `questions.tags` JSON.

Before this migration, `questions.tags` was a flat JSON list of free-text
strings, used both as fine-grained generation metadata and as the facet
shown to students. This script splits that into the two-tier tag system
(see CLAUDE.md / README.md):

1. creates the new tables (`hidden_tags`, `visible_tags`, `question_hidden_tags`,
   `tag_rules`, `tag_rule_hidden_tags`) — `db.create_all()` handles this, no
   ALTER needed since none of them existed before;
2. for every question, resolves each string in its legacy `tags` JSON to a
   `HiddenTag` (scoped by the question's `parcours`) and links it via
   `question_hidden_tags`.

The legacy `questions.tags` column is left in place (deprecated, no longer
read/written by the app) — SQLite doesn't cheaply support DROP COLUMN and
nothing depends on removing it.

Run once against an existing database:

    python -m scripts.migrate_tags

Fresh installs don't need it — there's nothing to backfill from.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from models import Question, db  # noqa: E402
from tags import get_or_create_hidden_tag  # noqa: E402


def migrate() -> None:
    app = create_app()
    with app.app_context():
        db.create_all()  # creates hidden_tags/visible_tags/tag_rules/* (new tables)

        tag_by_key: dict[tuple, object] = {}
        updated = 0
        skipped_no_parcours = 0
        for question in Question.query.all():
            names = question.tags or []
            if not isinstance(names, list) or not names or question.hidden_tags:
                continue  # nothing to migrate, or already migrated (idempotent re-run)
            if not question.parcours:
                skipped_no_parcours += 1
                continue
            resolved = []
            for name in names:
                name = str(name).strip()
                if not name:
                    continue
                key = (question.parcours, name)
                if key not in tag_by_key:
                    tag_by_key[key] = get_or_create_hidden_tag(question.parcours, name)
                resolved.append(tag_by_key[key])
            if resolved:
                question.hidden_tags = resolved
                updated += 1
        db.session.commit()
        print(f"backfilled hidden tags for {updated} question(s), {len(tag_by_key)} distinct HiddenTag created/reused")
        if skipped_no_parcours:
            print(f"WARNING: {skipped_no_parcours} question(s) had tags but no parcours set — skipped")
        print("migration complete")


if __name__ == "__main__":
    migrate()
