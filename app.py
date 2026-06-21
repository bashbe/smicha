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
