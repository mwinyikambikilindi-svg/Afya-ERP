from __future__ import annotations

from datetime import date

from flask import redirect, render_template, request, session as flask_session, url_for

from app.services.audit_log_service import log_audit_event
from app.services.auth_service import login_required, role_required
from app.services.student_module_final_service import (
    StudentModuleError,
    approve_existing_student_invoice,
    approve_existing_student_payment,
    approve_student_credit_note,
    approve_student_ecl_run,
    approve_student_refund,
    approve_student_waiver,
    create_student_credit_note,
    create_student_refund,
    create_student_waiver,
    list_student_approval_queue,
    list_student_credit_notes,
    list_student_ecl_runs,
    list_student_refunds,
    list_student_waivers,
    run_student_ecl,
)
from app.services.student_module_service import (
    list_cash_accounts,
    list_fee_items,
    list_gl_accounts_for_mapping,
    list_student_invoices,
    list_student_payments,
    list_students,
)


def register_student_pack4_routes(flask_app):
    @flask_app.route('/student-approvals')
    @login_required
    @role_required('ADMIN')
    def student_approvals():
        queue = list_student_approval_queue()
        return render_template('student_approvals.html', queue=queue)

    @flask_app.route('/student-invoices/<int:invoice_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_student_invoice_route(invoice_id):
        try:
            approve_existing_student_invoice(invoice_id)
            log_audit_event(user_id=flask_session.get('user_id'), module_name='STUDENT_INVOICE', record_table='student_invoices', record_id=invoice_id, action_name='APPROVE_AND_POST', details=f'Student invoice {invoice_id} approved and posted')
            return redirect(url_for('student_approvals'))
        except StudentModuleError as e:
            return redirect(url_for('student_approvals', error=str(e)))

    @flask_app.route('/student-payments/<int:payment_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_student_payment_route(payment_id):
        try:
            approve_existing_student_payment(payment_id)
            log_audit_event(user_id=flask_session.get('user_id'), module_name='STUDENT_PAYMENT', record_table='student_payments', record_id=payment_id, action_name='APPROVE_AND_POST', details=f'Student payment {payment_id} approved and posted')
            return redirect(url_for('student_approvals'))
        except StudentModuleError as e:
            return redirect(url_for('student_approvals', error=str(e)))

    @flask_app.route('/student-waivers', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def student_waivers():
        error_message = None
        if request.method == 'POST':
            try:
                action = (request.form.get('action') or 'save').strip().lower()
                current_role = (flask_session.get('role_name') or '').strip().upper()
                auto_post = action == 'post' and current_role == 'ADMIN'
                draft_status = 'draft_pending_review' if action == 'post' and current_role != 'ADMIN' else 'draft'
                result = create_student_waiver(
                    invoice_id=request.form.get('invoice_id'),
                    waiver_date=request.form.get('waiver_date'),
                    amount=request.form.get('amount'),
                    reason=request.form.get('reason'),
                    auto_post=auto_post,
                    draft_status=draft_status,
                )
                log_audit_event(user_id=flask_session.get('user_id'), module_name='STUDENT_WAIVER', record_table='student_waivers', record_id=result['waiver_id'], action_name='POST_WAIVER' if auto_post else 'CREATE_WAIVER', details=f"Student waiver {result['waiver_no']} processed")
                return redirect(url_for('student_waivers', success=result['waiver_no']))
            except StudentModuleError as e:
                error_message = str(e)
        return render_template('student_waivers.html', invoices=list_student_invoices(), rows=list_student_waivers(), default_waiver_date=date.today().isoformat(), error_message=error_message, success=request.args.get('success'))

    @flask_app.route('/student-waivers/<int:waiver_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_student_waiver_route(waiver_id):
        try:
            approve_student_waiver(waiver_id)
            return redirect(url_for('student_waivers'))
        except StudentModuleError as e:
            return redirect(url_for('student_waivers', error=str(e)))

    @flask_app.route('/student-credit-notes', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def student_credit_notes():
        error_message = None
        if request.method == 'POST':
            try:
                action = (request.form.get('action') or 'save').strip().lower()
                current_role = (flask_session.get('role_name') or '').strip().upper()
                auto_post = action == 'post' and current_role == 'ADMIN'
                draft_status = 'draft_pending_review' if action == 'post' and current_role != 'ADMIN' else 'draft'
                result = create_student_credit_note(
                    invoice_id=request.form.get('invoice_id'),
                    credit_note_date=request.form.get('credit_note_date'),
                    amount=request.form.get('amount'),
                    reason=request.form.get('reason'),
                    auto_post=auto_post,
                    draft_status=draft_status,
                )
                return redirect(url_for('student_credit_notes', success=result['credit_note_no']))
            except StudentModuleError as e:
                error_message = str(e)
        return render_template('student_credit_notes.html', invoices=list_student_invoices(), rows=list_student_credit_notes(), default_credit_note_date=date.today().isoformat(), error_message=error_message, success=request.args.get('success'))

    @flask_app.route('/student-credit-notes/<int:credit_note_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_student_credit_note_route(credit_note_id):
        try:
            approve_student_credit_note(credit_note_id)
            return redirect(url_for('student_credit_notes'))
        except StudentModuleError as e:
            return redirect(url_for('student_credit_notes', error=str(e)))

    @flask_app.route('/student-refunds', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def student_refunds():
        error_message = None
        if request.method == 'POST':
            try:
                action = (request.form.get('action') or 'save').strip().lower()
                current_role = (flask_session.get('role_name') or '').strip().upper()
                auto_post = action == 'post' and current_role == 'ADMIN'
                draft_status = 'draft_pending_review' if action == 'post' and current_role != 'ADMIN' else 'draft'
                result = create_student_refund(
                    student_id=request.form.get('student_id'),
                    payment_id=request.form.get('payment_id'),
                    cash_account_id=request.form.get('cash_account_id'),
                    refund_gl_account_id=request.form.get('refund_gl_account_id'),
                    refund_date=request.form.get('refund_date'),
                    amount=request.form.get('amount'),
                    reason=request.form.get('reason'),
                    auto_post=auto_post,
                    draft_status=draft_status,
                )
                return redirect(url_for('student_refunds', success=result['refund_no']))
            except StudentModuleError as e:
                error_message = str(e)
        return render_template('student_refunds.html', students=list_students(), payments=list_student_payments(), cash_accounts=list_cash_accounts(), gl_accounts=list_gl_accounts_for_mapping(), rows=list_student_refunds(), default_refund_date=date.today().isoformat(), error_message=error_message, success=request.args.get('success'))

    @flask_app.route('/student-refunds/<int:refund_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_student_refund_route(refund_id):
        try:
            approve_student_refund(refund_id)
            return redirect(url_for('student_refunds'))
        except StudentModuleError as e:
            return redirect(url_for('student_refunds', error=str(e)))

    @flask_app.route('/student-ecl', methods=['GET', 'POST'])
    @login_required
    @role_required('ADMIN', 'ACCOUNTANT')
    def student_ecl():
        error_message = None
        if request.method == 'POST':
            try:
                action = (request.form.get('action') or 'save').strip().lower()
                current_role = (flask_session.get('role_name') or '').strip().upper()
                auto_post = action == 'post' and current_role == 'ADMIN'
                draft_status = 'draft_pending_review' if action == 'post' and current_role != 'ADMIN' else 'draft'
                result = run_student_ecl(
                    as_of_date=request.form.get('as_of_date'),
                    allowance_gl_account_id=request.form.get('allowance_gl_account_id'),
                    remarks=request.form.get('remarks'),
                    auto_post=auto_post,
                    draft_status=draft_status,
                )
                return redirect(url_for('student_ecl', success=result['run_no']))
            except StudentModuleError as e:
                error_message = str(e)
        return render_template('student_ecl.html', gl_accounts=list_gl_accounts_for_mapping(), rows=list_student_ecl_runs(), default_as_of_date=date.today().isoformat(), error_message=error_message, success=request.args.get('success'))

    @flask_app.route('/student-ecl/<int:run_id>/approve', methods=['POST'])
    @login_required
    @role_required('ADMIN')
    def approve_student_ecl_route(run_id):
        try:
            approve_student_ecl_run(run_id)
            return redirect(url_for('student_ecl'))
        except StudentModuleError as e:
            return redirect(url_for('student_ecl', error=str(e)))
