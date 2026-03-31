from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler


def configure_logging(app) -> None:
    log_dir = app.config.get("LOG_DIR", "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_level_name = app.config.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    app_log_path = os.path.join(log_dir, "app.log")
    error_log_path = os.path.join(log_dir, "error.log")

    app_handler = RotatingFileHandler(
        app_log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setLevel(log_level)
    app_handler.setFormatter(formatter)

    error_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    if not getattr(root_logger, "_afya_logging_configured", False):
        root_logger.setLevel(log_level)
        root_logger.addHandler(app_handler)
        root_logger.addHandler(error_handler)
        root_logger._afya_logging_configured = True

    app.logger.setLevel(log_level)
    app.logger.propagate = True
    logging.getLogger("werkzeug").setLevel(log_level)
