"""Flask application factory for the Smiha exam-prep app."""

from __future__ import annotations

import os
import subprocess
import time

from flask import Flask, Response, render_template

from config import Config
from models import db
from auth_helpers import current_user


def _compute_app_version() -> str:
    """Short git commit hash, or a startup timestamp if git is unavailable."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(__file__),
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return str(int(time.time()))


APP_VERSION = _compute_app_version()


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

    @app.route("/sw.js")
    def service_worker():
        body = render_template("sw.js.jinja", app_version=APP_VERSION)
        response = Response(body, mimetype="application/javascript")
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response

    @app.template_filter("to_hebrew")
    def to_hebrew(n) -> str:
        """Integer → Hebrew gematria (e.g. 89 → פ״ט, 1 → א׳)."""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return str(n)
        if n <= 0 or n > 900:
            return str(n)
        HUNDREDS = ['', 'ק', 'ר', 'ש', 'ת', 'תק', 'תר', 'תש', 'תת', 'תתק']
        TENS     = ['', 'י', 'כ', 'ל', 'מ', 'נ', 'ס', 'ע', 'פ', 'צ']
        ONES     = ['', 'א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ז', 'ח', 'ט']
        h, n = n // 100, n % 100
        letters = HUNDREDS[h]
        if n == 15:
            letters += 'טו'
        elif n == 16:
            letters += 'טז'
        else:
            if n >= 10:
                letters += TENS[n // 10]
                n %= 10
            if n:
                letters += ONES[n]
        if len(letters) == 1:
            return letters + '׳'
        return letters[:-1] + '״' + letters[-1]

    from blueprints.auth import bp as auth_bp
    from blueprints.student import bp as student_bp
    from blueprints.admin import bp as admin_bp
    from blueprints.api import bp as api_bp
    from blueprints.webhook import bp as webhook_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(webhook_bp)

    @app.context_processor
    def inject_user():
        return {"current_user": current_user(), "app_version": APP_VERSION}

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    import os
    app.run(debug=True, port=int(os.environ.get("FLASK_PORT", 5000)))
