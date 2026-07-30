"""Fetch a siman from Sefaria — Shulchan Aruch AND the other layers the exam covers.

Card generation is graded per `exam_section` (voir README, "Sections d'examen"), so
fetching the Shulchan Aruch alone is not enough to verify a batch: a card tagged
`tur` must be checkable against the Tour/Beit Yossef/Darkei Moshe, and a card tagged
`shulchan_aruch` against the Chelkat Mechokek and the Beit Shmuel (les deux nossei
kelim principaux d'Even haEzer, équivalents du Ch"akh/Taz en Yoré Dé'a).

Layers fetched, grouped by the app's `exam_section` — volontairement limité aux
textes principaux (demande explicite de l'utilisateur, 2026-07-30 : "le reste des
commentateurs ne sont pas necessaire") plutôt qu'à tout ce que l'API `links`
retourne (Sefaria lie des dizaines de responsa/commentaires annexes à chaque siman) :
  - shulchan_aruch : Choulhan Aroukh + Chelkat Mechokek + Beit Shmuel
  - tur            : Tour + Beit Yossef + Darkei Moshe
  - ptei_teshuva   : Pitchei Teshuva

Les œuvres autonomes (Choulhan Aroukh, Tour, Beit Yossef, Darkei Moshe) sont
récupérées directement par leur titre. Les commentaires (Chelkat Mechokek, Beit
Shmuel, Pitchei Teshuva…) sont découverts via l'API `links` de Sefaria plutôt que
codés en dur : leurs titres exacts côté Sefaria n'ont pas pu être vérifiés depuis
la session Claude Code qui a écrit ce script (l'API Sefaria y est bloquée, 403 sur
le CONNECT du proxy — voir docs/journal_chupa_kidushin.md). L'API `links` renvoie
les refs exactes, ce qui évite de deviner.

⚠️ Ce script n'a jamais pu être exécuté contre l'API réelle. Lance d'abord
`--discover` sur un siman : il liste ce que Sefaria expose vraiment, sans rien
écrire. Si un titre d'œuvre autonome est faux, il sera signalé en ERREUR (et non
silencieusement ignoré) — corrige alors DIRECT_WORKS ci-dessous.

Stdlib uniquement (urllib), aucune dépendance à installer.

Usage :
    # 1. Vérifier ce que Sefaria expose pour ce siman (n'écrit aucun fichier)
    python3 scripts/fetch_sefaria_text.py --chelek ehy --siman 26 --discover

    # 2. Tout récupérer (toutes les couches)
    python3 scripts/fetch_sefaria_text.py --chelek ehy --siman 26 27 29

    # 3. Un sous-ensemble de couches seulement
    python3 scripts/fetch_sefaria_text.py --chelek ehy --siman 26 --works shulchan_aruch tur

Fichiers écrits sous --out-dir (défaut docs/sefaria_sources/), convention de nommage
`ehy_`/`chum_` documentée dans CLAUDE.md :
  - <chelek>_<siman>_<work>.txt    — une couche, texte brut (une ligne par סעיף / ס"ק)
  - <chelek>_<siman>_<work>.json   — réponse API brute de cette couche
  - <chelek>_<siman>_ALL.txt       — toutes les couches groupées par exam_section,
    le fichier à donner à un agent de vérification
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# Œuvres autonomes, récupérées directement par "<titre>.<siman>".
# Préfixe de chelek (voir CLAUDE.md, "Parcours multi-chelek") -> titres Sefaria.
# Si un titre est refusé (404), corrige-le ici : `--discover` aide à trouver le bon.
DIRECT_WORKS = {
    "ohc": {
        "shulchan_aruch": "Shulchan Arukh, Orach Chaim",
        "tur": "Tur, Orach Chaim",
        "beit_yosef": "Beit Yosef, Orach Chaim",
        "darkei_moshe": "Darkhei Moshe, Orach Chaim",
    },
    "yd": {
        "shulchan_aruch": "Shulchan Arukh, Yoreh De'ah",
        "tur": "Tur, Yoreh Deah",
        "beit_yosef": "Beit Yosef, Yoreh Deah",
        "darkei_moshe": "Darkhei Moshe, Yoreh Deah",
    },
    "ehy": {
        "shulchan_aruch": "Shulchan Arukh, Even HaEzer",
        "tur": "Tur, Even HaEzer",
        "beit_yosef": "Beit Yosef, Even HaEzer",
        "darkei_moshe": "Darkhei Moshe, Even HaEzer",
    },
    "chum": {
        "shulchan_aruch": "Shulchan Arukh, Choshen Mishpat",
        "tur": "Tur, Choshen Mishpat",
        "beit_yosef": "Beit Yosef, Choshen Mishpat",
        "darkei_moshe": "Darkhei Moshe, Choshen Mishpat",
    },
}

# Commentaires attendus via l'API links -> slug de fichier. La clé est comparée en
# minuscules et sans ponctuation au `collectiveTitle.en` renvoyé par Sefaria, donc
# les variantes de translittération ("Chelkat Mechokek" / "Helkat Mehokek") passent
# toutes par le même slug tant qu'un des alias correspond.
#
# Volontairement limité à ces 3 (demande explicite utilisateur) : Sefaria lie des
# dizaines d'autres œuvres à chaque siman (Beur HaGra, Be'er HaGolah, Ba'er Hetev,
# Turei Zahav, Rabbi Akiva Eiger, responsa diverses...) — tout ce qui n'est pas ici
# ressort simplement en "non suivi" dans `--discover` et n'est jamais téléchargé.
COMMENTARY_ALIASES = {
    "chelkat_mechokek": ["chelkat mechokek", "helkat mehokek", "chelkat mchokek"],
    "beit_shmuel": ["beit shmuel", "bet shmuel", "beis shmuel"],
    "pitchei_teshuva": ["pitchei teshuva", "pitchei teshuvah", "pticha teshuva"],
}

# Rattachement de chaque couche à une section d'examen de l'app (VALID_SECTIONS).
WORK_SECTION = {
    "shulchan_aruch": "shulchan_aruch",
    "chelkat_mechokek": "shulchan_aruch",
    "beit_shmuel": "shulchan_aruch",
    "tur": "tur",
    "beit_yosef": "tur",
    "darkei_moshe": "tur",
    "pitchei_teshuva": "ptei_teshuva",
}

# Libellés lisibles pour l'en-tête du fichier ALL.
WORK_LABELS = {
    "shulchan_aruch": "שולחן ערוך",
    "chelkat_mechokek": "חלקת מחוקק",
    "beit_shmuel": "בית שמואל",
    "tur": "טור",
    "beit_yosef": "בית יוסף",
    "darkei_moshe": "דרכי משה",
    "pitchei_teshuva": "פתחי תשובה",
}

TEXTS_API = "https://www.sefaria.org/api/texts/"
LINKS_API = "https://www.sefaria.org/api/links/"
USER_AGENT = "smiha-flask/fetch_sefaria_text.py"

# Sefaria embeds footnotes as <sup class="footnote-marker">N</sup><i class="footnote">...</i> —
# strip marker+text entirely, footnotes being out of scope for card generation
# (prompt_generation_questions.md, PASS 1 : "Footnotes are out of scope").
FOOTNOTE_RE = re.compile(r'<sup[^>]*>.*?</sup>|<i class="footnote"[^>]*>.*?</i>', re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")
NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")


def _strip_html(s) -> str:
    """Strip Sefaria's footnote markup (marker + text) and any remaining HTML tags."""
    if not isinstance(s, str):
        return ""
    return TAG_RE.sub("", FOOTNOTE_RE.sub("", s)).strip()


