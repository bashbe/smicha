"""Régénère les icônes PWA (static/images/icon-192.png, icon-512.png) depuis
static/favicon.svg. À relancer manuellement si le favicon change.

Nécessite `cairosvg` (non listé dans requirements.txt : outil de build, pas une
dépendance runtime de l'app) : pip install cairosvg
"""

import os

import cairosvg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SVG_PATH = os.path.join(ROOT, "static", "favicon.svg")
SIZES = (192, 512)

if __name__ == "__main__":
    for size in SIZES:
        out_path = os.path.join(ROOT, "static", "images", f"icon-{size}.png")
        cairosvg.svg2png(url=SVG_PATH, write_to=out_path, output_width=size, output_height=size)
        print(f"écrit {out_path}")
