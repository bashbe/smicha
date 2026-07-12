# Service worker & mise à jour automatique des assets statiques — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** À chaque nouveau déploiement (nouveau commit git), le service worker de l'app doit automatiquement invalider son cache d'assets statiques et proposer à l'utilisateur d'actualiser, sans jamais mettre en cache de pages dynamiques/authentifiées.

**Architecture:** Un module `version.py` calcule `APP_VERSION` (hash git court, fallback timestamp) une fois au démarrage. Une route Flask `GET /sw.js` (pas un fichier statique) génère le script du service worker avec `CACHE_NAME` dérivé de `APP_VERSION` — donc le contenu du fichier change à chaque déploiement, ce qui déclenche la détection native de mise à jour du navigateur. Le service worker ne cache que les requêtes `/static/*` (stale-while-revalidate) ; tout le reste passe en direct au réseau. Un petit script dans `base.html` affiche un bandeau « Nouvelle version disponible » quand une mise à jour est prête, et déclenche l'activation + rechargement au clic. Un `manifest.json` + icônes PNG rendent l'app installable (PWA).

**Tech Stack:** Python 3.8+, Flask 3.0, Jinja2, vanilla JS (pas de framework front-end), Pillow (déjà installé) pour la génération d'icônes en dev. pytest 8.3 déjà présent comme dépendance de dev ; tests écrits pytest-compatibles mais aussi exécutables en standalone, comme `tests/test_fsrs.py`.

## Global Constraints

- Le service worker ne doit **jamais** mettre en cache autre chose que `/static/*` (spec §Service worker) — pages HTML, `/app/*`, `/admin/*`, `/auth/*`, API toujours en passthrough réseau direct.
- `/sw.js` est servi par une **route Flask**, pas un fichier statique, avec `Cache-Control: no-cache, must-revalidate` (spec §Service worker).
- Pas de précache d'une liste figée de fichiers — le cache se construit au fil des requêtes réelles (spec §Service worker).
- Le nom du cache (`CACHE_NAME`) est **toujours** dérivé de `APP_VERSION`, jamais codé en dur (spec §Documentation).
- Mise à jour utilisateur = bandeau cliquable, jamais un rechargement automatique silencieux (spec §UX de mise à jour).
- Interface hébreu RTL — vérifier l'alignement après toute modification HTML/CSS (`CLAUDE.md`/`README.md` du projet).
- Pas de nouvelle dépendance de prod (Flask/Flask-SQLAlchemy/Werkzeug uniquement). Pillow est utilisé seulement par un script dev one-off, jamais importé par l'app Flask.
- Suivre le style de tests existant : fichiers `tests/test_*.py` pytest-compatibles et exécutables en standalone (`if __name__ == "__main__"`), voir `tests/test_points.py`.
- Un commit par tâche.
- Toute modification du code → mettre à jour `README.md` (règle `CLAUDE.md`).

---

## Checkpoints de reprise

Chaque tâche ci-dessous se termine par un commit. Pour reprendre après une pause : `git log --oneline -10`, puis reprendre à la tâche suivante non cochée. Les cases à cocher (`- [ ]`) font office de suivi de progression.

---

### Task 1 : `version.py` — calcul de `APP_VERSION`

**Files:**
- Create: `version.py`
- Create: `tests/test_version.py`
- Modify: `app.py` (ajouter un context processor `app_version`)

