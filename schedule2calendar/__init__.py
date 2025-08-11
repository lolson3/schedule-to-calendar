from schedule2calendar.extensions import limiter, csrf, session_ext

from dotenv import load_dotenv
from flask import Flask
from redis import Redis
import os

def create_app():
    load_dotenv()
    from schedule2calendar.config import Config
    app = Flask(__name__)
    app.config.from_object(Config)

    # Redis client
    app.extensions["redis_client"] = Redis.from_url(app.config["RATELIMIT_STORAGE_URI"])
    app.config["SESSION_REDIS"] = app.extensions["redis_client"]

    # Initializes rate limiter
    limiter.init_app(
        app,
        strategy = app.config["RATELIMIT_STRATEGY"],
        default_limits = app.config["RATELIMIT_DEFAULT"],
        storage_uri = app.config["RATELIMIT_STORAGE_URI"],
        storage_options = ["RATELIMIT_STORAGE_OPTIONS"],
    )

    csrf.init_app(app)
    session_ext.init_app(app)

    # Blueprints
    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app