def _flatten(value) -> list[str]:
    """Sefaria's `he` is a string, a list of strings, or a nested list — always flatten it."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_flatten(item))
        return out
    return []


def _normalize_title(title: str) -> str:
    """Lowercase + strip punctuation, so translittération variants compare equal."""
    return NON_ALNUM_RE.sub("", (title or "").lower()).strip()


def _slug_for_commentary(collective_title: str) -> str | None:
    """Map a Sefaria collectiveTitle to our file slug, or None if we don't track it."""
    normalized = _normalize_title(collective_title)
    for slug, aliases in COMMENTARY_ALIASES.items():
        if any(_normalize_title(alias) in normalized for alias in aliases):
            return slug
    return None


def _get(url: str, timeout: float) -> dict | list:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_direct_work(title: str, siman: int, timeout: float = 30.0) -> dict:
    """Fetch a standalone work (SA, Tur, Beit Yosef, Darkei Moshe) for one siman."""
    return _get(TEXTS_API + urllib.parse.quote(f"{title}.{siman}"), timeout)


def fetch_links(base_title: str, siman: int, timeout: float = 60.0) -> list:
    """Fetch every text Sefaria links to this siman, with the linked text included."""
    url = LINKS_API + urllib.parse.quote(f"{base_title}.{siman}") + "?with_text=1"
    payload = _get(url, timeout)
    return payload if isinstance(payload, list) else []


