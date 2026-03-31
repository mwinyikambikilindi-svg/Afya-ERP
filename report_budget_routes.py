from __future__ import annotations
from flask import current_app, render_template, request, send_file
from app.services.auth_service import login_required, role_required
from app.services.budget_reporting_service import (
    export_budget_vs_actual_to_excel,
    get_budget_headers,
    get_budget_vs_actual_statement,
    list_fiscal_years,
)

def register_budget_report_routes(flask_app):
    @flask_app.route("/reports/budget-vs-actual")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_budget_vs_actual():
        error_message = None
        result = None
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        budget_header_id = request.args.get("budget_header_id", type=int)
        try:
            if fiscal_year_id:
                result = get_budget_vs_actual_statement(fiscal_year_id=fiscal_year_id, budget_header_id=budget_header_id)
        except Exception as e:
            current_app.logger.exception("Budget vs Actual report error")
            error_message = str(e)
        return render_template("reports/budget_vs_actual.html", fiscal_years=list_fiscal_years(), budget_headers=get_budget_headers(fiscal_year_id), result=result, error_message=error_message)

    @flask_app.route("/reports/budget-vs-actual/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_budget_vs_actual_print():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        budget_header_id = request.args.get("budget_header_id", type=int)
        result = get_budget_vs_actual_statement(fiscal_year_id=fiscal_year_id, budget_header_id=budget_header_id)
        return render_template("reports/print_budget_vs_actual.html", result=result)

    @flask_app.route("/reports/budget-vs-actual/export.xlsx")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_budget_vs_actual_excel():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        budget_header_id = request.args.get("budget_header_id", type=int)
        result = get_budget_vs_actual_statement(fiscal_year_id=fiscal_year_id, budget_header_id=budget_header_id)
        stream = export_budget_vs_actual_to_excel("Statement of Comparison of Budget and Actual Amounts", result)
        return send_file(stream, as_attachment=True, download_name="budget_vs_actual.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
