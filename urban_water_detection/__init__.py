from pathlib import Path

from flask import Flask

from .config import Config
from .routes.api import api_bp
from .routes.main import main_bp


def create_app(config_class: type[Config] = Config) -> Flask:
    package_dir = Path(__file__).resolve().parent
    project_root = package_dir.parent

    app = Flask(
        __name__,
        template_folder=str(project_root / "templates"),
        static_folder=str(project_root / "static"),
        static_url_path="/static",
    )
    app.config.from_object(config_class)

    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    return app
