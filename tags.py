"""Lookup/creation of `HiddenTag`/`VisibleTag` rows and visible-tag resolution.

Mirrors `subjects.py`'s pattern for `Subject`: decouples the stable entity
(`HiddenTag`/`VisibleTag`, referenced by `question_hidden_tags`/`TagRule`)
from free-text input, so importers and the admin editor can keep writing
plain strings while the storage layer resolves them to canonical rows.

See CLAUDE.md / README.md for the two-tier tag system (hidden tags: many,
granular, never shown to students; visible tags: few, shown and filterable,
derived from hidden tags via `TagRule`).
"""

from __future__ import annotations

from models import HiddenTag, TagRule, VisibleTag, db


def get_or_create_hidden_tag(parcours: str, name: str) -> HiddenTag:
    """Lookup-or-create a HiddenTag by exact (parcours, name) match."""
    name = (name or "").strip()
    tag = HiddenTag.query.filter_by(parcours=parcours, name=name).first()
    if tag is None:
        tag = HiddenTag(parcours=parcours, name=name)
        db.session.add(tag)
        db.session.flush()
    return tag


def get_or_create_visible_tag(parcours: str, name: str) -> VisibleTag:
    """Lookup-or-create a VisibleTag by exact (parcours, name) match."""
    name = (name or "").strip()
    tag = VisibleTag.query.filter_by(parcours=parcours, name=name).first()
    if tag is None:
        tag = VisibleTag(parcours=parcours, name=name)
        db.session.add(tag)
        db.session.flush()
    return tag


def sync_question_hidden_tags(question, parcours: str, names: list[str]) -> None:
    """Replace a question's hidden tags with the given names (resolved/created)."""
    question.hidden_tags = [get_or_create_hidden_tag(parcours, n) for n in names if (n or "").strip()]


def visible_tags_for(question) -> list[VisibleTag]:
    """Resolve the visible tags a question exposes to students.

    A question's hidden-tag set is checked against every active `TagRule` of
    the same parcours: "or" rules match if any of the rule's hidden tags is
    present, "and" rules require all of them. The union of matching rules'
    visible tags is returned (sorted by name for stable display). A question
    whose hidden tags satisfy no active rule simply yields no visible tag —
    expected until an admin (or the tag-clustering skill) maps it.
    """
    hidden_ids = {t.id for t in question.hidden_tags}
    if not hidden_ids:
        return []
    rules = TagRule.query.filter_by(status="active").join(VisibleTag).filter(
        VisibleTag.parcours == question.parcours
    ).all()
    matched = {}
    for rule in rules:
        rule_ids = {t.id for t in rule.hidden_tags}
        if not rule_ids:
            continue
        ok = rule_ids.issubset(hidden_ids) if rule.logic == "and" else bool(rule_ids & hidden_ids)
        if ok:
            matched[rule.visible_tag.id] = rule.visible_tag
    return sorted(matched.values(), key=lambda t: t.name)
