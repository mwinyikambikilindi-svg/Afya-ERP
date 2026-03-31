from __future__ import annotations

from flask import render_template, request

from app.services.auth_service import login_required, role_required
from app.services.reporting_service import list_fiscal_years
from app.services.budget_reporting_service import get_budget_headers


def register_report_control_panel_routes(flask_app):
    @flask_app.route("/reports/control-panel")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_control_panel():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        budget_headers = []

        try:
            if fiscal_year_id:
                budget_headers = get_budget_headers(fiscal_year_id)
        except Exception:
            budget_headers = []

        return render_template(
            "reports/control_panel.html",
            fiscal_years=list_fiscal_years(),
            budget_headers=budget_headers,
            selected_fiscal_year_id=fiscal_year_id,
        )