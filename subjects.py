"""Lookup/creation and renaming of `Subject` rows.

Decouples the grouping key of a "sujet" (its stable `id`, referenced by
`Question.subject_id` and `Progression.subject_id`) from its displayed Hebrew
title. The JSON import format still carries free text (`sujet`) — this module
is where that text gets resolved to a stable ID, so a rename only touches one
row instead of every question that shares the old text.
"""

from __future__ import annotations

from models import Progression, Question, Subject, db


def get_or_create_subject(parcours: str, siman: int, title: str) -> Subject:
    """Lookup-or-create a Subject by exact (parcours, siman, title) match."""
    title = (title or "").strip()
    subj = Subject.query.filter_by(parcours=parcours, siman=siman, title=title).first()
    if subj is None:
        subj = Subject(parcours=parcours, siman=siman, title=title)
        db.session.add(subj)
        db.session.flush()
    return subj


def rename_subject(subject_id: str, new_title: str) -> dict:
    """Rename a subject's displayed title, or merge it into an existing one.

    If another subject in the same (parcours, siman) already has the target
    title, the two are merged instead: every Question and Progression row
    pointing at `subject_id` is reassigned to the existing subject, and the
    now-empty subject is deleted — mirroring what the old text-based rename
    did whenever two subjects were renamed to the same value.

    Returns None if `subject_id` doesn't exist, otherwise a dict:
    {"subject": Subject, "old_title": str, "merged_into": Subject | None,
     "questions": [Question, ...], "previous": {question_id: dict}} —
    `previous` snapshots each affected question's `as_dict()` *before* the
    change, so the caller can build QuestionEdit audit rows (mutating
    `subject_id` in place would otherwise leave `Question.subject` — a lazy
    relationship — stale for a "new" snapshot taken from the same objects).
    """
    subj = Subject.query.get(subject_id)
    if subj is None:
        return None

    new_title = (new_title or "").strip()
    old_title = subj.title
    questions = Question.query.filter_by(subject_id=subj.id).all()
    previous = {q.id: q.as_dict() for q in questions}

    collision = Subject.query.filter(
        Subject.parcours == subj.parcours,
        Subject.siman == subj.siman,
        Subject.title == new_title,
        Subject.id != subj.id,
    ).first()

    if collision is None:
        subj.title = new_title
        return {
            "subject": subj, "old_title": old_title, "merged_into": None,
            "questions": questions, "previous": previous,
        }

    for q in questions:
        q.subject_id = collision.id
    for prog in Progression.query.filter_by(subject_id=subj.id).all():
        existing = Progression.query.filter_by(user_id=prog.user_id, subject_id=collision.id).first()
        if existing:
            db.session.delete(prog)
        else:
            prog.subject_id = collision.id
    db.session.delete(subj)
    return {
        "subject": collision, "old_title": old_title, "merged_into": collision,
        "questions": questions, "previous": previous,
    }