def direct_work_to_text(payload: dict) -> str:
    """Render a standalone work as one 'סעיף N: ...' line per segment."""
    lines = []
    for i, segment in enumerate(_flatten(payload.get("he")), 1):
        text = _strip_html(segment)
        if text:
            lines.append(f"סעיף {i}: {text}")
    return "\n".join(lines)


def group_commentaries(links: list) -> dict[str, list[dict]]:
    """Group link entries by our commentary slug, keeping ref + Hebrew text."""
    grouped: dict[str, list[dict]] = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        collective = link.get("collectiveTitle") or {}
        title_en = collective.get("en") if isinstance(collective, dict) else None
        slug = _slug_for_commentary(title_en or link.get("index_title") or "")
        if not slug:
            continue
        text = " ".join(t for t in (_strip_html(s) for s in _flatten(link.get("he"))) if t)
        if not text:
            continue
        grouped.setdefault(slug, []).append(
            {"ref": link.get("ref") or "", "anchor": link.get("anchorRef") or "", "text": text}
        )
    return grouped


def commentary_to_text(entries: list[dict]) -> str:
    """Render grouped commentary entries, one line per ס\"ק, anchored to its seif."""
    lines = []
    for entry in entries:
        anchor = entry["anchor"].split(".")[-1] if entry["anchor"] else "?"
        lines.append(f"[{entry['ref']}] (על סעיף {anchor}): {entry['text']}")
    return "\n".join(lines)


