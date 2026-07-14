"""Webhook GitHub : `git pull` automatique (+ rechargement PythonAnywhere) à chaque push sur main.

PythonAnywhere (plan gratuit) n'autorise aucun processus persistant en dehors du
serveur WSGI de l'app — c'est donc l'app Flask elle-même (toujours active) qui
sert de récepteur de webhook.

# ping de test — vérification du reload via glob *_wsgi.py — à retirer
"""

from __future__ import annotations

import glob
import hashlib
import hmac
import os
import subprocess
import urllib.error
import urllib.request

from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("webhook", __name__, url_prefix="/webhook")

REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _verify_signature(secret: str, payload: bytes, signature_header: str | None) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature_header)


def _reload_pythonanywhere() -> tuple[bool, str]:
    """Rechargement best-effort (no-op si non configuré).

    PythonAnywhere recharge automatiquement une webapp quand son fichier WSGI
    est modifié (mtime) — ce mécanisme fonctionne même sur un compte gratuit,
    contrairement à l'API `/webapps/.../reload/` qui répond 403 "You do not
    have permission to perform this action" sur ces comptes. Le `touch` est
    donc tenté en premier ; l'API reste un fallback (comptes payants, ou si le
    chemin WSGI ne correspond pas à la convention par défaut).

    Le chemin WSGI dérivé du domaine peut être faux si `PYTHONANYWHERE_DOMAIN`
    est mal renseignée — dans ce cas on retombe sur le(s) fichier(s)
    `/var/www/*_wsgi.py` réellement présents (un compte gratuit n'héberge
    qu'une seule webapp, donc un seul candidat).
    """
    username = os.environ.get("PYTHONANYWHERE_USERNAME")
    if not username:
        return False, "reload ignoré (PYTHONANYWHERE_USERNAME non défini)"
    domain = os.environ.get("PYTHONANYWHERE_DOMAIN", f"{username}.pythonanywhere.com")
    resolved = f"username={username!r}, domain={domain!r}"

    candidates = [f"/var/www/{domain.replace('.', '_')}_wsgi.py"]
    candidates += [p for p in sorted(glob.glob("/var/www/*_wsgi.py")) if p not in candidates]
    touch_errors = []
    for wsgi_path in candidates:
        try:
            os.utime(wsgi_path, None)
            return True, f"reload via touch {wsgi_path}"
        except OSError as exc:
            touch_errors.append(f"touch échoué ({wsgi_path}) : {exc}")
    touch_error = f"{' ; '.join(touch_errors)} [{resolved}]"

    token = os.environ.get("PYTHONANYWHERE_API_TOKEN")
    if not token:
        return False, f"{touch_error} — et PYTHONANYWHERE_API_TOKEN non défini pour le fallback API"

    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{domain}/reload/"
    req = urllib.request.Request(url, method="POST", headers={"Authorization": f"Token {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status == 200, f"reload HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        return False, f"{touch_error} — reload API échoué : HTTP {exc.code} {exc.reason} — {body}"
    except urllib.error.URLError as exc:
        return False, f"{touch_error} — reload API échoué : {exc}"


@bp.route("/deploy", methods=["POST"])
def deploy():
    secret = current_app.config.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        return jsonify(error="GITHUB_WEBHOOK_SECRET non configuré côté serveur"), 500

    if not _verify_signature(secret, request.get_data(), request.headers.get("X-Hub-Signature-256")):
        return jsonify(error="signature invalide"), 401

    event = request.headers.get("X-GitHub-Event")
    if event == "ping":
        return jsonify(ok=True, message="pong"), 200
    if event != "push":
        return jsonify(ok=True, ignored=f"événement {event} ignoré"), 200

    payload = request.get_json(silent=True) or {}
    if payload.get("ref") != "refs/heads/main":
        return jsonify(ok=True, ignored=f"ref {payload.get('ref')} ignorée"), 200

    try:
        pull = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "main"],
            cwd=REPO_DIR,
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        return jsonify(ok=False, error="git pull a échoué", stdout=exc.stdout, stderr=exc.stderr), 500
    except subprocess.TimeoutExpired:
        return jsonify(ok=False, error="git pull a expiré (timeout)"), 500

    reloaded, reload_message = _reload_pythonanywhere()
    return jsonify(
        ok=True,
        pull_output=pull.stdout.strip(),
        reloaded=reloaded,
        reload_message=reload_message,
    ), 200
