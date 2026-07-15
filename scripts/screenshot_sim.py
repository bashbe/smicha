"""Capture d'écran de la simulation multi-parcours.

Se connecte au compte de démonstration servi par ``simulate_multi_parcours serve``
et enregistre des captures (viewport mobile) des pages clés dans
``screenshots/simulations/``.

Usage (le serveur doit tourner sur $BASE_URL, défaut http://127.0.0.1:5001) :
    python -m scripts.screenshot_sim
"""

from __future__ import annotations

import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:5001")
CHROME = "/opt/pw-browsers/chromium"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "screenshots", "simulations")

EMAIL = "demo-multi@example.com"
PASSWORD = "password123"

# (nom de fichier, chemin, pleine hauteur ?)
PAGES = [
    ("01_accueil", "/app/home", True),
    ("02_profil", "/app/profil", True),
    ("03_mon_parcours", "/app/parcours", True),
    ("04_hub_revision", "/app/revision", False),
    ("05_choix_revision_jour", "/app/revision/jour", False),
]


def run() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        context = browser.new_context(
            viewport={"width": 420, "height": 900},
            device_scale_factor=2,
            locale="he-IL",
        )
        page = context.new_page()

        # Connexion
        page.goto(f"{BASE_URL}/auth", wait_until="networkidle")
        page.fill('input[name="email"]', EMAIL)
        page.fill('input[name="password"]', PASSWORD)
        page.click('button[type="submit"]')
        page.wait_for_load_state("networkidle")

        for name, path, full in PAGES:
            page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
            page.wait_for_timeout(400)
            out = os.path.join(OUT_DIR, f"{name}.png")
            page.screenshot(path=out, full_page=full)
            print(f"→ {out}")

        context.close()
        browser.close()
    print(f"captures enregistrées dans {OUT_DIR}")


if __name__ == "__main__":
    run()
