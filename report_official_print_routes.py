from __future__ import annotations

from flask import current_app, render_template, request

from app.services.auth_service import login_required, role_required
from app.services.official_report_shell_service import build_official_shell_context
from app.services.reporting_service import get_prior_fiscal_year_id, get_statement, get_trial_balance
from app.services.budget_reporting_service import get_budget_vs_actual_statement


def _request_scope():
    return {
        "fiscal_year_id": request.args.get("fiscal_year_id", type=int),
        "facility_id": request.args.get("facility_id", type=int),
        "branch_id": request.args.get("branch_id", type=int),
        "date_from": request.args.get("date_from") or None,
        "date_to": request.args.get("date_to") or None,
    }


def register_report_official_print_routes(flask_app):
    @flask_app.route("/reports/official/trial-balance/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_trial_balance_print():
        scope = _request_scope()
        error_message = None
        result = {"rows": [], "total_debit": 0, "total_credit": 0}
        try:
            result = get_trial_balance(
                fiscal_year_id=scope["fiscal_year_id"],
                date_from=scope["date_from"],
                date_to=scope["date_to"],
            )
        except Exception as e:
            current_app.logger.exception("Official trial balance print error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="TRIAL BALANCE",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )
        return render_template(
            "reports/print_trial_balance_official.html",
            title="Trial Balance",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/statement-of-financial-position/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_sofp_print():
        scope = _request_scope()
        error_message = None
        result = {"sections": [], "grand_current": 0, "grand_prior": 0}
        try:
            prior_fiscal_year_id = get_prior_fiscal_year_id(scope["fiscal_year_id"]) if scope["fiscal_year_id"] else None
            result = get_statement(
                "SOFP",
                fiscal_year_id=scope["fiscal_year_id"],
                prior_fiscal_year_id=prior_fiscal_year_id,
                date_from=scope["date_from"],
                date_to=scope["date_to"],
            )
        except Exception as e:
            current_app.logger.exception("Official SOFP print error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF FINANCIAL POSITION",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )
        return render_template(
            "reports/print_statement_official.html",
            title="Statement of Financial Position",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/statement-of-financial-performance/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_sofperf_print():
        scope = _request_scope()
        error_message = None
        result = {"sections": [], "grand_current": 0, "grand_prior": 0}
        try:
            prior_fiscal_year_id = get_prior_fiscal_year_id(scope["fiscal_year_id"]) if scope["fiscal_year_id"] else None
            result = get_statement(
                "SOFPERF",
                fiscal_year_id=scope["fiscal_year_id"],
                prior_fiscal_year_id=prior_fiscal_year_id,
                date_from=scope["date_from"],
                date_to=scope["date_to"],
            )
        except Exception as e:
            current_app.logger.exception("Official SOFPERF print error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF FINANCIAL PERFORMANCE",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )
        return render_template(
            "reports/print_statement_official.html",
            title="Statement of Financial Performance",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/budget-vs-actual/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_budget_vs_actual_print():
        scope = _request_scope()
        error_message = None
        result = {"sections": [], "grand_budget": 0, "grand_actual": 0, "grand_variance": 0}
        try:
            result = get_budget_vs_actual_statement(
                fiscal_year_id=scope["fiscal_year_id"],
                budget_header_id=request.args.get("budget_header_id", type=int),
            )
        except Exception as e:
            current_app.logger.exception("Official Budget vs Actual print error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF COMPARISON OF BUDGET AND ACTUAL AMOUNTS",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )
        return render_template(
            "reports/print_budget_vs_actual_official.html",
            title="Statement of Comparison of Budget and Actual Amounts",
            result=result,
            shell=shell,
            error_message=error_message,
        )
