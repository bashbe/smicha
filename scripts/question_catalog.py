"""Export only editorial content to Git, or apply that content to the app."""

import argparse
import json
from pathlib import Path

from sqlalchemy import delete, select

from models import (
    HiddenTag, Question, Subject, TagRule, VisibleTag, db,
    question_hidden_tags, tag_rule_hidden_tags,
)

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data" / "questions.json"

# Explicit allowlist. Staff IDs, notes, reports, edits and statistics are private.
FIELDS = {
    Subject.__table__: "id parcours siman title",
    HiddenTag.__table__: "id parcours name",
    VisibleTag.__table__: "id parcours name",
    Question.__table__: (
        "id text choices correct_answer explanation difficulty section status "
        "subject_id siman seif hint parcours question_type payload source_ref"
    ),
    TagRule.__table__: "id visible_tag_id logic status source",
    question_hidden_tags: "question_id hidden_tag_id",
    tag_rule_hidden_tags: "rule_id hidden_tag_id",
}
LINK_OWNERS = {question_hidden_tags: "question_id", tag_rule_hidden_tags: "rule_id"}


def export_catalog(path):
    data = {}
    for table, fields in FIELDS.items():
        columns = [table.c[key] for key in fields.split()]
        rows = db.session.execute(select(*columns).order_by(*table.primary_key.columns))
        data[table.name] = [dict(row) for row in rows.mappings()]

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")
    temporary.replace(path)
    return len(data["questions"])


def import_catalog(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {table.name for table in FIELDS}:
        raise ValueError("Unexpected question catalog tables.")
    for table, fields in FIELDS.items():
        if any(set(row) != set(fields.split()) for row in data[table.name]):
            raise ValueError(f"Unexpected columns in {table.name}.")

    for table in FIELDS:
        rows = data[table.name]
        if table in LINK_OWNERS:
            owner = LINK_OWNERS[table]
            entities = "questions" if table is question_hidden_tags else "tag_rules"
            for row in data[entities]:
                db.session.execute(delete(table).where(table.c[owner] == row["id"]))
            if rows:
                db.session.execute(table.insert(), rows)
            continue
        for row in rows:
            match = table.c.id == row["id"]
            if db.session.scalar(select(table.c.id).where(match)) is None:
                db.session.execute(table.insert().values(**row))
            else:
                db.session.execute(table.update().where(match).values(**row))
    db.session.commit()
    return len(data["questions"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "import"])
    args = parser.parse_args()

    from app import app

    with app.app_context():
        action = export_catalog if args.action == "export" else import_catalog
        print(f"{action(CATALOG)} questions ({CATALOG.relative_to(ROOT)})")


if __name__ == "__main__":
    main()