**Interfaces:**
- Produces: `version.APP_VERSION` (str, calculé une fois à l'import) ; `version._git_short_hash() -> str | None` ; `version._compute_app_version() -> str`. Utilisés par Task 2 (`sw.py`) et par les templates via le context processor `app_version`.

- [ ] **Step 1: Write the failing test**

Créer `tests/test_version.py` :

```python
"""Tests for version.py — APP_VERSION computation.

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_version.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import version  # noqa: E402


def test_app_version_is_nonempty_string():
    assert isinstance(version.APP_VERSION, str)
    assert len(version.APP_VERSION) > 0


def test_git_short_hash_returns_hash_in_this_repo():
    # This file lives in a git checkout, so the helper must find a real hash.
    h = version._git_short_hash()
    assert h is not None
    assert len(h) >= 4
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_app_version_falls_back_to_timestamp_when_git_unavailable():
    original = version._git_short_hash
    version._git_short_hash = lambda: None
    try:
        v = version._compute_app_version()
    finally:
        version._git_short_hash = original
    assert v.isdigit()


def test_app_version_available_in_templates():
    from app import app as flask_app
    from flask import render_template_string

    with flask_app.app_context(), flask_app.test_request_context():
        rendered = render_template_string("{{ app_version }}")
    assert rendered == version.APP_VERSION


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_version.py`
Expected: `ModuleNotFoundError: No module named 'version'` (or import error) — the module doesn't exist yet.

- [ ] **Step 3: Write minimal implementation**

Créer `version.py` :

```python
"""App version helper.

APP_VERSION changes on every deploy (new git commit), which is what makes
the generated /sw.js response change bytes and triggers the browser's
native service-worker update check. See sw.py and
docs/superpowers/specs/2026-07-10-sw-auto-update-design.md.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent


def _git_short_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _compute_app_version() -> str:
    return _git_short_hash() or str(int(time.time()))


APP_VERSION = _compute_app_version()
```

Modifier `app.py` — ajouter l'import en haut du fichier (après `from auth_helpers import current_user`) :

```python
from auth_helpers import current_user
from version import APP_VERSION
```

Et ajouter un context processor, juste après le `inject_user` existant (`app.py:56-58`) :

```python
    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}

    @app.context_processor
    def inject_app_version():
        return {"app_version": APP_VERSION}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_version.py`
Expected: `4/4 passed`

- [ ] **Step 5: Commit**

```bash
git add version.py tests/test_version.py app.py
git commit -m "feat: compute APP_VERSION from git commit hash"
```

---

### Task 2 : Route `/sw.js` — service worker généré

**Files:**
- Create: `sw.py`
- Create: `tests/test_sw.py`
- Modify: `app.py` (enregistrer la route `/sw.js`)

**Interfaces:**
- Consumes: `version.APP_VERSION` (Task 1).
- Produces: `sw.render_service_worker(version: str) -> str` ; route Flask `GET /sw.js`. Utilisés par Task 4 (`base.html` enregistre `navigator.serviceWorker.register('/sw.js')`).

- [ ] **Step 1: Write the failing test**

Créer `tests/test_sw.py` :

```python
"""Tests for sw.py — the generated /sw.js service worker script.

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_sw.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sw import render_service_worker  # noqa: E402


def test_render_service_worker_embeds_version_in_cache_name():
    js = render_service_worker("abc1234")
    assert 'CACHE_NAME = "smiha-static-abc1234"' in js


def test_render_service_worker_only_intercepts_static_paths():
    js = render_service_worker("abc1234")
    assert '"/static/"' in js


def test_render_service_worker_does_not_skip_waiting_on_install():
    # The new worker must stay in "waiting" state until the user clicks the
    # update banner — auto-skipWaiting on install would activate silently.
    js = render_service_worker("abc1234")
    assert 'addEventListener("install"' not in js


def test_render_service_worker_skips_waiting_on_message():
    js = render_service_worker("abc1234")
    assert "SKIP_WAITING" in js
    assert "self.skipWaiting()" in js


def test_render_service_worker_cleans_up_old_caches_on_activate():
    js = render_service_worker("abc1234")
    assert 'addEventListener("activate"' in js
    assert "caches.delete" in js


def test_sw_route_returns_javascript_with_no_cache_header():
    from app import app as flask_app

    client = flask_app.test_client()
    resp = client.get("/sw.js")
    assert resp.status_code == 200
    assert resp.content_type.startswith("application/javascript")
    assert resp.headers["Cache-Control"] == "no-cache, must-revalidate"


def test_sw_route_body_contains_current_app_version():
    from app import app as flask_app
    from version import APP_VERSION

    client = flask_app.test_client()
    resp = client.get("/sw.js")
    assert f"smiha-static-{APP_VERSION}" in resp.get_data(as_text=True)


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_sw.py`
Expected: `ModuleNotFoundError: No module named 'sw'`

- [ ] **Step 3: Write minimal implementation**

Créer `sw.py` :

```python
"""Generates the /sw.js response body.

The service worker caches /static/* assets (stale-while-revalidate) and
rotates its cache name on every deploy (CACHE_NAME derived from
APP_VERSION) so browsers drop stale assets automatically. It never caches
anything outside /static/ — pages, /app/*, /admin/*, /auth/*, and the API
always go straight to the network.

See docs/superpowers/specs/2026-07-10-sw-auto-update-design.md.
"""

from __future__ import annotations

_SW_TEMPLATE = """const CACHE_NAME = "smiha-static-%(version)s";

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) =>
        Promise.all(
          names
            .filter((name) => name.startsWith("smiha-static-") && name !== CACHE_NAME)
            .map((name) => caches.delete(name))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || !url.pathname.startsWith("/static/")) {
    return;
  }
  event.respondWith(
    caches.open(CACHE_NAME).then((cache) =>
      cache.match(event.request).then((cached) => {
        const network = fetch(event.request)
          .then((response) => {
            if (response.ok) cache.put(event.request, response.clone());
            return response;
          })
          .catch(() => cached);
        return cached || network;
      })
    )
  );
});

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
"""


def render_service_worker(version: str) -> str:
    return _SW_TEMPLATE % {"version": version}
```

Modifier `app.py` — remplacer l'import Flask en haut du fichier :

```python
from flask import Flask
```

par :

```python
from flask import Flask, Response
```

Puis ajouter les imports du module (après `from version import APP_VERSION` ajouté en Task 1) :

```python
from sw import render_service_worker
from version import APP_VERSION
```

Et ajouter la route, après l'enregistrement des blueprints (`app.py:51-54`), avant le `context_processor` :

```python
    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @app.route("/sw.js")
    def service_worker():
        response = Response(render_service_worker(APP_VERSION), mimetype="application/javascript")
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_sw.py`
Expected: `7/7 passed`

- [ ] **Step 5: Commit**

```bash
git add sw.py tests/test_sw.py app.py
git commit -m "feat: serve /sw.js with version-derived cache name"
```

---

### Task 3 : Icônes PWA + `manifest.json`

**Files:**
- Create: `scripts/generate_pwa_icons.py`
- Create: `static/images/icon-192.png` (généré par le script)
- Create: `static/images/icon-512.png` (généré par le script)
- Create: `static/manifest.json`
- Create: `tests/test_pwa_icons.py`

**Interfaces:**
- Produces: `scripts/generate_pwa_icons._make_icon(size: int) -> PIL.Image.Image` ; fichiers `static/images/icon-192.png`, `static/images/icon-512.png`, `static/manifest.json`. Utilisés par Task 4 (`base.html` référence `/static/manifest.json`).

- [ ] **Step 1: Write the failing test**

Créer `tests/test_pwa_icons.py` :

```python
"""Tests for scripts/generate_pwa_icons.py and the generated PWA assets.

pytest-compatible, but also runnable standalone (no pytest required):

    python tests/test_pwa_icons.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.generate_pwa_icons import _make_icon  # noqa: E402

_STATIC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


def test_make_icon_192_has_correct_size():
    img = _make_icon(192)
    assert img.size == (192, 192)


def test_make_icon_512_has_correct_size():
    img = _make_icon(512)
    assert img.size == (512, 512)


def test_make_icon_draws_letter_in_contrasting_color():
    img = _make_icon(192)
    colors = img.getcolors(maxcolors=192 * 192)
    assert len(colors) > 1


def test_icon_files_exist_on_disk():
    assert os.path.exists(os.path.join(_STATIC, "images", "icon-192.png"))
    assert os.path.exists(os.path.join(_STATIC, "images", "icon-512.png"))


def test_manifest_json_is_valid_and_references_existing_icons():
    manifest_path = os.path.join(_STATIC, "manifest.json")
    assert os.path.exists(manifest_path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    assert manifest["name"]
    assert manifest["short_name"]
    assert manifest["display"] == "standalone"
    sizes = {icon["sizes"] for icon in manifest["icons"]}
    assert sizes == {"192x192", "512x512"}
    for icon in manifest["icons"]:
        rel_path = icon["src"].lstrip("/")
        assert os.path.exists(
            os.path.join(os.path.dirname(_STATIC), rel_path)
        ), f"missing {icon['src']}"


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/test_pwa_icons.py`
Expected: `ModuleNotFoundError: No module named 'scripts.generate_pwa_icons'`

- [ ] **Step 3: Write minimal implementation**

Créer `scripts/generate_pwa_icons.py` :

```python
"""One-off dev tool: (re)generate static/images/icon-192.png and
icon-512.png from the favicon design (#0D1117 background, orange ס
letter, see static/favicon.svg).

Run manually after changing the icon design:

    python -m scripts.generate_pwa_icons

This is a build-time tool, not a runtime dependency of the Flask app —
Pillow is not imported anywhere else in the project. Requires a
Hebrew-capable TrueType font on the machine running it.
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\DavidLibre-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf",
]

BG = "#0D1117"
FG = "#E07B20"
LETTER = "ס"  # ס

_HERE = os.path.dirname(os.path.abspath(__file__))
_OUT_DIR = os.path.join(os.path.dirname(_HERE), "static", "images")


def _find_font() -> str:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "No Hebrew-capable font found. Install one or add its path to "
        "FONT_CANDIDATES in scripts/generate_pwa_icons.py."
    )


def _make_icon(size: int) -> Image.Image:
    img = Image.new("RGB", (size, size), BG)
    draw = ImageDraw.Draw(img)
    radius = int(size * 0.1875)  # matches favicon.svg's rx=12 on a 64px canvas
    draw.rounded_rectangle([0, 0, size, size], radius=radius, fill=BG)
    font = ImageFont.truetype(_find_font(), int(size * 0.6))
    bbox = draw.textbbox((0, 0), LETTER, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        (size / 2 - w / 2 - bbox[0], size / 2 - h / 2 - bbox[1]),
        LETTER,
        font=font,
        fill=FG,
    )
    return img


def main() -> None:
    os.makedirs(_OUT_DIR, exist_ok=True)
    for size in (192, 512):
        icon = _make_icon(size)
        out_path = os.path.join(_OUT_DIR, f"icon-{size}.png")
        icon.save(out_path)
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
```

Générer les icônes :

```bash
python -m scripts.generate_pwa_icons
```

Expected output:
```
wrote .../static/images/icon-192.png
wrote .../static/images/icon-512.png
```

Créer `static/manifest.json` :

```json
{
  "name": "סמיכה — הכנה לבחינה",
  "short_name": "סמיכה",
  "start_url": "/",
  "display": "standalone",
  "lang": "he",
  "dir": "rtl",
  "background_color": "#0D1117",
  "theme_color": "#0D1117",
  "icons": [
    {
      "src": "/static/images/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/images/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/test_pwa_icons.py`
Expected: `5/5 passed`

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_pwa_icons.py static/images/icon-192.png static/images/icon-512.png static/manifest.json tests/test_pwa_icons.py
git commit -m "feat: add PWA manifest and generated app icons"
```

---

### Task 4 : Enregistrement du service worker + bandeau de mise à jour

**Files:**
- Modify: `templates/base.html`
- Modify: `static/css/styles.css`

**Interfaces:**
- Consumes: route `/sw.js` (Task 2), `/static/manifest.json` (Task 3).
- Produces: aucune interface consommée par une tâche suivante — c'est la dernière pièce fonctionnelle.

- [ ] **Step 1: Ajouter le lien manifest et le meta theme-color**

Dans `templates/base.html`, remplacer :

```html
  <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}" />
  <link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}" />
  {% block head %}{% endblock %}