def _write(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def run_discover(chelek: str, siman: int, timeout: float) -> None:
    """Print what Sefaria actually exposes for this siman — writes nothing."""
    works = DIRECT_WORKS[chelek]
    print(f"\n=== DISCOVER {chelek} siman {siman} ===")
    print("\n-- Œuvres autonomes (titres codés dans DIRECT_WORKS) --")
    for slug, title in works.items():
        try:
            payload = fetch_direct_work(title, siman, timeout)
            n = len(_flatten(payload.get("he")))
            print(f"  OK    {slug:<16} '{title}' -> {n} segment(s)")
        except urllib.error.HTTPError as exc:
            print(f"  ERREUR {slug:<16} '{title}' -> HTTP {exc.code} — titre probablement faux, à corriger dans DIRECT_WORKS")
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  ERREUR {slug:<16} '{title}' -> {exc}")

    print("\n-- Commentaires liés (via l'API links) --")
    try:
        links = fetch_links(works["shulchan_aruch"], siman, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"  ERREUR API links : {exc}")
        return

    seen: dict[str, int] = {}
    for link in links:
        if not isinstance(link, dict):
            continue
        collective = link.get("collectiveTitle") or {}
        title_en = (collective.get("en") if isinstance(collective, dict) else None) or link.get("index_title") or "?"
        seen[title_en] = seen.get(title_en, 0) + 1

    if not seen:
        print("  (aucun lien renvoyé)")
    for title_en, count in sorted(seen.items(), key=lambda kv: -kv[1]):
        slug = _slug_for_commentary(title_en)
        mark = f"-> {slug}" if slug else "(non suivi — ajoute un alias dans COMMENTARY_ALIASES si besoin)"
        print(f"  {count:>4} liens  {title_en:<40} {mark}")


def run_fetch(chelek: str, siman: int, wanted: set[str] | None, out_dir: str, timeout: float) -> None:
    """Fetch every layer for one siman and write the per-work + ALL files."""
    works = DIRECT_WORKS[chelek]
    collected: dict[str, str] = {}

    for slug, title in works.items():
        if wanted and slug not in wanted:
            continue
        try:
            payload = fetch_direct_work(title, siman, timeout)
        except urllib.error.HTTPError as exc:
            print(f"  ERREUR {slug} ('{title}') : HTTP {exc.code} — titre probablement faux, corrige DIRECT_WORKS (voir --discover)")
            continue
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  ERREUR {slug} ('{title}') : {exc}")
            continue

        text = direct_work_to_text(payload)
        if not text:
            print(f"  VIDE  {slug} ('{title}') — aucun texte hébreu renvoyé")
            continue
        _write(os.path.join(out_dir, f"{chelek}_{siman}_{slug}.json"), json.dumps(payload, ensure_ascii=False, indent=2))
        _write(os.path.join(out_dir, f"{chelek}_{siman}_{slug}.txt"), text)
        collected[slug] = text
        print(f"  OK    {slug:<16} {len(text.splitlines())} ligne(s)")

    # Commentaires : découverte via links plutôt que titres devinés.
    try:
        links = fetch_links(works["shulchan_aruch"], siman, timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"  ERREUR API links : {exc} — aucun commentaire récupéré pour ce siman")
        links = []

    for slug, entries in group_commentaries(links).items():
        if wanted and slug not in wanted:
            continue
        text = commentary_to_text(entries)
        _write(os.path.join(out_dir, f"{chelek}_{siman}_{slug}.json"), json.dumps(entries, ensure_ascii=False, indent=2))
        _write(os.path.join(out_dir, f"{chelek}_{siman}_{slug}.txt"), text)
        collected[slug] = text
        print(f"  OK    {slug:<16} {len(entries)} passage(s) (via links)")

    if not collected:
        print(f"  Rien récupéré pour le siman {siman} — fichier ALL non écrit.")
        return

    # Fichier combiné, groupé par exam_section : c'est celui à donner à un agent
    # de vérification (une seule lecture couvre toutes les sections de l'examen).
    blocks = [f"# {chelek} siman {siman} — sources Sefaria par section d'examen\n"]
    for section in ("shulchan_aruch", "tur", "ptei_teshuva"):
        slugs = [s for s in collected if WORK_SECTION.get(s) == section]
        if not slugs:
            continue
        blocks.append(f"\n{'=' * 70}\n## exam_section: {section}\n{'=' * 70}")
        for slug in slugs:
            blocks.append(f"\n----- {WORK_LABELS.get(slug, slug)} ({slug}) -----\n{collected[slug]}")
    _write(os.path.join(out_dir, f"{chelek}_{siman}_ALL.txt"), "\n".join(blocks))
    print(f"  -> {chelek}_{siman}_ALL.txt ({len(collected)} couches)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chelek", required=True, choices=sorted(DIRECT_WORKS), help="Préfixe de chelek (ehy, chum, yd, ohc)")
    parser.add_argument("--siman", required=True, type=int, nargs="+", help="Un ou plusieurs numéros de siman")
    parser.add_argument("--out-dir", default="docs/sefaria_sources", help="Dossier de sortie (défaut: docs/sefaria_sources)")
    parser.add_argument(
        "--works",
        nargs="+",
        choices=sorted(WORK_SECTION),
        help="Limiter à certaines couches (défaut: toutes)",
    )
    parser.add_argument("--discover", action="store_true", help="Lister ce que Sefaria expose pour le siman, sans rien écrire")
    parser.add_argument("--sleep", type=float, default=1.0, help="Pause en secondes entre deux simanim (politesse envers l'API)")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout par requête, en secondes")
    args = parser.parse_args()

    if args.discover:
        for i, siman in enumerate(args.siman):
            if i:
                time.sleep(args.sleep)
            run_discover(args.chelek, siman, args.timeout)
        return

    os.makedirs(args.out_dir, exist_ok=True)
    wanted = set(args.works) if args.works else None
    for i, siman in enumerate(args.siman):
        if i:
            time.sleep(args.sleep)
        print(f"\n=== {args.chelek} siman {siman} ===")
        run_fetch(args.chelek, siman, wanted, args.out_dir, args.timeout)


if __name__ == "__main__":
    main()
