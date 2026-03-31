from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from flask import redirect, render_template, request, session as flask_session, url_for
from sqlalchemy import text
from werkzeug.security import generate_password_hash

import app.extensions as ext
from app.extensions import test_db_connection
from app.models.account_group import AccountGroup
from app.models.branch import Branch
from app.models.fiscal_year import FiscalYear
from app.models.gl_account import GLAccount
from app.models.payer import Payer
from app.models.payer_type import PayerType
from app.models.role import Role
from app.models.supplier import Supplier
from app.models.supplier_category import SupplierCategory
from app.models.user import User
from app.services.student_module_service import (
    StudentModuleError,
    add_fee_structure_line,
    create_academic_year,
    create_fee_item,
    create_fee_structure,
    create_intake,
    create_program,
    create_semester,
    create_student,
    create_student_invoice,
    create_student_payment,
    get_student_statement,
    list_academic_years,
    list_cash_accounts,
    list_fee_items,
    list_fee_structures,
    list_gl_accounts_for_mapping,
    list_intakes,
    list_programs,
    list_semesters,
    list_student_enrollments,
    list_student_invoices,
    list_student_payments,
    list_student_receivables,
    list_students,
    post_student_invoice,
    post_student_payment,
)
from app.services.audit_log_service import list_audit_logs, log_audit_event
from app.services.auth_service import authenticate_user, login_required, role_required
from app.services.cash_payment_query_service import get_cash_payment_detail, list_cash_payments
from app.services.cash_payment_service import CashPaymentServiceError, create_cash_payment
from app.services.cash_receipt_query_service import get_cash_receipt_detail, list_cash_receipts
from app.services.cash_receipt_service import CashReceiptServiceError, create_cash_receipt
from app.services.chart_of_accounts_query_service import list_gl_accounts
from app.services.dashboard_service import get_dashboard_summary
from app.services.income_statement_service import get_income_statement
from app.services.journal_query_service import get_journal_detail, list_journals
from app.services.journal_service import (
    JournalServiceError,
    create_journal_draft,
    post_journal,
    submit_journal_for_approval,
)
from app.services.opening_balance_service import (
    OpeningBalanceError,
    create_opening_balances,
    list_opening_balance_accounts,
    list_opening_balance_history,
)
from app.services.payer_query_service import list_payers
from app.services.period_service import (
    PeriodServiceError,
    change_period_status,
    create_fiscal_year_with_periods,
    list_accounting_periods,
)
from app.services.profile_service import ProfileServiceError, change_user_password, get_user_profile
from app.services.statement_of_financial_position_service import get_statement_of_financial_position
from app.services.supplier_query_service import list_suppliers
from app.services.trial_balance_service import get_trial_balance
from app.services.user_query_service import list_users
from app.services.year_end_closing_query_service import list_year_end_closings
from app.services.year_end_closing_service import YearEndClosingError, run_year_end_closing
from app.services.global_search_service import get_notification_payload, search_global_records

from app.core.fiscal_year_context import get_effective_as_of_date, get_effective_report_range


