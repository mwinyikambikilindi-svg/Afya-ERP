from __future__ import annotations

from flask import current_app, render_template, request, send_file

from app.services.auth_service import login_required, role_required
from app.services.reporting_service import (
    export_statement_to_excel,
    get_cash_flow_statement,
    get_changes_in_equity,
    get_note_schedule,
    get_notes_index,
    get_prior_fiscal_year_id,
    get_statement,
    get_trial_balance,
    list_fiscal_years,
)
from app.services.pmu_notes_service import (
    get_note_template,
    get_note_title,
    group_note_rows_for_pmu,
)


def register_report_routes(flask_app):
    @flask_app.route("/reports/trial-balance")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_trial_balance():
        error_message = None
        result = None
        try:
            fiscal_year_id = request.args.get("fiscal_year_id", type=int)
            date_from = request.args.get("date_from") or None
            date_to = request.args.get("date_to") or None
            result = get_trial_balance(
                fiscal_year_id=fiscal_year_id,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as e:
            current_app.logger.exception("Trial Balance report error")
            error_message = str(e)

        return render_template(
            "reports/trial_balance.html",
            fiscal_years=list_fiscal_years(),
            result=result,
            error_message=error_message,
        )

    @flask_app.route("/reports/trial-balance/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_trial_balance_print():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        result = get_trial_balance(
            fiscal_year_id=fiscal_year_id,
            date_from=date_from,
            date_to=date_to,
        )
        return render_template("reports/print_trial_balance.html", result=result)

    @flask_app.route("/reports/trial-balance/export.xlsx")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_trial_balance_excel():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        result = get_trial_balance(
            fiscal_year_id=fiscal_year_id,
            date_from=date_from,
            date_to=date_to,
        )
        stream = export_statement_to_excel("Trial Balance", result)
        return send_file(
            stream,
            as_attachment=True,
            download_name="trial_balance.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @flask_app.route("/reports/statement-of-financial-position")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_sofp():
        error_message = None
        result = None
        try:
            fiscal_year_id = request.args.get("fiscal_year_id", type=int)
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
            )
            date_from = request.args.get("date_from") or None
            date_to = request.args.get("date_to") or None
            result = get_statement(
                "SOFP",
                fiscal_year_id=fiscal_year_id,
                prior_fiscal_year_id=prior_fiscal_year_id,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as e:
            current_app.logger.exception("SOFP report error")
            error_message = str(e)

        return render_template(
            "reports/statement_of_financial_position.html",
            fiscal_years=list_fiscal_years(),
            result=result,
            error_message=error_message,
        )

    @flask_app.route("/reports/statement-of-financial-position/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_sofp_print():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        prior_fiscal_year_id = (
            get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
        )
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        result = get_statement(
            "SOFP",
            fiscal_year_id=fiscal_year_id,
            prior_fiscal_year_id=prior_fiscal_year_id,
            date_from=date_from,
            date_to=date_to,
        )
        return render_template(
            "reports/print_statement.html",
            title="Statement of Financial Position",
            result=result,
        )

    @flask_app.route("/reports/statement-of-financial-position/export.xlsx")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_sofp_excel():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        prior_fiscal_year_id = (
            get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
        )
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        result = get_statement(
            "SOFP",
            fiscal_year_id=fiscal_year_id,
            prior_fiscal_year_id=prior_fiscal_year_id,
            date_from=date_from,
            date_to=date_to,
        )
        stream = export_statement_to_excel("Statement of Financial Position", result)
        return send_file(
            stream,
            as_attachment=True,
            download_name="statement_of_financial_position.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @flask_app.route("/reports/statement-of-financial-performance")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_sofperf():
        error_message = None
        result = None
        try:
            fiscal_year_id = request.args.get("fiscal_year_id", type=int)
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
            )
            date_from = request.args.get("date_from") or None
            date_to = request.args.get("date_to") or None
            result = get_statement(
                "SOFPERF",
                fiscal_year_id=fiscal_year_id,
                prior_fiscal_year_id=prior_fiscal_year_id,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as e:
            current_app.logger.exception("SOFPERF report error")
            error_message = str(e)

        return render_template(
            "reports/statement_of_financial_performance.html",
            fiscal_years=list_fiscal_years(),
            result=result,
            error_message=error_message,
        )

    @flask_app.route("/reports/statement-of-financial-performance/print")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_sofperf_print():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        prior_fiscal_year_id = (
            get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
        )
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        result = get_statement(
            "SOFPERF",
            fiscal_year_id=fiscal_year_id,
            prior_fiscal_year_id=prior_fiscal_year_id,
            date_from=date_from,
            date_to=date_to,
        )
        return render_template(
            "reports/print_statement.html",
            title="Statement of Financial Performance",
            result=result,
        )

    @flask_app.route("/reports/statement-of-financial-performance/export.xlsx")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_sofperf_excel():
        fiscal_year_id = request.args.get("fiscal_year_id", type=int)
        prior_fiscal_year_id = (
            get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
        )
        date_from = request.args.get("date_from") or None
        date_to = request.args.get("date_to") or None
        result = get_statement(
            "SOFPERF",
            fiscal_year_id=fiscal_year_id,
            prior_fiscal_year_id=prior_fiscal_year_id,
            date_from=date_from,
            date_to=date_to,
        )
        stream = export_statement_to_excel("Statement of Financial Performance", result)
        return send_file(
            stream,
            as_attachment=True,
            download_name="statement_of_financial_performance.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @flask_app.route("/reports/statement-of-changes-in-equity")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_equity():
        error_message = None
        result = None
        try:
            fiscal_year_id = request.args.get("fiscal_year_id", type=int)
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
            )
            date_from = request.args.get("date_from") or None
            date_to = request.args.get("date_to") or None
            result = get_changes_in_equity(
                fiscal_year_id=fiscal_year_id,
                prior_fiscal_year_id=prior_fiscal_year_id,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as e:
            current_app.logger.exception("Changes in Equity report error")
            error_message = str(e)

        return render_template(
            "reports/statement_of_changes_in_equity.html",
            fiscal_years=list_fiscal_years(),
            result=result,
            error_message=error_message,
        )

    @flask_app.route("/reports/cash-flow-statement")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_cash_flow():
        error_message = None
        result = None
        try:
            date_from = request.args.get("date_from") or None
            date_to = request.args.get("date_to") or None
            result = get_cash_flow_statement(date_from=date_from, date_to=date_to)
        except Exception as e:
            current_app.logger.exception("Cash Flow report error")
            error_message = str(e)

        return render_template(
            "reports/cash_flow_statement.html",
            fiscal_years=list_fiscal_years(),
            result=result,
            error_message=error_message,
        )

    @flask_app.route("/reports/notes")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_notes_index():
        error_message = None
        result = None
        try:
            result = get_notes_index()
        except Exception as e:
            current_app.logger.exception("Notes index report error")
            error_message = str(e)

        return render_template(
            "reports/notes_index.html",
            result=result,
            error_message=error_message,
        )

    @flask_app.route("/reports/notes/<note_no>")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def report_note_detail(note_no: str):
        error_message = None
        result = None
        pmu_note = None
        note_title = f"Note {note_no} Schedule"
        template_name = "reports/note_detail.html"

        try:
            fiscal_year_id = request.args.get("fiscal_year_id", type=int)
            prior_fiscal_year_id = (
                get_prior_fiscal_year_id(fiscal_year_id) if fiscal_year_id else None
            )

            result = get_note_schedule(
                note_no,
                fiscal_year_id=fiscal_year_id,
                prior_fiscal_year_id=prior_fiscal_year_id,
            )

            pmu_note = group_note_rows_for_pmu(note_no, result["rows"])
            note_title = get_note_title(note_no)
            template_name = get_note_template(note_no)

        except Exception as e:
            current_app.logger.exception("Note detail report error")
            error_message = str(e)

        return render_template(
            template_name,
            fiscal_years=list_fiscal_years(),
            result=result,
            pmu_note=pmu_note,
            note_title=note_title,
            error_message=error_message,
        )