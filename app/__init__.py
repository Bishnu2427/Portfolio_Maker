from flask import Flask
from app.config import Config
from app.extensions import mongo
from app.routes import register_routes
import os


def create_app(config_class=Config):
    app = Flask(__name__, template_folder='templates', static_folder='static')
    app.config.from_object(config_class)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['GENERATED_PORTFOLIOS_DIR'], exist_ok=True)

    mongo.init_app(app)
    register_routes(app)

    return app
