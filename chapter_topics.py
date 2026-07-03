"""Lookup for siman/seif topic labels shown on the /app/parcours page.

Sujet du parcours, sujet du siman et sujet du seif sont trois niveaux distincts :
- le sujet du parcours (`Question.subject`) reste la clé de groupement existante
- le sujet du siman et le sujet du seif sont des libellés courts, non stockés en base,
  maintenus dans siman_seif_topics.json (générés pour les simanim/seifim ayant déjà
  des questions).
"""

from __future__ import annotations

import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "siman_seif_topics.json")
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            _cache = {}
    return _cache


def siman_topic(subject: str, siman: int) -> str | None:
    return _load().get(subject, {}).get("siman_topics", {}).get(str(siman))


def seif_topic(subject: str, siman: int, seif: int) -> str | None:
    return _load().get(subject, {}).get("seif_topics", {}).get(str(siman), {}).get(str(seif))


def _write(data: dict) -> None:
    global _cache
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    _cache = data


def save_topics(siman_rows, seif_rows) -> None:
    """Persist edits from the admin /admin/topics form.

    siman_rows: iterable of (subject, siman, text)
    seif_rows: iterable of (subject, siman, seif, text)
    """
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}

    for subject, siman, text in siman_rows:
        text = text.strip()
        bucket = data.setdefault(subject, {}).setdefault("siman_topics", {})
        if text:
            bucket[str(siman)] = text
        else:
            bucket.pop(str(siman), None)

    for subject, siman, seif, text in seif_rows:
        text = text.strip()
        bucket = data.setdefault(subject, {}).setdefault("seif_topics", {}).setdefault(str(siman), {})
        if text:
            bucket[str(seif)] = text
        else:
            bucket.pop(str(seif), None)

    _write(data)
