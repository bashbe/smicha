"""Fetch Shulchan Aruch text from the Sefaria API and save it locally for
card-generation verification (see docs/journal_chupa_kidushin.md).

This session's network policy blocks www.sefaria.org (403 on the proxy CONNECT),
so this script must be run from a machine/session that has real internet access —
not from this Claude Code session. Stdlib only (urllib), no extra dependency.

Usage :
    python3 scripts/fetch_sefaria_text.py --chelek ehy --siman 26 27 29
    python3 scripts/fetch_sefaria_text.py --chelek chum --siman 100 101 --out-dir docs/sefaria_sources

For each siman it saves two files under --out-dir (default docs/sefaria_sources/,
matching the ehy_<siman> / chum_<siman> naming convention documented in CLAUDE.md):
  - <chelek>_<siman>.json  — raw Sefaria API response
  - <chelek>_<siman>.txt   — plain-text rendition, one line per seif ("סעיף N: ..."),
    Hebrew niqqud/markup stripped, ready to diff against generated_questions_*.json
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

# Préfixe de chelek (voir CLAUDE.md, section "Parcours multi-chelek") -> nom du
# livre tel qu'attendu par l'API Sefaria (avant encodage URL).
CHELEK_BOOKS = {
    "ohc": "Shulchan Arukh, Orach Chaim",
    "yd": "Shulchan Arukh, Yoreh De'ah",
    "ehy": "Shulchan Arukh, Even HaEzer",
    "chum": "Shulchan Arukh, Choshen Mishpat",
}

API_BASE = "https://www.sefaria.org/api/texts/"
# Sefaria embeds footnotes as <sup class="footnote-marker">N</sup><i class="footnote">...</i> —
# strip the marker+text entirely (not just the tags) since footnotes are out of scope for card
# generation (see prompt_generation_questions.md, PASS 1: "Footnotes are out of scope").
FOOTNOTE_RE = re.compile(r'<sup[^>]*>.*?</sup>|<i class="footnote"[^>]*>.*?</i>', re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    """Strip Sefaria's footnote markup (marker + text) and any remaining HTML tags."""
    no_footnotes = FOOTNOTE_RE.sub("", s or "")
    return TAG_RE.sub("", no_footnotes).strip()


def fetch_siman(chelek: str, siman: int, timeout: float = 20.0) -> dict:
    """Fetch one siman (all its seifim) from the Sefaria API. Raises on HTTP/network error."""
    book = CHELEK_BOOKS[chelek]
    ref = f"{book}.{siman}"
    url = API_BASE + urllib.parse.quote(ref)
    request = urllib.request.Request(url, headers={"User-Agent": "smiha-flask/fetch_sefaria_text.py"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def to_plain_text(payload: dict) -> str:
    """Render the API payload as one 'סעיף N: ...' line per segment, HTML-stripped."""
    segments = payload.get("he") or []
    lines = []
    for i, seif_html in enumerate(segments, 1):
        text = _strip_html(seif_html)
        if text:
            lines.append(f"סעיף {i}: {text}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chelek", required=True, choices=sorted(CHELEK_BOOKS), help="Préfixe de chelek (ehy, chum, yd, ohc)")
    parser.add_argument("--siman", required=True, type=int, nargs="+", help="Un ou plusieurs numéros de siman")
    parser.add_argument("--out-dir", default="docs/sefaria_sources", help="Dossier de sortie (défaut: docs/sefaria_sources)")
    parser.add_argument("--sleep", type=float, default=1.0, help="Pause en secondes entre deux requêtes (politesse envers l'API)")
    args = parser.parse_args()

    out_dir = args.out_dir
    import os

    os.makedirs(out_dir, exist_ok=True)

    for i, siman in enumerate(args.siman):
        if i > 0:
            time.sleep(args.sleep)
        print(f"Fetching {args.chelek} siman {siman}...")
        try:
            payload = fetch_siman(args.chelek, siman)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"  ERREUR pour siman {siman}: {exc}")
            continue

        json_path = os.path.join(out_dir, f"{args.chelek}_{siman}.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        text_path = os.path.join(out_dir, f"{args.chelek}_{siman}.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(to_plain_text(payload))

        n_seifim = len(payload.get("he") or [])
        print(f"  OK — {n_seifim} seifim -> {json_path}, {text_path}")


if __name__ == "__main__":
    main()
