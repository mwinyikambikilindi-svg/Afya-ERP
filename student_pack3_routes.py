from __future__ import annotations

from datetime import date

from flask import redirect, render_template, request, session as flask_session, url_for

from app.services.audit_log_service import log_audit_event
from app.services.auth_service import login_required, role_required
from app.services.student_module_service import (
    StudentModuleError,
    get_sponsor_statement,
    get_student_aging_report,
    get_student_collections_dashboard,
    list_sponsor_balances,
    list_student_revenue_runs,
    post_student_revenue_recognition,
    run_student_revenue_recognition,
)


def register_student_pack3_routes(flask_app):
    @flask_app.route("/student-revenue-recognition", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def student_revenue_recognition():
        error_message = None
        if request.method == "POST":
            try:
                as_of_date = request.form.get("as_of_date")
                remarks = request.form.get("remarks")
                action = (request.form.get("action") or "save").strip().lower()
                current_role = (flask_session.get("role_name") or "").strip().upper()
                auto_post = action == "post" and current_role == "ADMIN"
                draft_status = "draft_pending_review" if action == "post" and current_role != "ADMIN" else "draft"

                result = run_student_revenue_recognition(
                    as_of_date=as_of_date,
                    remarks=remarks,
                    auto_post=auto_post,
                    draft_status=draft_status,
                )

                log_audit_event(
                    user_id=flask_session.get("user_id"),
                    module_name="STUDENT_REVENUE_RECOGNITION",
                    record_table="student_revenue_recognition_runs",
                    record_id=result["run_id"],
                    action_name="POST_REVENUE_RECOGNITION" if auto_post else "CREATE_REVENUE_RECOGNITION_RUN",
                    details=f"Student revenue recognition run {result['run_no']} processed",
                )
                status = "posted" if auto_post else draft_status
                return redirect(url_for("student_revenue_recognition", success=result["run_no"], status=status))
            except StudentModuleError as e:
                error_message = str(e)

        runs = list_student_revenue_runs()
        return render_template(
            "student_revenue_recognition.html",
            runs=runs,
            default_as_of_date=date.today().isoformat(),
            success_run_no=request.args.get("success"),
            success_status=request.args.get("status"),
            error_message=error_message,
        )

    @flask_app.route("/student-revenue-recognition/<int:run_id>/post", methods=["POST"])
    @login_required
    @role_required("ADMIN")
    def post_student_revenue_recognition_run(run_id):
        try:
            post_student_revenue_recognition(run_id)
            log_audit_event(
                user_id=flask_session.get("user_id"),
                module_name="STUDENT_REVENUE_RECOGNITION",
                record_table="student_revenue_recognition_runs",
                record_id=run_id,
                action_name="POST_REVENUE_RECOGNITION",
                details=f"Revenue recognition run {run_id} approved and posted",
            )
            return redirect(url_for("student_revenue_recognition"))
        except StudentModuleError as e:
            return redirect(url_for("student_revenue_recognition", error=str(e)))

    @flask_app.route("/student-aging")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def student_aging_report():
        error_message = None
        try:
            as_of_date = request.args.get("as_of_date") or date.today().isoformat()
            result = get_student_aging_report(as_of_date)
            return render_template("student_aging_report.html", result=result, error_message=error_message)
        except StudentModuleError as e:
            error_message = str(e)
            return render_template("student_aging_report.html", result=None, error_message=error_message)

    @flask_app.route("/student-sponsors")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def sponsor_balances():
        rows = list_sponsor_balances()
        return render_template("sponsor_balances.html", rows=rows)

    @flask_app.route("/student-sponsors/statement")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def sponsor_statement():
        sponsor_name = request.args.get("sponsor_name")
        error_message = None
        result = None
        try:
            if sponsor_name:
                result = get_sponsor_statement(sponsor_name)
        except StudentModuleError as e:
            error_message = str(e)
        return render_template("sponsor_statement.html", result=result, sponsor_name=sponsor_name, error_message=error_message)

    @flask_app.route("/student-collections-dashboard")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def student_collections_dashboard():
        error_message = None
        try:
            date_from = request.args.get("date_from") or date.today().replace(day=1).isoformat()
            date_to = request.args.get("date_to") or date.today().isoformat()
            result = get_student_collections_dashboard(date_from, date_to)
            return render_template("student_collections_dashboard.html", result=result, error_message=error_message)
        except StudentModuleError as e:
            error_message = str(e)
            return render_template("student_collections_dashboard.html", result=None, error_message=error_message)
