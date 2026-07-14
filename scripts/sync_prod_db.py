"""Télécharge la base SQLite de production (PythonAnywhere) et remplace la base locale.

Utilise l'API "Files" de PythonAnywhere (https://www.pythonanywhere.com/api/v0/...),
authentifiée par un token API personnel. Aucune dépendance externe (urllib seul).

Variables d'environnement requises :
    PA_USERNAME    Nom d'utilisateur PythonAnywhere (ex: "bcbeneghmos")
    PA_API_TOKEN   Token API — Account > API Token sur pythonanywhere.com

Variable optionnelle :
    PA_DB_PATH     Chemin absolu du fichier smiha.db sur PythonAnywhere
                   (défaut: /home/<PA_USERNAME>/smiha-flask/smiha.db)

Usage :
    python -m scripts.sync_prod_db
    python -m scripts.sync_prod_db && python app.py
"""
import os
import shutil
import sys
import urllib.error
import urllib.request
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL_DB_PATH = os.path.join(PROJECT_ROOT, "smiha.db")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "db_backups")


def load_dotenv(path):
    """Charge un fichier .env minimal (KEY=value, KEY="value") sans dépendance externe."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def main():
    load_dotenv(ENV_PATH)
    username = os.environ.get("PA_USERNAME")
    token = os.environ.get("PA_API_TOKEN")
    if not username or not token:
        print(
            "Erreur : variables d'environnement PA_USERNAME et PA_API_TOKEN requises.\n"
            "  PowerShell : $env:PA_USERNAME='...'; $env:PA_API_TOKEN='...'\n"
            "  Bash       : export PA_USERNAME=... PA_API_TOKEN=...",
            file=sys.stderr,
        )
        sys.exit(1)

    remote_path = os.environ.get("PA_DB_PATH", f"/home/{username}/smiha-flask/smiha.db")
    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path{remote_path}"

    request = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})

    print(f"Téléchargement de {remote_path} depuis PythonAnywhere...")
    try:
        with urllib.request.urlopen(request) as response:
            data = response.read()
    except urllib.error.HTTPError as e:
        print(f"Erreur HTTP {e.code} lors du téléchargement : {e.reason}", file=sys.stderr)
        if e.code == 404:
            print(f"Vérifiez PA_DB_PATH (chemin testé : {remote_path})", file=sys.stderr)
        elif e.code in (401, 403):
            print("Vérifiez PA_USERNAME et PA_API_TOKEN", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Erreur réseau : {e.reason}", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(LOCAL_DB_PATH):
        os.makedirs(BACKUP_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"smiha-{timestamp}.db")
        shutil.copy2(LOCAL_DB_PATH, backup_path)
        print(f"Ancienne base locale sauvegardée : {backup_path}")

    with open(LOCAL_DB_PATH, "wb") as f:
        f.write(data)

    print(f"Base locale mise à jour : {LOCAL_DB_PATH} ({len(data)} octets)")


if __name__ == "__main__":
    main()
