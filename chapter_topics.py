"""Lookup for siman topic labels shown on the /app/parcours page.

La hiérarchie de contenu est parcours → simanim → sujets (le Subject référencé
par Question.subject_id est le thème traité DANS le siman, il peut couvrir
plusieurs seifim ; le seif reste indicatif). Le seul libellé géré ici est le
titre du siman, affiché dans le sélecteur de simanim — distinct des sujets
des questions. Il n'est pas stocké en base : maintenu dans
siman_seif_topics.json, indexé par code parcours (ex. "bassar_bechalav").
"""

from __future__ import annotations

import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "siman_seif_topics.json")
_cache: dict | None = None


def _load() -> dict:
    """Load the topic labels from siman_seif_topics.json, caching the result."""
    global _cache
    if _cache is None:
        try:
            with open(_PATH, encoding="utf-8") as f:
                _cache = json.load(f)
        except (OSError, json.JSONDecodeError):
            _cache = {}
    return _cache


def siman_topic(parcours: str, siman: int) -> str | None:
    """Fetch the display label for a siman chapter, or None if not set."""
    return _load().get(parcours, {}).get("siman_topics", {}).get(str(siman))


def _write(data: dict) -> None:
    """Write topic labels to siman_seif_topics.json and update the cache."""
    global _cache
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    _cache = data


def save_topics(siman_rows) -> None:
    """Persist edits from the admin /admin/topics form.

    siman_rows: iterable of (parcours, siman, text)
    """
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}

    for parcours, siman, text in siman_rows:
        text = text.strip()
        bucket = data.setdefault(parcours, {}).setdefault("siman_topics", {})
        if text:
            bucket[str(siman)] = text
        else:
            bucket.pop(str(siman), None)

    _write(data)
