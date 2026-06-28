"""Flask application factory for the Smiha exam-prep app."""

from __future__ import annotations

from flask import Flask

from config import Config
from models import db
from auth_helpers import current_user


def create_app(config_object: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    db.init_app(app)

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

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}

    with app.app_context():
        db.create_all()

    return app


app = create_app()


if __name__ == "__main__":
    import os
    app.run(debug=True, port=int(os.environ.get("FLASK_PORT", 5000)))