```

par :

```html
  <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}" />
  <link rel="icon" type="image/svg+xml" href="{{ url_for('static', filename='favicon.svg') }}" />
  <link rel="manifest" href="{{ url_for('static', filename='manifest.json') }}" />
  <meta name="theme-color" content="#0D1117" />
  {% block head %}{% endblock %}
```

- [ ] **Step 2: Ajouter le bandeau de mise à jour et le script d'enregistrement**

Dans `templates/base.html`, remplacer :

```html
<body>
  {% block body %}{% endblock %}
</body>
</html>
```

par :

```html
<body>
  {% block body %}{% endblock %}

  <div id="sw-update-banner" class="sw-update-banner" hidden>
    <span>גרסה חדשה זמינה</span>
    <button type="button" id="sw-update-reload">רענון</button>
  </div>

  <script>
    (function () {
      if (!("serviceWorker" in navigator)) return;

      var banner = document.getElementById("sw-update-banner");
      var reloadBtn = document.getElementById("sw-update-reload");
      var waitingWorker = null;

      function showBanner(worker) {
        waitingWorker = worker;
        banner.hidden = false;
      }

      reloadBtn.addEventListener("click", function () {
        if (!waitingWorker) return;
        waitingWorker.postMessage({ type: "SKIP_WAITING" });
      });

      navigator.serviceWorker.addEventListener("controllerchange", function () {
        window.location.reload();
      });

      navigator.serviceWorker.register("/sw.js").then(function (registration) {
        if (registration.waiting && navigator.serviceWorker.controller) {
          showBanner(registration.waiting);
        }

        registration.addEventListener("updatefound", function () {
          var newWorker = registration.installing;
          if (!newWorker) return;
          newWorker.addEventListener("statechange", function () {
            if (newWorker.state === "installed" && navigator.serviceWorker.controller) {
              showBanner(newWorker);
            }
          });
        });

        document.addEventListener("visibilitychange", function () {
          if (document.visibilityState === "visible") {
            registration.update();
          }
        });
      });
    })();
  </script>
