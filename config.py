from __future__ import annotations

import os
from datetime import timedelta


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    DEBUG = APP_ENV == "development"
    TESTING = APP_ENV == "testing"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///afya_erp.db")

    SESSION_COOKIE_NAME = os.getenv("SESSION_COOKIE_NAME", "afya_erp_session")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1" or APP_ENV == "production"
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")
    PERMANENT_SESSION_LIFETIME = timedelta(
        minutes=int(os.getenv("SESSION_LIFETIME_MINUTES", "180"))
    )

    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_SAMESITE = SESSION_COOKIE_SAMESITE

    AUTO_CREATE_TABLES = os.getenv(
        "AUTO_CREATE_TABLES",
        "1" if APP_ENV in {"development", "testing"} else "0",
    ) == "1"

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_DIR = os.getenv("LOG_DIR", "logs")
    USE_PROXY_FIX = os.getenv("USE_PROXY_FIX", "0") == "1"
    PREFERRED_URL_SCHEME = os.getenv(
        "PREFERRED_URL_SCHEME",
        "https" if SESSION_COOKIE_SECURE else "http",
    )

    WAITRESS_HOST = os.getenv("WAITRESS_HOST", "127.0.0.1")
    WAITRESS_PORT = int(os.getenv("WAITRESS_PORT", "8000"))
    WAITRESS_THREADS = int(os.getenv("WAITRESS_THREADS", "8"))

    @classmethod
    def validate(cls) -> None:
        if not cls.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is required.")

        if cls.APP_ENV == "production":
            if not cls.SECRET_KEY or cls.SECRET_KEY == "dev-change-me":
                raise RuntimeError(
                    "SECRET_KEY must be set to a strong value in production."
                )
