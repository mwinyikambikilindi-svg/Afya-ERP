from __future__ import annotations

from flask import current_app, render_template, request

from app.services.auth_service import login_required, role_required
from app.services.official_report_shell_service import build_official_shell_context
from app.services.reporting_service import (
    get_cash_flow_statement,
    get_changes_in_equity,
    get_note_schedule,
    get_notes_index,
    get_prior_fiscal_year_id,
)
from app.services.pmu_notes_service import (
    get_note_template,
    get_note_title,
    group_note_rows_for_pmu,
)


def _request_scope():
    return {
        "fiscal_year_id": request.args.get("fiscal_year_id", type=int),
        "facility_id": request.args.get("facility_id", type=int),
        "branch_id": request.args.get("branch_id", type=int),
        "date_from": request.args.get("date_from") or None,
        "date_to": request.args.get("date_to") or None,
    }


def register_report_official_remaining_routes(flask_app):
    @flask_app.route("/reports/official/notes")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_notes_index():
        scope = _request_scope()
        error_message = None
        result = None

        try:
            result = get_notes_index()
        except Exception as e:
            current_app.logger.exception("Official Notes index error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="NOTES TO THE FINANCIAL STATEMENTS",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/notes_index_official_screen.html",
            result=result,
            shell=shell,
            error_message=error_message,
            fiscal_year_id=scope["fiscal_year_id"],
        )

    @flask_app.route("/reports/official/notes/<note_no>")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_note_detail(note_no: str):
        scope = _request_scope()
        error_message = None
        result = None
        pmu_note = None
        note_title = f"Note {note_no} Schedule"
        template_name = "reports/note_detail.html"

        try:
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(scope["fiscal_year_id"])
                if scope["fiscal_year_id"]
                else None
            )

            result = get_note_schedule(
                note_no,
                fiscal_year_id=scope["fiscal_year_id"],
                prior_fiscal_year_id=prior_fiscal_year_id,
            )

            pmu_note = group_note_rows_for_pmu(note_no, result["rows"])
            note_title = get_note_title(note_no)
            template_name = get_note_template(note_no)

        except Exception as e:
            current_app.logger.exception("Official Note detail error")
            error_message = str(e)

        return render_template(
            template_name,
            fiscal_years=[],
            result=result,
            pmu_note=pmu_note,
            note_title=note_title,
            error_message=error_message,
        )
    
    @flask_app.route("/reports/official/statement-of-changes-in-equity")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_changes_in_equity():
        scope = _request_scope()
        error_message = None
        result = None

        try:
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(scope["fiscal_year_id"])
                if scope["fiscal_year_id"]
                else None
            )
            result = get_changes_in_equity(
                fiscal_year_id=scope["fiscal_year_id"],
                prior_fiscal_year_id=prior_fiscal_year_id,
                date_from=scope["date_from"],
                date_to=scope["date_to"],
            )
        except Exception as e:
            current_app.logger.exception("Official Changes in Equity error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF CHANGES IN EQUITY",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/changes_in_equity_official_screen.html",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/cash-flow-statement")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_cash_flow_statement():
        scope = _request_scope()
        error_message = None
        result = None

        try:
            result = get_cash_flow_statement(
                date_from=scope["date_from"],
                date_to=scope["date_to"],
            )
        except Exception as e:
            current_app.logger.exception("Official Cash Flow error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="CASH FLOW STATEMENT",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/cash_flow_official_screen.html",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/notes/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_notes_index_print():
        scope = _request_scope()
        error_message = None
        result = None

        try:
            result = get_notes_index()
        except Exception as e:
            current_app.logger.exception("Official Notes index print error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="NOTES TO THE FINANCIAL STATEMENTS",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/print_notes_index_official.html",
            title="Notes to the Financial Statements",
            result=result,
            shell=shell,
            error_message=error_message,
            fiscal_year_id=scope["fiscal_year_id"],
        )

    @flask_app.route("/reports/official/notes/<note_no>/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_note_detail_print(note_no: str):
        scope = _request_scope()
        error_message = None
        result = None
        pmu_note = None
        note_title = f"Note {note_no} Schedule"
        template_name = "reports/note_detail.html"

        try:
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(scope["fiscal_year_id"])
                if scope["fiscal_year_id"]
                else None
            )

            result = get_note_schedule(
                note_no,
                fiscal_year_id=scope["fiscal_year_id"],
                prior_fiscal_year_id=prior_fiscal_year_id,
            )

            pmu_note = group_note_rows_for_pmu(note_no, result["rows"])
            note_title = get_note_title(note_no)
            template_name = get_note_template(note_no)

        except Exception as e:
            current_app.logger.exception("Official Note detail print error")
            error_message = str(e)

        return render_template(
            template_name,
            fiscal_years=[],
            result=result,
            pmu_note=pmu_note,
            note_title=note_title,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/statement-of-changes-in-equity/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_changes_in_equity_print():
        scope = _request_scope()
        error_message = None
        result = None

        try:
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(scope["fiscal_year_id"])
                if scope["fiscal_year_id"]
                else None
            )
            result = get_changes_in_equity(
                fiscal_year_id=scope["fiscal_year_id"],
                prior_fiscal_year_id=prior_fiscal_year_id,
                date_from=scope["date_from"],
                date_to=scope["date_to"],
            )
        except Exception as e:
            current_app.logger.exception("Official Changes in Equity print error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="STATEMENT OF CHANGES IN EQUITY",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/print_changes_in_equity_official.html",
            title="Statement of Changes in Equity",
            result=result,
            shell=shell,
            error_message=error_message,
        )

    @flask_app.route("/reports/official/cash-flow-statement/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def official_cash_flow_statement_print():
        scope = _request_scope()
        error_message = None
        result = None

        try:
            result = get_cash_flow_statement(
                date_from=scope["date_from"],
                date_to=scope["date_to"],
            )
        except Exception as e:
            current_app.logger.exception("Official Cash Flow print error")
            error_message = str(e)

        shell = build_official_shell_context(
            report_title="CASH FLOW STATEMENT",
            fiscal_year_id=scope["fiscal_year_id"],
            facility_id=scope["facility_id"],
            branch_id=scope["branch_id"],
        )

        return render_template(
            "reports/print_cash_flow_official.html",
            title="Cash Flow Statement",
            result=result,
            shell=shell,
            error_message=error_message,
        )