</body>
</html>
```

- [ ] **Step 3: Ajouter le CSS du bandeau**

Dans `static/css/styles.css`, ajouter à la fin du fichier :

```css
/* Service worker update banner */
.sw-update-banner {
  position: fixed;
  inset-inline: 0;
  bottom: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: 0.75rem 1rem;
  padding-bottom: calc(0.75rem + env(safe-area-inset-bottom));
  background: var(--fg);
  color: var(--bg);
  font-size: var(--text-sm);
}
.sw-update-banner[hidden] {
  display: none;
}
.sw-update-banner button {
  border: 1px solid var(--bg);
  background: transparent;
  color: var(--bg);
  border-radius: var(--radius-btn);
  padding: 0.375rem 0.875rem;
  font-size: var(--text-sm);
  cursor: pointer;
}
```

- [ ] **Step 4: Vérification manuelle dans le navigateur**

Cette fonctionnalité (enregistrement du service worker, bandeau de mise à jour) ne peut pas être testée par un test automatisé Python — c'est un comportement navigateur. Vérifier avec le serveur de dev :

1. Démarrer le serveur (`preview_start` ou `python app.py`).
2. Charger la page d'accueil, ouvrir `preview_console_logs` — aucune erreur JS.
3. `preview_eval`: `navigator.serviceWorker.getRegistration().then(r => r && r.active && r.active.scriptURL)` doit retourner une URL se terminant par `/sw.js`.
4. `preview_network` : vérifier que la requête vers `/sw.js` a bien l'en-tête `cache-control: no-cache, must-revalidate`.
5. `preview_eval`: `fetch('/static/manifest.json').then(r => r.json())` doit retourner le JSON du manifest avec les 2 icônes.
6. `preview_screenshot` pour confirmer qu'aucun bandeau ne s'affiche en usage normal (`hidden` par défaut).
7. Vérifier l'alignement RTL du bandeau : `preview_eval` pour retirer temporairement l'attribut `hidden` du bandeau (`document.getElementById('sw-update-banner').hidden = false`), puis `preview_screenshot` pour confirmer que le texte et le bouton s'alignent correctement en RTL.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html static/css/styles.css
git commit -m "feat: register service worker and show update banner"
```

