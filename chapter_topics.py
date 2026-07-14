"""Lookup for siman/seif topic labels shown on the /app/parcours page.

La hiérarchie de contenu est parcours → simanim → sujets (Question.subject est le
thème traité DANS le siman, il peut couvrir plusieurs seifim ; le seif reste
indicatif). Les libellés gérés ici sont distincts des sujets des questions :
- le titre du siman (affiché dans le sélecteur de simanim)
- le titre du seif (indicatif, édité dans /admin/topics mais plus affiché
  dans le sélecteur)
Ils ne sont pas stockés en base : maintenus dans siman_seif_topics.json,
indexé par code parcours (ex. "bassar_bechalav").
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


def seif_topic(parcours: str, siman: int, seif: int) -> str | None:
    """Fetch the display label for a seif (sub-section), or None if not set."""
    return _load().get(parcours, {}).get("seif_topics", {}).get(str(siman), {}).get(str(seif))


def _write(data: dict) -> None:
    """Write topic labels to siman_seif_topics.json and update the cache."""
    global _cache
    with open(_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    _cache = data


def save_topics(siman_rows, seif_rows) -> None:
    """Persist edits from the admin /admin/topics form.

    siman_rows: iterable of (parcours, siman, text)
    seif_rows: iterable of (parcours, siman, seif, text)
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

    for parcours, siman, seif, text in seif_rows:
        text = text.strip()
        bucket = data.setdefault(parcours, {}).setdefault("seif_topics", {}).setdefault(str(siman), {})
        if text:
            bucket[str(seif)] = text
        else:
            bucket.pop(str(seif), None)

    _write(data)
