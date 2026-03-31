from __future__ import annotations

from flask import current_app, render_template, request

from app.services.auth_service import login_required, role_required
from app.services.official_report_shell_service import build_official_shell_context
from app.services.reporting_service import get_prior_fiscal_year_id, get_statement, get_trial_balance
from app.services.budget_reporting_service import get_budget_headers, get_budget_vs_actual_statement, list_fiscal_years


def _request_scope():
    return {
        "fiscal_year_id": request.args.get("fiscal_year_id", type=int),
        "facility_id": request.args.get("facility_id", type=int),
        "branch_id": request.args.get("branch_id", type=int),
        "date_from": request.args.get("date_from") or None,
        "date_to": request.args.get("date_to") or None,
        "budget_header_id": request.args.get("budget_header_id", type=int),
    }


def register_report_official_screen_routes(flask_app):
    @flask_app.route("/reports/official/trial-balance")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_trial_balance():
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
            current_app.logger.exception("Official on-screen trial balance error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="TRIAL BALANCE",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/trial_balance_official_screen.html",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/statement-of-financial-position")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_statement_of_financial_position():
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
            current_app.logger.exception("Official on-screen SOFP error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF FINANCIAL POSITION",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/statement_official_screen.html",
            title="Statement of Financial Position",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/statement-of-financial-performance")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_statement_of_financial_performance():
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
            current_app.logger.exception("Official on-screen SOFPERF error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF FINANCIAL PERFORMANCE",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/statement_official_screen.html",
            title="Statement of Financial Performance",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/budget-vs-actual")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_budget_vs_actual():
        scope = _request_scope()
        error_message = None
        result = {"sections": [], "grand_budget": 0, "grand_actual": 0, "grand_variance": 0}

        try:
            if scope["fiscal_year_id"]:
                result = get_budget_vs_actual_statement(
                    fiscal_year_id=scope["fiscal_year_id"],
                    budget_header_id=scope["budget_header_id"],
                )
        except Exception as e:
            current_app.logger.exception("Official on-screen Budget vs Actual error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF COMPARISON OF BUDGET AND ACTUAL AMOUNTS",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/budget_vs_actual_official_screen.html",
            result=result,
            shell=shell,
            error_message=error_message,
            fiscal_years=list_fiscal_years(),
            budget_headers=get_budget_headers(scope["fiscal_year_id"]),
            selected_fiscal_year_id=scope["fiscal_year_id"],
            selected_budget_header_id=scope["budget_header_id"],
        )
