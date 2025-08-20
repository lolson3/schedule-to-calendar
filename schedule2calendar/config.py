import os
from datetime import timedelta

class Config():

    # Secret keys
    SECRET_KEY = os.getenv("SECRET_KEY")
    WTF_CSRF_SECRET_KEY = os.getenv("WTF_CSRF_SECRET_KEY")

    # Session settings
    SESSION_COOKIE_SECURE = False # Forces HTTPS when True
    SESSION_COOKIE_HTTPONLY = True # Prevents JS from accessing session cookies
    SESSION_COOKIE_SAMESITE = "Lax" # Mitigate CSRF attacks
    SESSION_REFRESH_EACH_REQUEST = True # Extends session expiration
    PERMANENT_SESSION_LIFETIME = timedelta(days = 7)

    # Initializes connection to Redis
    SESSION_TYPE = "redis"
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = "flask_session:"

    REDIS_HOST = os.getenv("REDIS_HOST", "localHost") # Use local host instead of Redis
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") # Add a password if needed
    REDIS_USE_SSL = os.getenv("REDIS_USE_SSL", "false").lower() == "true"
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_SCHEME = "rediss" if REDIS_USE_SSL else "redis"

    # Flask-Limiter (reads these via init_app)
    # Allow direct override via env; otherwise build from parts
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI")
    if not RATELIMIT_STORAGE_URI:
        _SCHEME = "rediss" if REDIS_USE_SSL else "redis"
        _AUTH = f":{REDIS_PASSWORD}@" if REDIS_PASSWORD else ""
        RATELIMIT_STORAGE_URI = f"{_SCHEME}://{_AUTH}{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        
    RATELIMIT_STORAGE_OPTIONS = {"socket_connect_timeout": 30}
    RATELIMIT_STRATEGY = "fixed-window"
    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_HEADERS_ENABLED = True

    # Google OAUTH2
    SCOPES = os.getenv("SCOPES", "").split()
    GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
