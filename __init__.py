from __future__ import annotations

import os

from dotenv import load_dotenv
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()

import app.extensions as ext
from app.config import Config
from app.core.fiscal_year_context import (
    get_global_fiscal_year_context,
    hydrate_current_fiscal_year_session,
)
from app.logging_config import configure_logging
from app.routes import register_routes


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def create_app() -> Flask:
    Config.validate()

    flask_app = Flask(__name__)
    flask_app.config.from_object(Config)

    flask_app.config["USE_PROXY_FIX"] = _to_bool(
        os.getenv("USE_PROXY_FIX", flask_app.config.get("USE_PROXY_FIX", False))
    )
    flask_app.config["AUTO_CREATE_TABLES"] = _to_bool(
        os.getenv("AUTO_CREATE_TABLES", flask_app.config.get("AUTO_CREATE_TABLES", False))
    )

    if flask_app.config["USE_PROXY_FIX"]:
        flask_app.wsgi_app = ProxyFix(
            flask_app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
        )

    configure_logging(flask_app)
    flask_app.logger.info(
        "Starting AFYA ERP in %s mode",
        flask_app.config.get("APP_ENV", "development"),
    )

    ext.init_db(flask_app)

    # Register all SQLAlchemy models
    from app import models  # noqa: F401

    if flask_app.config["AUTO_CREATE_TABLES"]:
        flask_app.logger.warning(
            "AUTO_CREATE_TABLES is enabled. Use this only in development/testing."
        )
        ext.create_all_tables()
    else:
        flask_app.logger.info("AUTO_CREATE_TABLES is disabled.")

    @flask_app.before_request
    def _load_fiscal_year_session():
        hydrate_current_fiscal_year_session()

    @flask_app.context_processor
    def inject_fiscal_year_context():
        return get_global_fiscal_year_context()

    @flask_app.context_processor
    def inject_active_path():
        from flask import request
        return {"active_path": request.path}

    # Core routes
    register_routes(flask_app)

    # Optional module route packs
    try:
        from app.student_pack3_routes import register_student_pack3_routes

        register_student_pack3_routes(flask_app)
        flask_app.logger.info("Student Pack 3 routes registered.")
    except Exception as e:
        flask_app.logger.warning("Student Pack 3 routes not registered: %s", e)

    try:
        from app.student_pack4_routes import register_student_pack4_routes

        register_student_pack4_routes(flask_app)
        flask_app.logger.info("Student Pack 4 routes registered.")
    except Exception as e:
        flask_app.logger.warning("Student Pack 4 routes not registered: %s", e)

    try:
        from app.asset_management_routes import register_asset_management_routes

        register_asset_management_routes(flask_app)
        flask_app.logger.info("Asset Management routes registered.")
    except Exception as e:
        flask_app.logger.warning("Asset Management routes not registered: %s", e)

    try:
        from app.nhif_routes import register_nhif_routes

        register_nhif_routes(flask_app)
        flask_app.logger.info("NHIF routes registered.")
    except Exception as e:
        flask_app.logger.warning("NHIF routes not registered: %s", e)

    try:
        from app.facility_routes import register_facility_routes

        register_facility_routes(flask_app)
        flask_app.logger.info("Facilities routes registered.")
    except Exception as e:
        flask_app.logger.warning("Facilities routes not registered: %s", e)

    try:
        from app.report_routes import register_report_routes

        register_report_routes(flask_app)
        flask_app.logger.info("Report routes registered.")
    except Exception as e:
        flask_app.logger.warning("Report routes not registered: %s", e)

    try:
        from app.report_budget_routes import register_budget_report_routes

        register_budget_report_routes(flask_app)
        flask_app.logger.info("Budget report routes registered.")
    except Exception as e:
        flask_app.logger.warning("Budget report routes not registered: %s", e)

    try:
        from app.budget_routes import register_budget_routes

        register_budget_routes(flask_app)
        flask_app.logger.info("Budget routes registered.")
    except Exception as e:
        flask_app.logger.warning("Budget routes not registered: %s", e)

    try:
        from app.report_control_panel_routes import register_report_control_panel_routes

        register_report_control_panel_routes(flask_app)
        flask_app.logger.info("Report control panel routes registered.")
    except Exception as e:
        flask_app.logger.warning("Report control panel routes not registered: %s", e)

    try:
        from app.report_official_print_routes import register_report_official_print_routes

        register_report_official_print_routes(flask_app)
        flask_app.logger.info("Official print report routes registered.")
    except Exception as e:
        flask_app.logger.warning("Official print report routes not registered: %s", e)

    try:
        from app.report_official_screen_routes import register_report_official_screen_routes

        register_report_official_screen_routes(flask_app)
        flask_app.logger.info("Official on-screen report routes registered.")
    except Exception as e:
        flask_app.logger.warning("Official on-screen report routes not registered: %s", e)

    try:
        from app.report_official_remaining_routes import register_report_official_remaining_routes

        register_report_official_remaining_routes(flask_app)
        flask_app.logger.info("Official remaining report routes registered.")
    except Exception as e:
        flask_app.logger.warning("Official remaining report routes not registered: %s", e)

    return flask_app

__all__ = ["create_app", "ext"]