---

### Task 5 : Documentation README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: rien (documentation uniquement).

- [ ] **Step 1: Ajouter une entrée dans la table des matières**

Dans `README.md`, section `## Table des matières` (ligne 23), ajouter une entrée après celle qui pointe vers `## Rôles et authentification` (avant `## Commandes utiles`), suivant le style existant des autres entrées de la table des matières (lien markdown vers l'ancre de la nouvelle section).

- [ ] **Step 2: Ajouter la section "Service worker & mise à jour automatique"**

Dans `README.md`, insérer une nouvelle section juste avant `## Commandes utiles` (ligne 812) :

```markdown
## Service worker & mise à jour automatique

L'app sert un service worker généré dynamiquement sur `GET /sw.js`
(`sw.py` + route dans `app.py`) — **pas** un fichier statique, car son
contenu doit changer à chaque déploiement pour déclencher la détection de
mise à jour du navigateur.

**Mécanisme :**

1. `version.py` calcule `APP_VERSION` une seule fois au démarrage :
   `git rev-parse --short HEAD`, ou un timestamp si `.git` est absent
   (déploiement sans historique git).
2. `sw.py` génère le script du service worker avec
   `CACHE_NAME = "smiha-static-" + APP_VERSION`. Comme ce nom change à
   chaque commit, le fichier `/sw.js` change d'octets à chaque
   déploiement — c'est ce qui déclenche la vérification native du
   navigateur (`registration.update()` compare le nouveau `/sw.js`
   octet-à-octet).
3. Le service worker ne met en cache **que** les requêtes `GET /static/*`
   (stratégie stale-while-revalidate). Toutes les autres routes (pages
   HTML, `/app/*`, `/admin/*`, `/auth/*`, API) passent toujours en
   direct au réseau — aucune donnée dynamique ou authentifiée n'est
   mise en cache.
4. À l'activation, les anciens caches `smiha-static-*` sont supprimés.
5. Le nouveau service worker reste en état "waiting" tant que
   l'utilisateur n'a pas cliqué sur le bandeau « גרסה חדשה זמינה »
   affiché par le script dans `templates/base.html` — pas de
   rechargement automatique silencieux qui interromprait une session en
   cours (ex. un quiz).

**Règle de maintenance : ne jamais coder en dur un nom de cache
statique.** Le nom est toujours dérivé de `APP_VERSION` — c'est ce
mécanisme qui garantit que chaque déploiement purge le cache des
anciens assets statiques.

**PWA :** `static/manifest.json` + icônes `static/images/icon-192.png`
et `icon-512.png` rendent l'app installable. Les icônes sont générées
depuis le design de `static/favicon.svg` via
`python -m scripts.generate_pwa_icons` (outil de dev, à relancer
uniquement si le design de l'icône change).
```

- [ ] **Step 3: Ajouter la commande de génération d'icônes dans "Commandes utiles"**

Dans `README.md`, section `## Commandes utiles` (bloc bash débutant ligne 815), ajouter après le bloc `# Tests (sans pytest requis)` :

```bash
# Régénérer les icônes PWA après un changement de design du favicon
python -m scripts.generate_pwa_icons
```

- [ ] **Step 4: Vérifier la cohérence**

Relire la nouvelle section et confirmer qu'elle référence des noms de fichiers/fonctions réels : `sw.py`, `version.py`, `APP_VERSION`, `templates/base.html`, `static/manifest.json`, `scripts/generate_pwa_icons`. Confirmer qu'aucune de ces références n'a été renommée pendant l'implémentation des tâches précédentes (`grep -n "APP_VERSION\|render_service_worker" *.py`).

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document the service worker auto-update mechanism"
```