def register_routes(flask_app):
    @flask_app.route("/")
    @login_required
    def home():
        fy, date_from, date_to = get_effective_report_range()

        summary = get_dashboard_summary(
            date_from=date_from,
            date_to=date_to,
        )

        return render_template(
            "dashboard.html",
            summary=summary,
            full_name=flask_session.get("full_name"),
            role_name=flask_session.get("role_name"),
            branch_name=flask_session.get("branch_name"),
            dashboard_date_from=date_from.isoformat() if date_from else "",
            dashboard_date_to=date_to.isoformat() if date_to else "",
        )

    @flask_app.route("/health")
    def health():
        try:
            test_db_connection()
            return {
                "status": "ok",
                "message": "System is running",
                "database": "connected",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "database": "not connected",
            }, 500

    @flask_app.route("/trial-balance")
    @login_required
    def trial_balance():
        try:
            fy, as_of_date = get_effective_as_of_date(request.args.get("as_of_date"))
            result = get_trial_balance(as_of_date=as_of_date)

            return render_template(
                "trial_balance.html",
                rows=result["rows"],
                total_debit=result["total_debit"],
                total_credit=result["total_credit"],
                is_balanced=result["is_balanced"],
                as_of_date=as_of_date.isoformat() if as_of_date else "",
                error_message=None,
            )
        except ValueError as e:
            return render_template(
                "trial_balance.html",
                rows=[],
                total_debit=0,
                total_credit=0,
                is_balanced=True,
                as_of_date="",
                error_message=str(e),
            )

    @flask_app.route("/manual-journal", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def manual_journal():
        session = ext.SessionLocal()

        try:
            branches = (
                session.query(Branch)
                .filter(Branch.is_active == True)
                .order_by(Branch.code)
                .all()
            )

            accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.account_type == "posting",
                )
                .order_by(GLAccount.code)
                .all()
            )

            if request.method == "POST":
                branch_id_raw = (request.form.get("branch_id") or "").strip()
                journal_date_raw = (request.form.get("journal_date") or "").strip()
                reference_no = (request.form.get("reference_no") or "").strip() or None
                narration = (request.form.get("narration") or "").strip() or None
                action = (request.form.get("action") or "").strip().lower() or "save"

                if action not in {"save", "submit", "post"}:
                    raise JournalServiceError("Action ya journal haijatambulika.")

                if not branch_id_raw:
                    raise JournalServiceError("Chagua branch kwanza.")

                if not journal_date_raw:
                    raise JournalServiceError("Weka journal date.")

                branch_id = int(branch_id_raw)
                journal_date = datetime.strptime(journal_date_raw, "%Y-%m-%d").date()

                raw_account_ids = request.form.getlist("gl_account_id[]")
                raw_descriptions = request.form.getlist("description[]")
                raw_debits = request.form.getlist("debit_amount[]")
                raw_credits = request.form.getlist("credit_amount[]")

                lines = []
                total_rows = max(
                    len(raw_account_ids),
                    len(raw_descriptions),
                    len(raw_debits),
                    len(raw_credits),
                )

                for i in range(total_rows):
                    account_id = raw_account_ids[i].strip() if i < len(raw_account_ids) and raw_account_ids[i] else ""
                    description = raw_descriptions[i].strip() if i < len(raw_descriptions) and raw_descriptions[i] else ""
                    debit_text = raw_debits[i].strip() if i < len(raw_debits) and raw_debits[i] else ""
                    credit_text = raw_credits[i].strip() if i < len(raw_credits) and raw_credits[i] else ""

                    if not account_id and not description and not debit_text and not credit_text:
                        continue

                    if not account_id:
                        raise JournalServiceError("Kila line yenye amount lazima ichague account.")

                    try:
                        debit_amount = Decimal(debit_text) if debit_text else Decimal("0.00")
                        credit_amount = Decimal(credit_text) if credit_text else Decimal("0.00")
                    except InvalidOperation:
                        raise JournalServiceError("Debit au Credit lazima iwe namba sahihi.")

                    lines.append(
                        {
                            "gl_account_id": int(account_id),
                            "description": description or None,
                            "debit_amount": debit_amount,
                            "credit_amount": credit_amount,
                        }
                    )

                batch_id = create_journal_draft(
                    branch_id=branch_id,
                    journal_date=journal_date,
                    source_module="MANUAL_JOURNAL",
                    reference_no=reference_no,
                    narration=narration,
                    lines=lines,
                )

                log_audit_event(
                    user_id=flask_session.get("user_id"),
                    module_name="GENERAL_LEDGER",
                    record_table="journal_batches",
                    record_id=batch_id,
                    action_name="CREATE_JOURNAL",
                    details=f"Manual journal created. Batch ID {batch_id}",
                )

                if action == "save":
                    return redirect(url_for("manual_journal", success=batch_id, status="draft"))

                if action == "submit":
                    submit_journal_for_approval(batch_id)

                    log_audit_event(
                        user_id=flask_session.get("user_id"),
                        module_name="GENERAL_LEDGER",
                        record_table="journal_batches",
                        record_id=batch_id,
                        action_name="SUBMIT_JOURNAL",
                        details=f"Manual journal submitted for approval. Batch ID {batch_id}",
                    )

                    return redirect(url_for("manual_journal", success=batch_id, status="pending_approval"))

                current_role = (flask_session.get("role_name") or "").strip().upper()

                if action == "post":
                    if current_role != "ADMIN":
                        submit_journal_for_approval(batch_id)

                        log_audit_event(
                            user_id=flask_session.get("user_id"),
                            module_name="GENERAL_LEDGER",
                            record_table="journal_batches",
                            record_id=batch_id,
                            action_name="SUBMIT_JOURNAL",
                            details=f"Manual journal submitted for approval by non-admin user. Batch ID {batch_id}",
                        )

                        return redirect(url_for("manual_journal", success=batch_id, status="pending_approval"))

                    submit_journal_for_approval(batch_id)
                    post_journal(batch_id)

                    log_audit_event(
                        user_id=flask_session.get("user_id"),
                        module_name="GENERAL_LEDGER",
                        record_table="journal_batches",
                        record_id=batch_id,
                        action_name="APPROVE_AND_POST_JOURNAL",
                        details=f"Manual journal approved and posted. Batch ID {batch_id}",
                    )

                    return redirect(url_for("manual_journal", success=batch_id, status="posted"))

            return render_template(
                "manual_journal_form.html",
                branches=branches,
                accounts=accounts,
                default_journal_date=date.today().isoformat(),
                success_batch_id=request.args.get("success"),
                success_status=request.args.get("status"),
                error_message=None,
            )

        except (JournalServiceError, ValueError) as e:
            branches = (
                session.query(Branch)
                .filter(Branch.is_active == True)
                .order_by(Branch.code)
                .all()
            )

            accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.account_type == "posting",
                )
                .order_by(GLAccount.code)
                .all()
            )

            return render_template(
                "manual_journal_form.html",
                branches=branches,
                accounts=accounts,
                default_journal_date=date.today().isoformat(),
                success_batch_id=None,
                success_status=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/journals")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def journal_list():
        status = (request.args.get("status") or "").strip() or None
        source_module = (request.args.get("source_module") or "").strip() or None

        result = list_journals(status=status, source_module=source_module)

        return render_template(
            "journal_list.html",
            journals=result["rows"],
            total_rows=result["count"],
            selected_status=status,
            selected_source_module=source_module,
        )

    @flask_app.route("/journals/<int:batch_id>")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def journal_detail(batch_id):
        result = get_journal_detail(batch_id)

        if not result:
            return {"status": "error", "message": "Journal not found"}, 404

        return render_template(
            "journal_detail.html",
            journal=result["header"],
            lines=result["lines"],
            total_debit=result["total_debit"],
            total_credit=result["total_credit"],
            is_balanced=result["is_balanced"],
            error_message=request.args.get("error"),
        )

    @flask_app.route("/journals/<int:batch_id>/submit", methods=["POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def submit_existing_journal(batch_id):
        try:
            submit_journal_for_approval(batch_id)

            log_audit_event(
                user_id=flask_session.get("user_id"),
                module_name="GENERAL_LEDGER",
                record_table="journal_batches",
                record_id=batch_id,
                action_name="SUBMIT_JOURNAL",
                details=f"Existing journal submitted for approval. Batch ID {batch_id}",
            )

            return redirect(url_for("journal_detail", batch_id=batch_id))
        except JournalServiceError as e:
            return redirect(url_for("journal_detail", batch_id=batch_id, error=str(e)))

    @flask_app.route("/journals/<int:batch_id>/post", methods=["POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def post_existing_journal(batch_id):
        current_role = (flask_session.get("role_name") or "").strip().upper()

        try:
            if current_role != "ADMIN":
                raise JournalServiceError("Ni ADMIN tu anayeruhusiwa ku-approve na kupost journal moja kwa moja.")

            post_journal(batch_id)

            log_audit_event(
                user_id=flask_session.get("user_id"),
                module_name="GENERAL_LEDGER",
                record_table="journal_batches",
                record_id=batch_id,
                action_name="POST_JOURNAL",
                details=f"Existing journal posted. Batch ID {batch_id}",
            )

            return redirect(url_for("journal_detail", batch_id=batch_id))
        except JournalServiceError as e:
            return redirect(url_for("journal_detail", batch_id=batch_id, error=str(e)))

    @flask_app.route("/cash-receipts/new", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def cash_receipt_new():
        session = ext.SessionLocal()

        try:
            branches = (
                session.query(Branch)
                .filter(Branch.is_active == True)
                .order_by(Branch.code)
                .all()
            )

            payers = (
                session.query(Payer)
                .filter(Payer.is_active == True)
                .order_by(Payer.name)
                .all()
            )

            cash_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.code.in_(["1110", "1120", "1130"]),
                )
                .order_by(GLAccount.code)
                .all()
            )

            revenue_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.code.like("41%"),
                )
                .order_by(GLAccount.code)
                .all()
            )

            if request.method == "POST":
                branch_id = int((request.form.get("branch_id") or "").strip())
                receipt_date = datetime.strptime(
                    (request.form.get("receipt_date") or "").strip(),
                    "%Y-%m-%d",
                ).date()

                receipt_type = (request.form.get("receipt_type") or "").strip()
                cash_account_id = int((request.form.get("cash_account_id") or "").strip())
                payer_id_raw = (request.form.get("payer_id") or "").strip()
                payer_id = int(payer_id_raw) if payer_id_raw else None
                reference_no = (request.form.get("reference_no") or "").strip() or None
                narration = (request.form.get("narration") or "").strip() or None
                action = (request.form.get("action") or "").strip().lower() or "save"

                if action not in {"save", "post"}:
                    raise CashReceiptServiceError("Action ya cash receipt haijatambulika.")

                raw_revenue_accounts = request.form.getlist("revenue_account_id[]")
                raw_descriptions = request.form.getlist("description[]")
                raw_amounts = request.form.getlist("amount[]")

                lines = []
                total_rows = max(
                    len(raw_revenue_accounts),
                    len(raw_descriptions),
                    len(raw_amounts),
                )

                for i in range(total_rows):
                    revenue_account_id = raw_revenue_accounts[i].strip() if i < len(raw_revenue_accounts) and raw_revenue_accounts[i] else ""
                    description = raw_descriptions[i].strip() if i < len(raw_descriptions) and raw_descriptions[i] else ""
                    amount_text = raw_amounts[i].strip() if i < len(raw_amounts) and raw_amounts[i] else ""

                    if not revenue_account_id and not description and not amount_text:
                        continue

                    if not revenue_account_id:
                        raise CashReceiptServiceError("Chagua revenue account kwenye kila line yenye amount.")

                    lines.append(
                        {
                            "revenue_account_id": int(revenue_account_id),
                            "description": description or None,
                            "amount": amount_text,
                        }
                    )

                current_role = (flask_session.get("role_name") or "").strip().upper()
                direct_post_allowed = current_role == "ADMIN" and action == "post"

                result = create_cash_receipt(
                    branch_id=branch_id,
                    receipt_date=receipt_date,
                    receipt_type=receipt_type,
                    cash_account_id=cash_account_id,
                    reference_no=reference_no,
                    narration=narration,
                    payer_id=payer_id,
                    lines=lines,
                    auto_post=direct_post_allowed,
                )

                if direct_post_allowed:
                    log_audit_event(
                        user_id=flask_session.get("user_id"),
                        module_name="CASH_RECEIPTS",
                        record_table="cash_receipts",
                        record_id=result["receipt_id"],
                        action_name="POST_RECEIPT",
                        details=f"Cash receipt {result['receipt_no']} approved and posted by ADMIN",
                    )
                    return redirect(
                        url_for(
                            "cash_receipt_new",
                            success=result["receipt_no"],
                            status="posted",
                        )
                    )

                if action == "post" and current_role != "ADMIN":
                    log_audit_event(
                        user_id=flask_session.get("user_id"),
                        module_name="CASH_RECEIPTS",
                        record_table="cash_receipts",
                        record_id=result["receipt_id"],
                        action_name="SAVE_RECEIPT_FOR_REVIEW",
                        details=f"Cash receipt {result['receipt_no']} saved as draft for ADMIN review",
                    )
                    return redirect(
                        url_for(
                            "cash_receipt_new",
                            success=result["receipt_no"],
                            status="draft_pending_review",
                        )
                    )

                log_audit_event(
                    user_id=flask_session.get("user_id"),
                    module_name="CASH_RECEIPTS",
                    record_table="cash_receipts",
                    record_id=result["receipt_id"],
                    action_name="CREATE_RECEIPT",
                    details=f"Cash receipt {result['receipt_no']} saved as draft",
                )

                return redirect(
                    url_for(
                        "cash_receipt_new",
                        success=result["receipt_no"],
                        status="draft",
                    )
                )

            return render_template(
                "cash_receipt_form.html",
                branches=branches,
                payers=payers,
                cash_accounts=cash_accounts,
                revenue_accounts=revenue_accounts,
                default_receipt_date=date.today().isoformat(),
                success_receipt_no=request.args.get("success"),
                success_status=request.args.get("status"),
                error_message=None,
            )

        except (CashReceiptServiceError, ValueError) as e:
            branches = (
                session.query(Branch)
                .filter(Branch.is_active == True)
                .order_by(Branch.code)
                .all()
            )

            payers = (
                session.query(Payer)
                .filter(Payer.is_active == True)
                .order_by(Payer.name)
                .all()
            )

            cash_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.code.in_(["1110", "1120", "1130"]),
                )
                .order_by(GLAccount.code)
                .all()
            )

            revenue_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.code.like("41%"),
                )
                .order_by(GLAccount.code)
                .all()
            )

            return render_template(
                "cash_receipt_form.html",
                branches=branches,
                payers=payers,
                cash_accounts=cash_accounts,
                revenue_accounts=revenue_accounts,
                default_receipt_date=date.today().isoformat(),
                success_receipt_no=None,
                success_status=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/cash-receipts")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def cash_receipt_list():
        status = (request.args.get("status") or "").strip() or None
        receipt_type = (request.args.get("receipt_type") or "").strip() or None

        result = list_cash_receipts(status=status, receipt_type=receipt_type)

        return render_template(
            "cash_receipt_list.html",
            receipts=result["rows"],
            total_rows=result["count"],
            selected_status=status,
            selected_receipt_type=receipt_type,
        )

    @flask_app.route("/cash-receipts/<int:receipt_id>")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def cash_receipt_detail(receipt_id):
        result = get_cash_receipt_detail(receipt_id)

        if not result:
            return {"status": "error", "message": "Cash receipt not found"}, 404

        return render_template(
            "cash_receipt_detail.html",
            receipt=result["header"],
            lines=result["lines"],
            journal=result["journal"],
            total_amount=result["total_amount"],
        )

    @flask_app.route("/cash-payments/new", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def cash_payment_new():
        session = ext.SessionLocal()

        try:
            branches = (
                session.query(Branch)
                .filter(Branch.is_active == True)
                .order_by(Branch.code)
                .all()
            )

            suppliers = (
                session.query(Supplier)
                .filter(Supplier.is_active == True)
                .order_by(Supplier.name)
                .all()
            )

            cash_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.code.in_(["1110", "1120", "1130"]),
                )
                .order_by(GLAccount.code)
                .all()
            )

            expense_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    ((GLAccount.code.like("51%")) | (GLAccount.code.like("52%")) | (GLAccount.code.like("53%"))),
                )
                .order_by(GLAccount.code)
                .all()
            )

            if request.method == "POST":
                branch_id = int((request.form.get("branch_id") or "").strip())
                payment_date = datetime.strptime(
                    (request.form.get("payment_date") or "").strip(),
                    "%Y-%m-%d",
                ).date()

                payment_type = (request.form.get("payment_type") or "").strip()
                cash_account_id = int((request.form.get("cash_account_id") or "").strip())
                supplier_id_raw = (request.form.get("supplier_id") or "").strip()
                supplier_id = int(supplier_id_raw) if supplier_id_raw else None
                reference_no = (request.form.get("reference_no") or "").strip() or None
                narration = (request.form.get("narration") or "").strip() or None
                action = (request.form.get("action") or "").strip().lower() or "save"

                if action not in {"save", "post"}:
                    raise CashPaymentServiceError("Action ya cash payment haijatambulika.")

                raw_expense_accounts = request.form.getlist("expense_account_id[]")
                raw_descriptions = request.form.getlist("description[]")
                raw_amounts = request.form.getlist("amount[]")

                lines = []
                total_rows = max(
                    len(raw_expense_accounts),
                    len(raw_descriptions),
                    len(raw_amounts),
                )

                for i in range(total_rows):
                    expense_account_id = raw_expense_accounts[i].strip() if i < len(raw_expense_accounts) and raw_expense_accounts[i] else ""
                    description = raw_descriptions[i].strip() if i < len(raw_descriptions) and raw_descriptions[i] else ""
                    amount_text = raw_amounts[i].strip() if i < len(raw_amounts) and raw_amounts[i] else ""

                    if not expense_account_id and not description and not amount_text:
                        continue

                    if not expense_account_id:
                        raise CashPaymentServiceError("Chagua expense account kwenye kila line yenye amount.")

                    lines.append(
                        {
                            "expense_account_id": int(expense_account_id),
                            "description": description or None,
                            "amount": amount_text,
                        }
                    )

                current_role = (flask_session.get("role_name") or "").strip().upper()
                direct_post_allowed = current_role == "ADMIN" and action == "post"

                result = create_cash_payment(
                    branch_id=branch_id,
                    payment_date=payment_date,
                    payment_type=payment_type,
                    cash_account_id=cash_account_id,
                    reference_no=reference_no,
                    narration=narration,
                    supplier_id=supplier_id,
                    lines=lines,
                    auto_post=direct_post_allowed,
                )

                if direct_post_allowed:
                    log_audit_event(
                        user_id=flask_session.get("user_id"),
                        module_name="CASH_PAYMENTS",
                        record_table="cash_payments",
                        record_id=result["payment_id"],
                        action_name="POST_PAYMENT",
                        details=f"Cash payment {result['payment_no']} approved and posted by ADMIN",
                    )
                    return redirect(
                        url_for(
                            "cash_payment_new",
                            success=result["payment_no"],
                            status="posted",
                        )
                    )

                if action == "post" and current_role != "ADMIN":
                    log_audit_event(
                        user_id=flask_session.get("user_id"),
                        module_name="CASH_PAYMENTS",
                        record_table="cash_payments",
                        record_id=result["payment_id"],
                        action_name="SAVE_PAYMENT_FOR_REVIEW",
                        details=f"Cash payment {result['payment_no']} saved as draft for ADMIN review",
                    )
                    return redirect(
                        url_for(
                            "cash_payment_new",
                            success=result["payment_no"],
                            status="draft_pending_review",
                        )
                    )

                log_audit_event(
                    user_id=flask_session.get("user_id"),
                    module_name="CASH_PAYMENTS",
                    record_table="cash_payments",
                    record_id=result["payment_id"],
                    action_name="CREATE_PAYMENT",
                    details=f"Cash payment {result['payment_no']} saved as draft",
                )

                return redirect(
                    url_for(
                        "cash_payment_new",
                        success=result["payment_no"],
                        status="draft",
                    )
                )

            return render_template(
                "cash_payment_form.html",
                branches=branches,
                suppliers=suppliers,
                cash_accounts=cash_accounts,
                expense_accounts=expense_accounts,
                default_payment_date=date.today().isoformat(),
                success_payment_no=request.args.get("success"),
                success_status=request.args.get("status"),
                error_message=None,
            )

        except (CashPaymentServiceError, ValueError) as e:
            branches = (
                session.query(Branch)
                .filter(Branch.is_active == True)
                .order_by(Branch.code)
                .all()
            )

            suppliers = (
                session.query(Supplier)
                .filter(Supplier.is_active == True)
                .order_by(Supplier.name)
                .all()
            )

            cash_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    GLAccount.code.in_(["1110", "1120", "1130"]),
                )
                .order_by(GLAccount.code)
                .all()
            )

            expense_accounts = (
                session.query(GLAccount)
                .filter(
                    GLAccount.is_active == True,
                    ((GLAccount.code.like("51%")) | (GLAccount.code.like("52%")) | (GLAccount.code.like("53%"))),
                )
                .order_by(GLAccount.code)
                .all()
            )

            return render_template(
                "cash_payment_form.html",
                branches=branches,
                suppliers=suppliers,
                cash_accounts=cash_accounts,
                expense_accounts=expense_accounts,
                default_payment_date=date.today().isoformat(),
                success_payment_no=None,
                success_status=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/cash-payments")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def cash_payment_list():
        status = (request.args.get("status") or "").strip() or None
        payment_type = (request.args.get("payment_type") or "").strip() or None

        result = list_cash_payments(status=status, payment_type=payment_type)

        return render_template(
            "cash_payment_list.html",
            payments=result["rows"],
            total_rows=result["count"],
            selected_status=status,
            selected_payment_type=payment_type,
        )

    @flask_app.route("/cash-payments/<int:payment_id>")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def cash_payment_detail(payment_id):
        result = get_cash_payment_detail(payment_id)

        if not result:
            return {"status": "error", "message": "Cash payment not found"}, 404

        return render_template(
            "cash_payment_detail.html",
            payment=result["header"],
            lines=result["lines"],
            journal=result["journal"],
            total_amount=result["total_amount"],
        )

    @flask_app.route("/payers", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def payer_setup():
        session = ext.SessionLocal()

        try:
            payer_types = (
                session.query(PayerType)
                .filter(PayerType.is_active == True)
                .order_by(PayerType.name)
                .all()
            )

            if request.method == "POST":
                payer_type_id_raw = (request.form.get("payer_type_id") or "").strip()
                code = (request.form.get("code") or "").strip().upper()
                name = (request.form.get("name") or "").strip()
                phone = (request.form.get("phone") or "").strip() or None
                email = (request.form.get("email") or "").strip() or None
                address = (request.form.get("address") or "").strip() or None
                contact_person = (request.form.get("contact_person") or "").strip() or None
                tin = (request.form.get("tin") or "").strip() or None

                if not payer_type_id_raw:
                    raise ValueError("Chagua payer type.")
                if not code:
                    raise ValueError("Weka payer code.")
                if not name:
                    raise ValueError("Weka payer name.")

                existing_code = session.execute(
                    text("SELECT id FROM payers WHERE code = :code"),
                    {"code": code},
                ).fetchone()
                if existing_code:
                    raise ValueError("Payer code tayari ipo.")

                existing_name = session.execute(
                    text("SELECT id FROM payers WHERE name = :name"),
                    {"name": name},
                ).fetchone()
                if existing_name:
                    raise ValueError("Payer name tayari ipo.")

                session.execute(
                    text(
                        """
                        INSERT INTO payers (
                            payer_type_id, code, name, phone, email,
                            address, contact_person, tin, is_active
                        )
                        VALUES (
                            :payer_type_id, :code, :name, :phone, :email,
                            :address, :contact_person, :tin, TRUE
                        )
                        """
                    ),
                    {
                        "payer_type_id": int(payer_type_id_raw),
                        "code": code,
                        "name": name,
                        "phone": phone,
                        "email": email,
                        "address": address,
                        "contact_person": contact_person,
                        "tin": tin,
                    },
                )
                session.commit()
                return redirect("/payers?success=1")

            return render_template(
                "payer_setup.html",
                payer_types=payer_types,
                payers=list_payers(),
                success=request.args.get("success"),
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            payer_types = (
                session.query(PayerType)
                .filter(PayerType.is_active == True)
                .order_by(PayerType.name)
                .all()
            )

            return render_template(
                "payer_setup.html",
                payer_types=payer_types,
                payers=list_payers(),
                success=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/suppliers", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def supplier_setup():
        session = ext.SessionLocal()

        try:
            supplier_categories = (
                session.query(SupplierCategory)
                .filter(SupplierCategory.is_active == True)
                .order_by(SupplierCategory.name)
                .all()
            )

            if request.method == "POST":
                supplier_category_id_raw = (request.form.get("supplier_category_id") or "").strip()
                code = (request.form.get("code") or "").strip().upper()
                name = (request.form.get("name") or "").strip()
                tin = (request.form.get("tin") or "").strip() or None
                vrn = (request.form.get("vrn") or "").strip() or None
                phone = (request.form.get("phone") or "").strip() or None
                email = (request.form.get("email") or "").strip() or None
                address = (request.form.get("address") or "").strip() or None
                contact_person = (request.form.get("contact_person") or "").strip() or None

                if not code:
                    raise ValueError("Weka supplier code.")
                if not name:
                    raise ValueError("Weka supplier name.")

                supplier_category_id = int(supplier_category_id_raw) if supplier_category_id_raw else None

                existing_code = session.execute(
                    text("SELECT id FROM suppliers WHERE code = :code"),
                    {"code": code},
                ).fetchone()
                if existing_code:
                    raise ValueError("Supplier code tayari ipo.")

                existing_name = session.execute(
                    text("SELECT id FROM suppliers WHERE name = :name"),
                    {"name": name},
                ).fetchone()
                if existing_name:
                    raise ValueError("Supplier name tayari ipo.")

                session.execute(
                    text(
                        """
                        INSERT INTO suppliers (
                            supplier_category_id, code, name, tin, vrn,
                            phone, email, address, contact_person, is_active
                        )
                        VALUES (
                            :supplier_category_id, :code, :name, :tin, :vrn,
                            :phone, :email, :address, :contact_person, TRUE
                        )
                        """
                    ),
                    {
                        "supplier_category_id": supplier_category_id,
                        "code": code,
                        "name": name,
                        "tin": tin,
                        "vrn": vrn,
                        "phone": phone,
                        "email": email,
                        "address": address,
                        "contact_person": contact_person,
                    },
                )
                session.commit()
                return redirect("/suppliers?success=1")

            return render_template(
                "supplier_setup.html",
                supplier_categories=supplier_categories,
                suppliers=list_suppliers(),
                success=request.args.get("success"),
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            supplier_categories = (
                session.query(SupplierCategory)
                .filter(SupplierCategory.is_active == True)
                .order_by(SupplierCategory.name)
                .all()
            )

            return render_template(
                "supplier_setup.html",
                supplier_categories=supplier_categories,
                suppliers=list_suppliers(),
                success=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()


    @flask_app.route("/academic-setup", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def academic_setup():
        error_message = None
    
        try:
            if request.method == "POST":
                action = (request.form.get("action") or "").strip()
    
                if action == "create_program":
                    create_program(
                        code=request.form.get("code"),
                        name=request.form.get("name"),
                        award_type=request.form.get("award_type"),
                        duration_in_semesters=request.form.get("duration_in_semesters"),
                        description=request.form.get("description"),
                    )
                    return redirect("/academic-setup?success=program")
    
                if action == "create_academic_year":
                    create_academic_year(
                        code=request.form.get("code"),
                        name=request.form.get("name"),
                        start_date=request.form.get("start_date"),
                        end_date=request.form.get("end_date"),
                    )
                    return redirect("/academic-setup?success=academic_year")
    
                if action == "create_semester":
                    create_semester(
                        academic_year_id=request.form.get("academic_year_id"),
                        code=request.form.get("code"),
                        name=request.form.get("name"),
                        start_date=request.form.get("start_date"),
                        end_date=request.form.get("end_date"),
                    )
                    return redirect("/academic-setup?success=semester")
    
                if action == "create_intake":
                    create_intake(
                        academic_year_id=request.form.get("academic_year_id"),
                        code=request.form.get("code"),
                        name=request.form.get("name"),
                        start_date=request.form.get("start_date"),
                        end_date=request.form.get("end_date"),
                    )
                    return redirect("/academic-setup?success=intake")
    
                raise StudentModuleError("Action ya academic setup haijatambulika.")
    
            return render_template(
                "academic_setup.html",
                programs=list_programs(),
                academic_years=list_academic_years(),
                semesters=list_semesters(),
                intakes=list_intakes(),
                success=request.args.get("success"),
                error_message=error_message,
            )
        except StudentModuleError as e:
            error_message = str(e)
            return render_template(
                "academic_setup.html",
                programs=list_programs(),
                academic_years=list_academic_years(),
                semesters=list_semesters(),
                intakes=list_intakes(),
                success=None,
                error_message=error_message,
            ), 400
    
    @flask_app.route("/students", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def student_setup():
        error_message = None
    
        try:
            if request.method == "POST":
                create_student(
                    student_no=request.form.get("student_no"),
                    admission_no=request.form.get("admission_no"),
                    first_name=request.form.get("first_name"),
                    middle_name=request.form.get("middle_name"),
                    last_name=request.form.get("last_name"),
                    gender=request.form.get("gender"),
                    date_of_birth=request.form.get("date_of_birth"),
                    phone=request.form.get("phone"),
                    email=request.form.get("email"),
                    national_id_no=request.form.get("national_id_no"),
                    sponsor_name=request.form.get("sponsor_name"),
                    guardian_name=request.form.get("guardian_name"),
                    guardian_phone=request.form.get("guardian_phone"),
                    program_id=request.form.get("program_id"),
                    intake_id=request.form.get("intake_id"),
                    current_semester_id=request.form.get("current_semester_id"),
                    admission_date=request.form.get("admission_date"),
                    notes=request.form.get("notes"),
                )
                return redirect("/students?success=1")
    
            return render_template(
                "student_setup.html",
                students=list_students(),
                programs=list_programs(),
                intakes=list_intakes(),
                semesters=list_semesters(),
                success=request.args.get("success"),
                error_message=error_message,
            )
        except StudentModuleError as e:
            error_message = str(e)
            return render_template(
                "student_setup.html",
                students=list_students(),
                programs=list_programs(),
                intakes=list_intakes(),
                semesters=list_semesters(),
                success=None,
                error_message=error_message,
            ), 400
    
    @flask_app.route("/fee-items", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def fee_item_setup():
        error_message = None
    
        try:
            if request.method == "POST":
                create_fee_item(
                    code=request.form.get("code"),
                    name=request.form.get("name"),
                    category=request.form.get("category"),
                    monetary_class=request.form.get("monetary_class"),
                    recognition_basis=request.form.get("recognition_basis"),
                    is_refundable=(request.form.get("is_refundable") == "1"),
                    description=request.form.get("description"),
                    gl_receivable_account_id=request.form.get("gl_receivable_account_id"),
                    gl_deferred_revenue_account_id=request.form.get("gl_deferred_revenue_account_id"),
                    gl_revenue_account_id=request.form.get("gl_revenue_account_id"),
                    gl_discount_account_id=request.form.get("gl_discount_account_id"),
                    gl_refund_account_id=request.form.get("gl_refund_account_id"),
                    gl_ecl_account_id=request.form.get("gl_ecl_account_id"),
                )
                return redirect("/fee-items?success=1")
    
            return render_template(
                "fee_item_setup.html",
                fee_items=list_fee_items(),
                gl_accounts=list_gl_accounts_for_mapping(),
                success=request.args.get("success"),
                error_message=error_message,
            )
        except StudentModuleError as e:
            error_message = str(e)
            return render_template(
                "fee_item_setup.html",
                fee_items=list_fee_items(),
                gl_accounts=list_gl_accounts_for_mapping(),
                success=None,
                error_message=error_message,
            ), 400
    
    @flask_app.route("/fee-structures", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def fee_structure_setup():
        error_message = None
    
        try:
            if request.method == "POST":
                action = (request.form.get("action") or "").strip()
    
                if action == "create_structure":
                    create_fee_structure(
                        code=request.form.get("code"),
                        name=request.form.get("name"),
                        program_id=request.form.get("program_id"),
                        academic_year_id=request.form.get("academic_year_id"),
                        semester_id=request.form.get("semester_id"),
                        intake_id=request.form.get("intake_id"),
                        currency_code=request.form.get("currency_code"),
                        notes=request.form.get("notes"),
                    )
                    return redirect("/fee-structures?success=structure")
    
                if action == "add_line":
                    add_fee_structure_line(
                        fee_structure_id=request.form.get("fee_structure_id"),
                        fee_item_id=request.form.get("fee_item_id"),
                        amount=request.form.get("amount"),
                        mandatory=(request.form.get("mandatory") == "on"),
                        sort_order=request.form.get("sort_order"),
                    )
                    return redirect("/fee-structures?success=line")
    
                raise StudentModuleError("Action ya fee structure haijatambulika.")
    
            return render_template(
                "fee_structure_setup.html",
                fee_structures=list_fee_structures(),
                fee_items=list_fee_items(),
                programs=list_programs(),
                academic_years=list_academic_years(),
                semesters=list_semesters(),
                intakes=list_intakes(),
                success=request.args.get("success"),
                error_message=error_message,
            )
        except StudentModuleError as e:
            error_message = str(e)
            return render_template(
                "fee_structure_setup.html",
                fee_structures=list_fee_structures(),
                fee_items=list_fee_items(),
                programs=list_programs(),
                academic_years=list_academic_years(),
                semesters=list_semesters(),
                intakes=list_intakes(),
                success=None,
                error_message=error_message,
            ), 400


    @flask_app.route("/student-invoices", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def student_invoices():
        error_message = None
        success_message = None
        try:
            if request.method == "POST":
                action = (request.form.get("action") or "save").strip().lower()
                auto_post = flask_session.get("role_name") == "ADMIN" and action == "post"
                draft_status = "draft_pending_review" if action == "post" and flask_session.get("role_name") != "ADMIN" else "draft"
                result = create_student_invoice(
                    enrollment_id=request.form.get("enrollment_id"),
                    invoice_date=request.form.get("invoice_date"),
                    due_date=request.form.get("due_date"),
                    reference_no=request.form.get("reference_no"),
                    remarks=request.form.get("remarks"),
                    auto_post=auto_post,
                    draft_status=draft_status,
                )
                log_audit_event(
                    user_id=flask_session.get("user_id"),
                    module_name="STUDENT_FEES",
                    record_table="student_invoices",
                    record_id=result["invoice_id"],
                    action_name="POST_STUDENT_INVOICE" if auto_post else "CREATE_STUDENT_INVOICE",
                    details=f"Student invoice {result['invoice_no']} processed",
                )
                return redirect(f"/student-invoices?success={result['invoice_no']}")
            if request.args.get("success"):
                success_message = f"Invoice {request.args.get('success')} saved successfully."
            return render_template(
                "student_invoice_setup.html",
                enrollments=list_student_enrollments(),
                invoices=list_student_invoices(),
                default_invoice_date=date.today().isoformat(),
                default_due_date=date.today().isoformat(),
                success_message=success_message,
                error_message=error_message,
            )
        except StudentModuleError as e:
            error_message = str(e)
            return render_template(
                "student_invoice_setup.html",
                enrollments=list_student_enrollments(),
                invoices=list_student_invoices(),
                default_invoice_date=date.today().isoformat(),
                default_due_date=date.today().isoformat(),
                success_message=None,
                error_message=error_message,
            ), 400

    @flask_app.route("/student-invoices/<int:invoice_id>/post", methods=["POST"])
    @login_required
    @role_required("ADMIN")
    def approve_student_invoice(invoice_id):
        try:
            post_student_invoice(invoice_id)
            return redirect("/student-invoices?success=posted")
        except StudentModuleError as e:
            return redirect(f"/student-invoices?error={str(e)}")

    @flask_app.route("/student-payments", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def student_payments():
        error_message = request.args.get("error")
        success_message = None
        try:
            if request.method == "POST":
                action = (request.form.get("action") or "save").strip().lower()
                auto_post = flask_session.get("role_name") == "ADMIN" and action == "post"
                draft_status = "draft_pending_review" if action == "post" and flask_session.get("role_name") != "ADMIN" else "draft"
                result = create_student_payment(
                    student_id=request.form.get("student_id"),
                    cash_account_id=request.form.get("cash_account_id"),
                    payment_date=request.form.get("payment_date"),
                    amount=request.form.get("amount"),
                    reference_no=request.form.get("reference_no"),
                    remarks=request.form.get("remarks"),
                    auto_post=auto_post,
                    draft_status=draft_status,
                )
                log_audit_event(
                    user_id=flask_session.get("user_id"),
                    module_name="STUDENT_FEES",
                    record_table="student_payments",
                    record_id=result["payment_id"],
                    action_name="POST_STUDENT_PAYMENT" if auto_post else "CREATE_STUDENT_PAYMENT",
                    details=f"Student payment {result['payment_no']} processed",
                )
                return redirect(f"/student-payments?success={result['payment_no']}")
            if request.args.get("success"):
                success_message = f"Payment {request.args.get('success')} saved successfully."
            return render_template(
                "student_payment_setup.html",
                students=list_students(),
                cash_accounts=list_cash_accounts(),
                payments=list_student_payments(),
                default_payment_date=date.today().isoformat(),
                success_message=success_message,
                error_message=error_message,
            )
        except StudentModuleError as e:
            error_message = str(e)
            return render_template(
                "student_payment_setup.html",
                students=list_students(),
                cash_accounts=list_cash_accounts(),
                payments=list_student_payments(),
                default_payment_date=date.today().isoformat(),
                success_message=None,
                error_message=error_message,
            ), 400

    @flask_app.route("/student-payments/<int:payment_id>/post", methods=["POST"])
    @login_required
    @role_required("ADMIN")
    def approve_student_payment(payment_id):
        try:
            post_student_payment(payment_id)
            return redirect("/student-payments?success=posted")
        except StudentModuleError as e:
            return redirect(f"/student-payments?error={str(e)}")

    @flask_app.route("/student-receivables")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def student_receivables():
        return render_template("student_receivables.html", receivables=list_student_receivables())

    @flask_app.route("/students/<int:student_id>/statement")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def student_statement(student_id):
        try:
            statement = get_student_statement(student_id)
            return render_template("student_statement.html", statement=statement)
        except StudentModuleError as e:
            return render_template("student_statement.html", statement=None, error_message=str(e)), 400
    
    @flask_app.route("/income-statement")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def income_statement():
        try:
            fy, date_from, date_to = get_effective_report_range(
                request.args.get("date_from"),
                request.args.get("date_to"),
            )

            result = get_income_statement(
                date_from=date_from,
                date_to=date_to,
            )

            return render_template(
                "income_statement.html",
                income_rows=result["income_rows"],
                expense_rows=result["expense_rows"],
                total_income=result["total_income"],
                total_expenses=result["total_expenses"],
                surplus_deficit=result["surplus_deficit"],
                date_from=date_from.isoformat() if date_from else "",
                date_to=date_to.isoformat() if date_to else "",
                error_message=None,
            )
        except ValueError as e:
            return render_template(
                "income_statement.html",
                income_rows=[],
                expense_rows=[],
                total_income=0,
                total_expenses=0,
                surplus_deficit=0,
                date_from="",
                date_to="",
                error_message=str(e),
            )

    @flask_app.route("/statement-of-financial-position")
    @login_required
    @role_required("ADMIN", "ACCOUNTANT", "MANAGER", "AUDITOR")
    def statement_of_financial_position():
        try:
            fy, as_of_date = get_effective_as_of_date(request.args.get("as_of_date"))
            result = get_statement_of_financial_position(as_of_date=as_of_date)

            return render_template(
                "statement_of_financial_position.html",
                asset_rows=result["asset_rows"],
                liability_rows=result["liability_rows"],
                equity_rows=result["equity_rows"],
                total_assets=result["total_assets"],
                total_liabilities=result["total_liabilities"],
                total_equity=result["total_equity"],
                current_period_result=result["current_period_result"],
                total_equity_and_result=result["total_equity_and_result"],
                is_balanced=result["is_balanced"],
                as_of_date=as_of_date.isoformat() if as_of_date else "",
                error_message=None,
            )
        except ValueError as e:
            return render_template(
                "statement_of_financial_position.html",
                asset_rows=[],
                liability_rows=[],
                equity_rows=[],
                total_assets=0,
                total_liabilities=0,
                total_equity=0,
                current_period_result=0,
                total_equity_and_result=0,
                is_balanced=True,
                as_of_date="",
                error_message=str(e),
            )

    @flask_app.route("/gl-accounts", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def gl_account_setup():
        session = ext.SessionLocal()

        try:
            account_groups = session.query(AccountGroup).order_by(AccountGroup.code).all()

            if request.method == "POST":
                account_group_id_raw = (request.form.get("account_group_id") or "").strip()
                code = (request.form.get("code") or "").strip()
                name = (request.form.get("name") or "").strip()
                account_type = (request.form.get("account_type") or "").strip() or "posting"

                allow_manual_posting = request.form.get("allow_manual_posting") == "on"
                requires_subledger = request.form.get("requires_subledger") == "on"
                requires_cost_center = request.form.get("requires_cost_center") == "on"
                requires_department = request.form.get("requires_department") == "on"
                is_control_account = request.form.get("is_control_account") == "on"
                is_active = request.form.get("is_active") == "on"

                if not account_group_id_raw:
                    raise ValueError("Chagua account group.")
                if not code:
                    raise ValueError("Weka account code.")
                if not name:
                    raise ValueError("Weka account name.")

                existing_code = session.execute(
                    text("SELECT id FROM gl_accounts WHERE code = :code"),
                    {"code": code},
                ).fetchone()
                if existing_code:
                    raise ValueError("Account code tayari ipo.")

                existing_name = session.execute(
                    text("SELECT id FROM gl_accounts WHERE name = :name"),
                    {"name": name},
                ).fetchone()
                if existing_name:
                    raise ValueError("Account name tayari ipo.")

                session.execute(
                    text(
                        """
                        INSERT INTO gl_accounts (
                            account_group_id,
                            parent_id,
                            code,
                            name,
                            account_type,
                            allow_manual_posting,
                            requires_subledger,
                            requires_cost_center,
                            requires_department,
                            is_control_account,
                            is_active
                        )
                        VALUES (
                            :account_group_id,
                            NULL,
                            :code,
                            :name,
                            :account_type,
                            :allow_manual_posting,
                            :requires_subledger,
                            :requires_cost_center,
                            :requires_department,
                            :is_control_account,
                            :is_active
                        )
                        """
                    ),
                    {
                        "account_group_id": int(account_group_id_raw),
                        "code": code,
                        "name": name,
                        "account_type": account_type,
                        "allow_manual_posting": allow_manual_posting,
                        "requires_subledger": requires_subledger,
                        "requires_cost_center": requires_cost_center,
                        "requires_department": requires_department,
                        "is_control_account": is_control_account,
                        "is_active": is_active,
                    },
                )
                session.commit()
                return redirect("/gl-accounts?success=1")

            return render_template(
                "gl_account_setup.html",
                account_groups=account_groups,
                accounts=list_gl_accounts(),
                success=request.args.get("success"),
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            account_groups = session.query(AccountGroup).order_by(AccountGroup.code).all()
            return render_template(
                "gl_account_setup.html",
                account_groups=account_groups,
                accounts=list_gl_accounts(),
                success=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/year-end-closing", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def year_end_closing():
        session = ext.SessionLocal()

        try:
            fiscal_years = session.query(FiscalYear).order_by(FiscalYear.start_date.desc()).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            retained_accounts = session.query(GLAccount).filter(GLAccount.code == "3120").order_by(GLAccount.code).all()

            if request.method == "POST":
                fiscal_year_id = int((request.form.get("fiscal_year_id") or "").strip())
                branch_id = int((request.form.get("branch_id") or "").strip())
                retained_surplus_account_id = int((request.form.get("retained_surplus_account_id") or "").strip())
                closing_date = datetime.strptime(
                    (request.form.get("closing_date") or "").strip(),
                    "%Y-%m-%d",
                ).date()
                remarks = (request.form.get("remarks") or "").strip() or None

                result = run_year_end_closing(
                    fiscal_year_id=fiscal_year_id,
                    closing_date=closing_date,
                    retained_surplus_account_id=retained_surplus_account_id,
                    branch_id=branch_id,
                    remarks=remarks,
                )

                return redirect(f"/year-end-closing?success=1&batch_id={result['closing_journal_batch_id']}")

            return render_template(
                "year_end_closing.html",
                fiscal_years=fiscal_years,
                branches=branches,
                retained_accounts=retained_accounts,
                closings=list_year_end_closings(),
                success=request.args.get("success"),
                batch_id=request.args.get("batch_id"),
                error_message=None,
            )

        except (ValueError, YearEndClosingError) as e:
            session.rollback()
            fiscal_years = session.query(FiscalYear).order_by(FiscalYear.start_date.desc()).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            retained_accounts = session.query(GLAccount).filter(GLAccount.code == "3120").order_by(GLAccount.code).all()
            return render_template(
                "year_end_closing.html",
                fiscal_years=fiscal_years,
                branches=branches,
                retained_accounts=retained_accounts,
                closings=list_year_end_closings(),
                success=None,
                batch_id=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/periods", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def period_setup():
        session = ext.SessionLocal()

        try:
            fiscal_years = session.query(FiscalYear).order_by(FiscalYear.start_date.desc()).all()

            if request.method == "POST":
                action = (request.form.get("action") or "").strip()

                if action == "create_fiscal_year":
                    create_fiscal_year_with_periods(
                        year_name=(request.form.get("year_name") or "").strip(),
                        start_date=(request.form.get("start_date") or "").strip(),
                        end_date=(request.form.get("end_date") or "").strip(),
                    )
                    return redirect("/periods?success=fiscal_year_created")

                if action == "close_period":
                    change_period_status(int((request.form.get("period_id") or "").strip()), "closed")
                    return redirect("/periods?success=period_closed")

                if action == "reopen_period":
                    change_period_status(int((request.form.get("period_id") or "").strip()), "open")
                    return redirect("/periods?success=period_reopened")

                raise PeriodServiceError("Action ya period haijatambulika.")

            return render_template(
                "period_setup.html",
                fiscal_years=fiscal_years,
                periods=list_accounting_periods(),
                success=request.args.get("success"),
                error_message=None,
            )

        except (ValueError, PeriodServiceError) as e:
            session.rollback()
            fiscal_years = session.query(FiscalYear).order_by(FiscalYear.start_date.desc()).all()
            return render_template(
                "period_setup.html",
                fiscal_years=fiscal_years,
                periods=list_accounting_periods(),
                success=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/opening-balances", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def opening_balances():
        session = ext.SessionLocal()

        try:
            fiscal_years = session.query(FiscalYear).order_by(FiscalYear.start_date.desc()).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            accounts = list_opening_balance_accounts()

            if request.method == "POST":
                fiscal_year_id = int((request.form.get("fiscal_year_id") or "").strip())
                branch_id = int((request.form.get("branch_id") or "").strip())
                opening_date = datetime.strptime(
                    (request.form.get("opening_date") or "").strip(),
                    "%Y-%m-%d",
                ).date()
                remarks = (request.form.get("remarks") or "").strip() or None

                raw_account_ids = request.form.getlist("gl_account_id[]")
                raw_descriptions = request.form.getlist("description[]")
                raw_debits = request.form.getlist("debit_amount[]")
                raw_credits = request.form.getlist("credit_amount[]")

                lines = []
                total_rows = max(
                    len(raw_account_ids),
                    len(raw_descriptions),
                    len(raw_debits),
                    len(raw_credits),
                )

                for i in range(total_rows):
                    account_id = raw_account_ids[i].strip() if i < len(raw_account_ids) and raw_account_ids[i] else ""
                    description = raw_descriptions[i].strip() if i < len(raw_descriptions) and raw_descriptions[i] else ""
                    debit_text = raw_debits[i].strip() if i < len(raw_debits) and raw_debits[i] else ""
                    credit_text = raw_credits[i].strip() if i < len(raw_credits) and raw_credits[i] else ""

                    if not account_id and not description and not debit_text and not credit_text:
                        continue

                    if not account_id:
                        raise OpeningBalanceError("Chagua account kwenye kila line yenye amount.")

                    lines.append(
                        {
                            "gl_account_id": int(account_id),
                            "description": description or None,
                            "debit_amount": Decimal(debit_text) if debit_text else Decimal("0.00"),
                            "credit_amount": Decimal(credit_text) if credit_text else Decimal("0.00"),
                        }
                    )

                batch_id = create_opening_balances(
                    fiscal_year_id=fiscal_year_id,
                    branch_id=branch_id,
                    opening_date=opening_date,
                    remarks=remarks,
                    lines=lines,
                )

                return redirect(f"/opening-balances?success=1&batch_id={batch_id}")

            return render_template(
                "opening_balances.html",
                fiscal_years=fiscal_years,
                branches=branches,
                accounts=accounts,
                history=list_opening_balance_history(),
                success=request.args.get("success"),
                batch_id=request.args.get("batch_id"),
                error_message=None,
            )

        except (ValueError, OpeningBalanceError) as e:
            session.rollback()
            fiscal_years = session.query(FiscalYear).order_by(FiscalYear.start_date.desc()).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            return render_template(
                "opening_balances.html",
                fiscal_years=fiscal_years,
                branches=branches,
                accounts=list_opening_balance_accounts(),
                history=list_opening_balance_history(),
                success=None,
                batch_id=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""

            user = authenticate_user(username, password)
            if not user:
                return render_template("login.html", error_message="Username au password si sahihi.")

            flask_session["user_id"] = user["id"]
            flask_session["username"] = user["username"]
            flask_session["full_name"] = user["full_name"]
            flask_session["role_name"] = user["role_name"]
            flask_session["branch_code"] = user["branch_code"]
            flask_session["branch_name"] = user["branch_name"]

            log_audit_event(
                user_id=user["id"],
                module_name="AUTH",
                record_table="users",
                record_id=user["id"],
                action_name="LOGIN",
                details=f"User {user['username']} logged in",
            )

            return redirect(url_for("home"))

        return render_template("login.html", error_message=None)

    @flask_app.route("/logout")
    def logout():
        user_id = flask_session.get("user_id")
        username = flask_session.get("username")

        if user_id:
            log_audit_event(
                user_id=user_id,
                module_name="AUTH",
                record_table="users",
                record_id=user_id,
                action_name="LOGOUT",
                details=f"User {username} logged out",
            )

        flask_session.clear()
        return redirect(url_for("login"))

    @flask_app.route("/audit-logs")
    @login_required
    @role_required("ADMIN")
    def audit_logs():
        return render_template("audit_logs.html", logs=list_audit_logs())

    @flask_app.route("/users", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def user_setup():
        session = ext.SessionLocal()

        try:
            roles = session.query(Role).filter(Role.is_active == True).order_by(Role.name).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()

            if request.method == "POST":
                action = (request.form.get("action") or "").strip()

                if action == "create_user":
                    full_name = (request.form.get("full_name") or "").strip()
                    username = (request.form.get("username") or "").strip()
                    email = (request.form.get("email") or "").strip() or None
                    phone = (request.form.get("phone") or "").strip() or None
                    password = request.form.get("password") or ""
                    role_id_raw = (request.form.get("role_id") or "").strip()
                    branch_id_raw = (request.form.get("branch_id") or "").strip()

                    if not full_name:
                        raise ValueError("Weka full name.")
                    if not username:
                        raise ValueError("Weka username.")
                    if not password:
                        raise ValueError("Weka password.")
                    if not role_id_raw:
                        raise ValueError("Chagua role.")

                    existing_username = session.execute(
                        text("SELECT id FROM users WHERE username = :username"),
                        {"username": username},
                    ).fetchone()
                    if existing_username:
                        raise ValueError("Username tayari ipo.")

                    branch_id = int(branch_id_raw) if branch_id_raw else None

                    session.execute(
                        text(
                            """
                            INSERT INTO users (
                                full_name,
                                username,
                                email,
                                phone,
                                password_hash,
                                role_id,
                                branch_id,
                                is_active
                            )
                            VALUES (
                                :full_name,
                                :username,
                                :email,
                                :phone,
                                :password_hash,
                                :role_id,
                                :branch_id,
                                TRUE
                            )
                            """
                        ),
                        {
                            "full_name": full_name,
                            "username": username,
                            "email": email,
                            "phone": phone,
                            "password_hash": generate_password_hash(password),
                            "role_id": int(role_id_raw),
                            "branch_id": branch_id,
                        },
                    )
                    session.commit()
                    return redirect("/users?success=user_created")

                if action == "toggle_status":
                    user_id = int((request.form.get("user_id") or "").strip())
                    user = session.get(User, user_id)
                    if not user:
                        raise ValueError("User haipo.")

                    user.is_active = not user.is_active
                    session.commit()
                    return redirect("/users?success=status_changed")

                raise ValueError("Action ya user haijatambulika.")

            return render_template(
                "user_setup.html",
                roles=roles,
                branches=branches,
                users=list_users(),
                success=request.args.get("success"),
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            roles = session.query(Role).filter(Role.is_active == True).order_by(Role.name).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            return render_template(
                "user_setup.html",
                roles=roles,
                branches=branches,
                users=list_users(),
                success=None,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/profile", methods=["GET", "POST"])
    @login_required
    def profile():
        user_id = flask_session.get("user_id")
        if not user_id:
            return redirect(url_for("login"))

        try:
            if request.method == "POST":
                action = (request.form.get("action") or "").strip()

                if action == "change_password":
                    change_user_password(
                        user_id=user_id,
                        current_password=request.form.get("current_password") or "",
                        new_password=request.form.get("new_password") or "",
                        confirm_password=request.form.get("confirm_password") or "",
                    )
                    return redirect("/profile?success=password_changed")

                raise ProfileServiceError("Action ya profile haijatambulika.")

            return render_template(
                "profile.html",
                profile_data=get_user_profile(user_id),
                success=request.args.get("success"),
                error_message=None,
            )
        except ProfileServiceError as e:
            return render_template(
                "profile.html",
                profile_data=get_user_profile(user_id),
                success=None,
                error_message=str(e),
            ), 400

    @flask_app.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def edit_user(user_id):
        session = ext.SessionLocal()

        try:
            user = session.get(User, user_id)
            if not user:
                return {"status": "error", "message": "User not found"}, 404

            roles = session.query(Role).filter(Role.is_active == True).order_by(Role.name).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()

            if request.method == "POST":
                full_name = (request.form.get("full_name") or "").strip()
                email = (request.form.get("email") or "").strip() or None
                phone = (request.form.get("phone") or "").strip() or None
                role_id_raw = (request.form.get("role_id") or "").strip()
                branch_id_raw = (request.form.get("branch_id") or "").strip()
                is_active = request.form.get("is_active") == "on"

                if not full_name:
                    raise ValueError("Weka full name.")
                if not role_id_raw:
                    raise ValueError("Chagua role.")

                user.full_name = full_name
                user.email = email
                user.phone = phone
                user.role_id = int(role_id_raw)
                user.branch_id = int(branch_id_raw) if branch_id_raw else None
                user.is_active = is_active

                session.commit()
                return redirect("/users?success=user_updated")

            return render_template(
                "user_edit.html",
                user=user,
                roles=roles,
                branches=branches,
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            roles = session.query(Role).filter(Role.is_active == True).order_by(Role.name).all()
            branches = session.query(Branch).filter(Branch.is_active == True).order_by(Branch.code).all()
            return render_template(
                "user_edit.html",
                user=user,
                roles=roles,
                branches=branches,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/users/<int:user_id>/reset-password", methods=["POST"])
    @login_required
    @role_required("ADMIN")
    def reset_user_password(user_id):
        session = ext.SessionLocal()

        try:
            user = session.get(User, user_id)
            if not user:
                return {"status": "error", "message": "User not found"}, 404

            new_password = (request.form.get("new_password") or "").strip()
            if not new_password:
                raise ValueError("Weka new password.")
            if len(new_password) < 8:
                raise ValueError("Password mpya lazima iwe na angalau characters 8.")

            user.password_hash = generate_password_hash(new_password)
            session.commit()
            return redirect("/users?success=password_reset")

        except ValueError as e:
            session.rollback()
            return redirect(f"/users?error={str(e)}")

        finally:
            session.close()

    @flask_app.route("/payers/<int:payer_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def edit_payer(payer_id):
        session = ext.SessionLocal()

        try:
            payer = session.get(Payer, payer_id)
            if not payer:
                return {"status": "error", "message": "Payer not found"}, 404

            payer_types = session.query(PayerType).filter(PayerType.is_active == True).order_by(PayerType.name).all()

            if request.method == "POST":
                payer_type_id_raw = (request.form.get("payer_type_id") or "").strip()
                code = (request.form.get("code") or "").strip().upper()
                name = (request.form.get("name") or "").strip()
                phone = (request.form.get("phone") or "").strip() or None
                email = (request.form.get("email") or "").strip() or None
                address = (request.form.get("address") or "").strip() or None
                contact_person = (request.form.get("contact_person") or "").strip() or None
                tin = (request.form.get("tin") or "").strip() or None
                is_active = request.form.get("is_active") == "on"

                if not payer_type_id_raw:
                    raise ValueError("Chagua payer type.")
                if not code:
                    raise ValueError("Weka payer code.")
                if not name:
                    raise ValueError("Weka payer name.")

                existing_code = session.execute(
                    text("SELECT id FROM payers WHERE code = :code AND id <> :id"),
                    {"code": code, "id": payer.id},
                ).fetchone()
                if existing_code:
                    raise ValueError("Payer code tayari ipo.")

                existing_name = session.execute(
                    text("SELECT id FROM payers WHERE name = :name AND id <> :id"),
                    {"name": name, "id": payer.id},
                ).fetchone()
                if existing_name:
                    raise ValueError("Payer name tayari ipo.")

                payer.payer_type_id = int(payer_type_id_raw)
                payer.code = code
                payer.name = name
                payer.phone = phone
                payer.email = email
                payer.address = address
                payer.contact_person = contact_person
                payer.tin = tin
                payer.is_active = is_active

                session.commit()
                return redirect("/payers?success=payer_updated")

            return render_template(
                "payer_edit.html",
                payer=payer,
                payer_types=payer_types,
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            payer_types = session.query(PayerType).filter(PayerType.is_active == True).order_by(PayerType.name).all()
            return render_template(
                "payer_edit.html",
                payer=payer,
                payer_types=payer_types,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/payers/<int:payer_id>/toggle-status", methods=["POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def toggle_payer_status(payer_id):
        session = ext.SessionLocal()
        try:
            payer = session.get(Payer, payer_id)
            if not payer:
                return {"status": "error", "message": "Payer not found"}, 404
            payer.is_active = not payer.is_active
            session.commit()
            return redirect("/payers?success=status_changed")
        finally:
            session.close()

    @flask_app.route("/suppliers/<int:supplier_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def edit_supplier(supplier_id):
        session = ext.SessionLocal()

        try:
            supplier = session.get(Supplier, supplier_id)
            if not supplier:
                return {"status": "error", "message": "Supplier not found"}, 404

            supplier_categories = session.query(SupplierCategory).filter(SupplierCategory.is_active == True).order_by(SupplierCategory.name).all()

            if request.method == "POST":
                supplier_category_id_raw = (request.form.get("supplier_category_id") or "").strip()
                code = (request.form.get("code") or "").strip().upper()
                name = (request.form.get("name") or "").strip()
                tin = (request.form.get("tin") or "").strip() or None
                vrn = (request.form.get("vrn") or "").strip() or None
                phone = (request.form.get("phone") or "").strip() or None
                email = (request.form.get("email") or "").strip() or None
                address = (request.form.get("address") or "").strip() or None
                contact_person = (request.form.get("contact_person") or "").strip() or None
                is_active = request.form.get("is_active") == "on"

                if not code:
                    raise ValueError("Weka supplier code.")
                if not name:
                    raise ValueError("Weka supplier name.")

                supplier_category_id = int(supplier_category_id_raw) if supplier_category_id_raw else None

                existing_code = session.execute(
                    text("SELECT id FROM suppliers WHERE code = :code AND id <> :id"),
                    {"code": code, "id": supplier.id},
                ).fetchone()
                if existing_code:
                    raise ValueError("Supplier code tayari ipo.")

                existing_name = session.execute(
                    text("SELECT id FROM suppliers WHERE name = :name AND id <> :id"),
                    {"name": name, "id": supplier.id},
                ).fetchone()
                if existing_name:
                    raise ValueError("Supplier name tayari ipo.")

                supplier.supplier_category_id = supplier_category_id
                supplier.code = code
                supplier.name = name
                supplier.tin = tin
                supplier.vrn = vrn
                supplier.phone = phone
                supplier.email = email
                supplier.address = address
                supplier.contact_person = contact_person
                supplier.is_active = is_active

                session.commit()
                return redirect("/suppliers?success=supplier_updated")

            return render_template(
                "supplier_edit.html",
                supplier=supplier,
                supplier_categories=supplier_categories,
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            supplier_categories = session.query(SupplierCategory).filter(SupplierCategory.is_active == True).order_by(SupplierCategory.name).all()
            return render_template(
                "supplier_edit.html",
                supplier=supplier,
                supplier_categories=supplier_categories,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/suppliers/<int:supplier_id>/toggle-status", methods=["POST"])
    @login_required
    @role_required("ADMIN", "ACCOUNTANT")
    def toggle_supplier_status(supplier_id):
        session = ext.SessionLocal()
        try:
            supplier = session.get(Supplier, supplier_id)
            if not supplier:
                return {"status": "error", "message": "Supplier not found"}, 404
            supplier.is_active = not supplier.is_active
            session.commit()
            return redirect("/suppliers?success=status_changed")
        finally:
            session.close()

    @flask_app.route("/gl-accounts/<int:account_id>/edit", methods=["GET", "POST"])
    @login_required
    @role_required("ADMIN")
    def edit_gl_account(account_id):
        session = ext.SessionLocal()

        try:
            account = session.get(GLAccount, account_id)
            if not account:
                return {"status": "error", "message": "GL account not found"}, 404

            account_groups = session.query(AccountGroup).order_by(AccountGroup.code).all()

            if request.method == "POST":
                account_group_id_raw = (request.form.get("account_group_id") or "").strip()
                code = (request.form.get("code") or "").strip()
                name = (request.form.get("name") or "").strip()
                account_type = (request.form.get("account_type") or "").strip() or "posting"

                allow_manual_posting = request.form.get("allow_manual_posting") == "on"
                requires_subledger = request.form.get("requires_subledger") == "on"
                requires_cost_center = request.form.get("requires_cost_center") == "on"
                requires_department = request.form.get("requires_department") == "on"
                is_control_account = request.form.get("is_control_account") == "on"
                is_active = request.form.get("is_active") == "on"

                if not account_group_id_raw:
                    raise ValueError("Chagua account group.")
                if not code:
                    raise ValueError("Weka account code.")
                if not name:
                    raise ValueError("Weka account name.")

                existing_code = session.execute(
                    text("SELECT id FROM gl_accounts WHERE code = :code AND id <> :id"),
                    {"code": code, "id": account.id},
                ).fetchone()
                if existing_code:
                    raise ValueError("Account code tayari ipo.")

                existing_name = session.execute(
                    text("SELECT id FROM gl_accounts WHERE name = :name AND id <> :id"),
                    {"name": name, "id": account.id},
                ).fetchone()
                if existing_name:
                    raise ValueError("Account name tayari ipo.")

                account.account_group_id = int(account_group_id_raw)
                account.code = code
                account.name = name
                account.account_type = account_type
                account.allow_manual_posting = allow_manual_posting
                account.requires_subledger = requires_subledger
                account.requires_cost_center = requires_cost_center
                account.requires_department = requires_department
                account.is_control_account = is_control_account
                account.is_active = is_active

                session.commit()
                return redirect("/gl-accounts?success=account_updated")

            return render_template(
                "gl_account_edit.html",
                account=account,
                account_groups=account_groups,
                error_message=None,
            )

        except ValueError as e:
            session.rollback()
            account_groups = session.query(AccountGroup).order_by(AccountGroup.code).all()
            return render_template(
                "gl_account_edit.html",
                account=account,
                account_groups=account_groups,
                error_message=str(e),
            ), 400

        finally:
            session.close()

    @flask_app.route("/gl-accounts/<int:account_id>/toggle-status", methods=["POST"])
    @login_required
    @role_required("ADMIN")
    def toggle_gl_account_status(account_id):
        session = ext.SessionLocal()
        try:
            account = session.get(GLAccount, account_id)
            if not account:
                return {"status": "error", "message": "GL account not found"}, 404
            account.is_active = not account.is_active
            session.commit()
            return redirect("/gl-accounts?success=status_changed")
        finally:
            session.close()

    @flask_app.route("/switch-fiscal-year", methods=["POST"])
    @login_required
    def switch_fiscal_year():
        fiscal_year_id_raw = (request.form.get("fiscal_year_id") or "").strip()

        if not fiscal_year_id_raw:
            return redirect(request.referrer or url_for("home"))

        db = ext.SessionLocal()
        try:
            fy = db.get(FiscalYear, int(fiscal_year_id_raw))
            if fy:
                flask_session["current_fiscal_year_id"] = fy.id
                flask_session["current_fiscal_year_name"] = fy.year_name
        finally:
            db.close()

        return redirect(request.referrer or url_for("home"))

    @flask_app.route("/api/global-search")
    @login_required
    def api_global_search():
        query = (request.args.get("q") or "").strip()
        return search_global_records(query)

    @flask_app.route("/api/notifications")
    @login_required
    def api_notifications():
        return get_notification_payload()

    @flask_app.route("/notifications-center")
    @login_required
    def notifications_center():
        payload = get_notification_payload()
        return render_template(
            "notifications_center.html",
            items=payload["items"],
            cards=payload["cards"],
        )

