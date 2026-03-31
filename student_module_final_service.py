from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import app.extensions as ext
from sqlalchemy.orm import joinedload

from app.models.fee_item import FeeItem
from app.models.gl_account import GLAccount
from app.models.student import Student
from app.models.student_credit_note import StudentCreditNote
from app.models.student_ecl_line import StudentECLLine
from app.models.student_ecl_run import StudentECLRun
from app.models.student_invoice import StudentInvoice
from app.models.student_invoice_line import StudentInvoiceLine
from app.models.student_payment import StudentPayment
from app.models.student_payment_allocation import StudentPaymentAllocation
from app.models.student_refund import StudentRefund
from app.models.student_revenue_recognition_run import StudentRevenueRecognitionRun
from app.models.student_waiver import StudentWaiver
from app.services.journal_service import create_journal_draft, post_journal
from app.services.student_module_service import StudentModuleError

TWOPLACES = Decimal("0.01")


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized. Call init_db(app) first.")
    return ext.SessionLocal()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _parse_date(value: Any):
    if value in (None, ""):
        return None
    if hasattr(value, "isoformat"):
        return value
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise StudentModuleError("Date si sahihi. Tumia YYYY-MM-DD.") from exc


def _to_decimal(value: Any) -> Decimal:
    try:
        if value in (None, ""):
            raise StudentModuleError("Amount inahitajika.")
        return Decimal(str(value).replace(",", "").strip()).quantize(TWOPLACES)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise StudentModuleError("Amount lazima iwe namba sahihi.") from exc


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise StudentModuleError("ID si sahihi.") from exc


def _gen(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _status_after_balance(invoice: StudentInvoice) -> str:
    balance = Decimal(invoice.balance_amount)
    paid = Decimal(invoice.paid_amount)
    if balance <= 0:
        return "paid"
    if paid > 0:
        return "partially_paid"
    if invoice.journal_batch_id:
        return "posted"
    return invoice.status


def _reduce_invoice_balance(session, invoice: StudentInvoice, amount: Decimal) -> None:
    remaining = Decimal(amount)
    lines = session.query(StudentInvoiceLine).filter(
        StudentInvoiceLine.invoice_id == invoice.id,
        StudentInvoiceLine.balance_amount > 0,
    ).order_by(StudentInvoiceLine.id.asc()).all()
    if sum((Decimal(x.balance_amount) for x in lines), Decimal('0.00')) < remaining:
        raise StudentModuleError("Amount inazidi invoice outstanding balance.")
    for line in lines:
        if remaining <= 0:
            break
        open_amt = Decimal(line.balance_amount)
        applied = open_amt if open_amt <= remaining else remaining
        line.balance_amount = open_amt - applied
        remaining -= applied
    invoice.balance_amount = Decimal(invoice.balance_amount) - Decimal(amount)
    invoice.status = _status_after_balance(invoice)


def _aggregate(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bucket: dict[tuple[int, str, str], Decimal] = defaultdict(lambda: Decimal('0.00'))
    for row in lines:
        acct = int(row['gl_account_id'])
        desc = row.get('description') or 'Student final pack posting'
        debit = Decimal(row.get('debit_amount', 0))
        credit = Decimal(row.get('credit_amount', 0))
        if debit > 0:
            bucket[(acct, 'D', desc)] += debit
        if credit > 0:
            bucket[(acct, 'C', desc)] += credit
    result = []
    for (acct, side, desc), amount in bucket.items():
        result.append({
            'gl_account_id': acct,
            'description': desc,
            'debit_amount': amount if side == 'D' else Decimal('0.00'),
            'credit_amount': amount if side == 'C' else Decimal('0.00'),
        })
    return result


def list_student_approval_queue():
    session = _new_session()
    try:
        invoices = session.query(StudentInvoice).options(joinedload(StudentInvoice.student)).filter(StudentInvoice.status == 'draft_pending_review').order_by(StudentInvoice.id.desc()).all()
        payments = session.query(StudentPayment).options(joinedload(StudentPayment.student)).filter(StudentPayment.status == 'draft_pending_review').order_by(StudentPayment.id.desc()).all()
        revenue_runs = session.query(StudentRevenueRecognitionRun).filter(StudentRevenueRecognitionRun.status == 'draft_pending_review').order_by(StudentRevenueRecognitionRun.id.desc()).all()
        waivers = session.query(StudentWaiver).options(joinedload(StudentWaiver.student), joinedload(StudentWaiver.invoice)).filter(StudentWaiver.status == 'draft_pending_review').order_by(StudentWaiver.id.desc()).all()
        credit_notes = session.query(StudentCreditNote).options(joinedload(StudentCreditNote.student), joinedload(StudentCreditNote.invoice)).filter(StudentCreditNote.status == 'draft_pending_review').order_by(StudentCreditNote.id.desc()).all()
        refunds = session.query(StudentRefund).options(joinedload(StudentRefund.student)).filter(StudentRefund.status == 'draft_pending_review').order_by(StudentRefund.id.desc()).all()
        ecl_runs = session.query(StudentECLRun).filter(StudentECLRun.status == 'draft_pending_review').order_by(StudentECLRun.id.desc()).all()
        return {
            'invoices': invoices,
            'payments': payments,
            'revenue_runs': revenue_runs,
            'waivers': waivers,
            'credit_notes': credit_notes,
            'refunds': refunds,
            'ecl_runs': ecl_runs,
        }
    finally:
        session.close()


def approve_existing_student_invoice(invoice_id: Any):
    invoice_id = _optional_int(invoice_id)
    if not invoice_id:
        raise StudentModuleError('Invoice ID si sahihi.')
    session = _new_session()
    try:
        invoice = session.query(StudentInvoice).options(joinedload(StudentInvoice.lines), joinedload(StudentInvoice.student)).filter(StudentInvoice.id == invoice_id).first()
        if not invoice:
            raise StudentModuleError('Student invoice haipo.')
        if invoice.journal_batch_id and invoice.status in {'posted', 'partially_paid', 'paid'}:
            raise StudentModuleError('Invoice hii tayari imepostiwa.')
        if not invoice.lines:
            raise StudentModuleError('Invoice haina lines.')
        debit_by_receivable = defaultdict(lambda: Decimal('0.00'))
        credit_by_recognition = defaultdict(lambda: Decimal('0.00'))
        for line in invoice.lines:
            if not line.receivable_gl_account_id or not line.recognition_gl_account_id:
                raise StudentModuleError('Kuna line ya invoice isiyo na GL mapping kamili.')
            debit_by_receivable[int(line.receivable_gl_account_id)] += Decimal(line.amount)
            credit_by_recognition[int(line.recognition_gl_account_id)] += Decimal(line.amount)
        journal_lines = []
        for acct, amt in debit_by_receivable.items():
            journal_lines.append({'gl_account_id': acct, 'description': f'Student invoice {invoice.invoice_no}', 'debit_amount': amt, 'credit_amount': Decimal('0.00')})
        for acct, amt in credit_by_recognition.items():
            journal_lines.append({'gl_account_id': acct, 'description': f'Student invoice {invoice.invoice_no}', 'debit_amount': Decimal('0.00'), 'credit_amount': amt})
        batch_id = create_journal_draft(branch_id=1, journal_date=invoice.invoice_date, source_module='STUDENT_INVOICE', reference_no=invoice.invoice_no, narration=invoice.remarks or f'Student invoice {invoice.invoice_no}', lines=_aggregate(journal_lines))
        post_journal(batch_id)
        invoice.journal_batch_id = batch_id
        invoice.status = _status_after_balance(invoice)
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def approve_existing_student_payment(payment_id: Any):
    payment_id = _optional_int(payment_id)
    if not payment_id:
        raise StudentModuleError('Payment ID si sahihi.')
    session = _new_session()
    try:
        payment = session.query(StudentPayment).options(joinedload(StudentPayment.allocations).joinedload(StudentPaymentAllocation.invoice_line), joinedload(StudentPayment.allocations).joinedload(StudentPaymentAllocation.invoice)).filter(StudentPayment.id == payment_id).first()
        if not payment:
            raise StudentModuleError('Student payment haipo.')
        if payment.status == 'posted':
            raise StudentModuleError('Payment hii tayari imepostiwa.')
        if Decimal(payment.unallocated_amount) > 0:
            raise StudentModuleError('Payment hii bado ina unallocated amount. Allocate kwanza kabla ya approve/post.')
        if not payment.allocations:
            raise StudentModuleError('Payment haina allocations.')
        journal_lines = [{'gl_account_id': int(payment.cash_account_id), 'description': f'Student payment {payment.payment_no}', 'debit_amount': Decimal(payment.total_amount), 'credit_amount': Decimal('0.00')}]
        by_receivable = defaultdict(lambda: Decimal('0.00'))
        invoice_map = {}
        for alloc in payment.allocations:
            line = alloc.invoice_line
            invoice = alloc.invoice
            if not line or not invoice:
                raise StudentModuleError('Allocation imeharibika.')
            by_receivable[int(line.receivable_gl_account_id)] += Decimal(alloc.allocated_amount)
            invoice_map[invoice.id] = invoice
        for acct, amt in by_receivable.items():
            journal_lines.append({'gl_account_id': acct, 'description': f'Receivable settlement {payment.payment_no}', 'debit_amount': Decimal('0.00'), 'credit_amount': amt})
        batch_id = create_journal_draft(branch_id=1, journal_date=payment.payment_date, source_module='STUDENT_PAYMENT', reference_no=payment.payment_no, narration=payment.remarks or f'Student payment {payment.payment_no}', lines=_aggregate(journal_lines))
        post_journal(batch_id)
        payment.journal_batch_id = batch_id
        payment.status = 'posted'
        for alloc in payment.allocations:
            line = alloc.invoice_line
            invoice = alloc.invoice
            line.paid_amount = Decimal(line.paid_amount) + Decimal(alloc.allocated_amount)
            line.balance_amount = Decimal(line.balance_amount) - Decimal(alloc.allocated_amount)
        for invoice in invoice_map.values():
            invoice.paid_amount = sum((Decimal(x.paid_amount) for x in invoice.lines), Decimal('0.00'))
            invoice.balance_amount = sum((Decimal(x.balance_amount) for x in invoice.lines), Decimal('0.00'))
            invoice.status = _status_after_balance(invoice)
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def create_student_waiver(invoice_id: Any, waiver_date: Any, amount: Any, reason: str | None, auto_post: bool = False, draft_status: str = 'draft'):
    invoice_id = _optional_int(invoice_id)
    dt = _parse_date(waiver_date)
    amt = _to_decimal(amount)
    reason = _clean_text(reason)
    if not invoice_id:
        raise StudentModuleError('Chagua invoice.')
    if not dt:
        raise StudentModuleError('Weka waiver date.')
    if amt <= 0:
        raise StudentModuleError('Waiver amount lazima iwe zaidi ya sifuri.')
    session = _new_session()
    try:
        invoice = session.query(StudentInvoice).options(joinedload(StudentInvoice.lines)).filter(StudentInvoice.id == invoice_id).first()
        if not invoice:
            raise StudentModuleError('Invoice haipo.')
        if Decimal(invoice.balance_amount) <= 0:
            raise StudentModuleError('Invoice hii haina outstanding balance.')
        if Decimal(invoice.balance_amount) < amt:
            raise StudentModuleError('Waiver amount haiwezi kuzidi outstanding balance.')
        row = StudentWaiver(student_id=invoice.student_id, invoice_id=invoice.id, waiver_no=_gen('SWAIV'), waiver_date=dt, reason=reason, amount=amt, status=draft_status)
        session.add(row)
        session.commit()
        waiver_id = row.id
        waiver_no = row.waiver_no
    except Exception:
        session.rollback(); raise
    finally:
        session.close()
    if auto_post:
        approve_student_waiver(waiver_id)
    return {'waiver_id': waiver_id, 'waiver_no': waiver_no}


def approve_student_waiver(waiver_id: Any):
    waiver_id = _optional_int(waiver_id)
    if not waiver_id:
        raise StudentModuleError('Waiver ID si sahihi.')
    session = _new_session()
    try:
        waiver = session.query(StudentWaiver).options(joinedload(StudentWaiver.invoice).joinedload(StudentInvoice.lines)).filter(StudentWaiver.id == waiver_id).first()
        if not waiver:
            raise StudentModuleError('Waiver haipo.')
        if waiver.status == 'posted':
            raise StudentModuleError('Waiver hii tayari imepostiwa.')
        invoice = waiver.invoice
        if not invoice:
            raise StudentModuleError('Waiver haina invoice.')
        # use first open line with fee item discount mapping if available, else recognition GL
        expense_gl = None
        receivable_gl = None
        for line in invoice.lines:
            if Decimal(line.balance_amount) > 0:
                receivable_gl = line.receivable_gl_account_id
                if line.fee_item_id:
                    item = session.get(FeeItem, line.fee_item_id)
                    expense_gl = (item.gl_discount_account_id or item.recognition_gl_account_id or line.recognition_gl_account_id) if item else line.recognition_gl_account_id
                else:
                    expense_gl = line.recognition_gl_account_id
                break
        if not expense_gl or not receivable_gl:
            raise StudentModuleError('Waiver posting GL mapping haijakamilika.')
        batch_id = create_journal_draft(branch_id=1, journal_date=waiver.waiver_date, source_module='STUDENT_WAIVER', reference_no=waiver.waiver_no, narration=waiver.reason or f'Student waiver {waiver.waiver_no}', lines=_aggregate([
            {'gl_account_id': int(expense_gl), 'description': f'Student waiver {waiver.waiver_no}', 'debit_amount': Decimal(waiver.amount), 'credit_amount': Decimal('0.00')},
            {'gl_account_id': int(receivable_gl), 'description': f'Student waiver {waiver.waiver_no}', 'debit_amount': Decimal('0.00'), 'credit_amount': Decimal(waiver.amount)},
        ]))
        post_journal(batch_id)
        waiver.journal_batch_id = batch_id
        waiver.status = 'posted'
        _reduce_invoice_balance(session, invoice, Decimal(waiver.amount))
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_student_waivers():
    session = _new_session()
    try:
        return session.query(StudentWaiver).options(joinedload(StudentWaiver.student), joinedload(StudentWaiver.invoice)).order_by(StudentWaiver.id.desc()).all()
    finally:
        session.close()


def create_student_credit_note(invoice_id: Any, credit_note_date: Any, amount: Any, reason: str | None, auto_post: bool = False, draft_status: str = 'draft'):
    invoice_id = _optional_int(invoice_id)
    dt = _parse_date(credit_note_date)
    amt = _to_decimal(amount)
    reason = _clean_text(reason)
    if not invoice_id:
        raise StudentModuleError('Chagua invoice.')
    session = _new_session()
    try:
        invoice = session.get(StudentInvoice, invoice_id)
        if not invoice:
            raise StudentModuleError('Invoice haipo.')
        if Decimal(invoice.balance_amount) < amt:
            raise StudentModuleError('Credit note haiwezi kuzidi outstanding balance.')
        row = StudentCreditNote(student_id=invoice.student_id, invoice_id=invoice.id, credit_note_no=_gen('SCN'), credit_note_date=dt, reason=reason, amount=amt, status=draft_status)
        session.add(row); session.commit(); row_id=row.id; row_no=row.credit_note_no
    except Exception:
        session.rollback(); raise
    finally:
        session.close()
    if auto_post:
        approve_student_credit_note(row_id)
    return {'credit_note_id': row_id, 'credit_note_no': row_no}


def approve_student_credit_note(credit_note_id: Any):
    credit_note_id = _optional_int(credit_note_id)
    if not credit_note_id:
        raise StudentModuleError('Credit note ID si sahihi.')
    session = _new_session()
    try:
        row = session.query(StudentCreditNote).options(joinedload(StudentCreditNote.invoice).joinedload(StudentInvoice.lines)).filter(StudentCreditNote.id == credit_note_id).first()
        if not row:
            raise StudentModuleError('Credit note haipo.')
        if row.status == 'posted':
            raise StudentModuleError('Credit note tayari imepostiwa.')
        invoice = row.invoice
        adjustment_gl = None
        receivable_gl = None
        for line in invoice.lines:
            if Decimal(line.balance_amount) > 0:
                receivable_gl = line.receivable_gl_account_id
                adjustment_gl = line.recognition_gl_account_id
                break
        if not adjustment_gl or not receivable_gl:
            raise StudentModuleError('Credit note GL mapping haijakamilika.')
        batch_id = create_journal_draft(branch_id=1, journal_date=row.credit_note_date, source_module='STUDENT_CREDIT_NOTE', reference_no=row.credit_note_no, narration=row.reason or f'Credit note {row.credit_note_no}', lines=_aggregate([
            {'gl_account_id': int(adjustment_gl), 'description': f'Credit note {row.credit_note_no}', 'debit_amount': Decimal(row.amount), 'credit_amount': Decimal('0.00')},
            {'gl_account_id': int(receivable_gl), 'description': f'Credit note {row.credit_note_no}', 'debit_amount': Decimal('0.00'), 'credit_amount': Decimal(row.amount)},
        ]))
        post_journal(batch_id)
        row.journal_batch_id = batch_id
        row.status = 'posted'
        _reduce_invoice_balance(session, invoice, Decimal(row.amount))
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_student_credit_notes():
    session = _new_session()
    try:
        return session.query(StudentCreditNote).options(joinedload(StudentCreditNote.student), joinedload(StudentCreditNote.invoice)).order_by(StudentCreditNote.id.desc()).all()
    finally:
        session.close()


def create_student_refund(student_id: Any, payment_id: Any, cash_account_id: Any, refund_gl_account_id: Any, refund_date: Any, amount: Any, reason: str | None, auto_post: bool = False, draft_status: str = 'draft'):
    student_id = _optional_int(student_id)
    payment_id = _optional_int(payment_id)
    cash_account_id = _optional_int(cash_account_id)
    refund_gl_account_id = _optional_int(refund_gl_account_id)
    dt = _parse_date(refund_date)
    amt = _to_decimal(amount)
    reason = _clean_text(reason)
    if not student_id or not cash_account_id or not dt:
        raise StudentModuleError('Student, cash account na refund date vinahitajika.')
    session = _new_session()
    try:
        student = session.get(Student, student_id)
        if not student:
            raise StudentModuleError('Student haipo.')
        cash = session.get(GLAccount, cash_account_id)
        if not cash:
            raise StudentModuleError('Cash account haipo.')
        if refund_gl_account_id:
            if not session.get(GLAccount, refund_gl_account_id):
                raise StudentModuleError('Refund/adjustment GL account haipo.')
        row = StudentRefund(student_id=student_id, payment_id=payment_id, cash_account_id=cash_account_id, refund_gl_account_id=refund_gl_account_id, refund_no=_gen('SREF'), refund_date=dt, reason=reason, amount=amt, status=draft_status)
        session.add(row); session.commit(); row_id=row.id; row_no=row.refund_no
    except Exception:
        session.rollback(); raise
    finally:
        session.close()
    if auto_post:
        approve_student_refund(row_id)
    return {'refund_id': row_id, 'refund_no': row_no}


def approve_student_refund(refund_id: Any):
    refund_id = _optional_int(refund_id)
    if not refund_id:
        raise StudentModuleError('Refund ID si sahihi.')
    session = _new_session()
    try:
        row = session.get(StudentRefund, refund_id)
        if not row:
            raise StudentModuleError('Refund haipo.')
        if row.status == 'posted':
            raise StudentModuleError('Refund tayari imepostiwa.')
        if not row.refund_gl_account_id:
            raise StudentModuleError('Refund GL account inahitajika ili kupost refund.')
        batch_id = create_journal_draft(branch_id=1, journal_date=row.refund_date, source_module='STUDENT_REFUND', reference_no=row.refund_no, narration=row.reason or f'Student refund {row.refund_no}', lines=_aggregate([
            {'gl_account_id': int(row.refund_gl_account_id), 'description': f'Student refund {row.refund_no}', 'debit_amount': Decimal(row.amount), 'credit_amount': Decimal('0.00')},
            {'gl_account_id': int(row.cash_account_id), 'description': f'Student refund {row.refund_no}', 'debit_amount': Decimal('0.00'), 'credit_amount': Decimal(row.amount)},
        ]))
        post_journal(batch_id)
        row.journal_batch_id = batch_id
        row.status = 'posted'
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_student_refunds():
    session = _new_session()
    try:
        return session.query(StudentRefund).options(joinedload(StudentRefund.student), joinedload(StudentRefund.payment)).order_by(StudentRefund.id.desc()).all()
    finally:
        session.close()


def _loss_rate(days_overdue: int) -> tuple[str, Decimal]:
    if days_overdue <= 30:
        return '0-30', Decimal('0.0100')
    if days_overdue <= 60:
        return '31-60', Decimal('0.0500')
    if days_overdue <= 90:
        return '61-90', Decimal('0.1500')
    if days_overdue <= 180:
        return '91-180', Decimal('0.3000')
    return '180+', Decimal('0.5000')


def run_student_ecl(as_of_date: Any, allowance_gl_account_id: Any, remarks: str | None, auto_post: bool = False, draft_status: str = 'draft'):
    as_of = _parse_date(as_of_date)
    allowance_gl_account_id = _optional_int(allowance_gl_account_id)
    remarks = _clean_text(remarks)
    if not as_of:
        raise StudentModuleError('Weka as-of date.')
    session = _new_session()
    try:
        invoices = session.query(StudentInvoice).options(joinedload(StudentInvoice.lines).joinedload(StudentInvoiceLine.fee_item)).filter(StudentInvoice.balance_amount > 0, StudentInvoice.status.in_(['posted', 'partially_paid', 'paid'])).all()
        run = StudentECLRun(run_no=_gen('SECL'), as_of_date=as_of, allowance_gl_account_id=allowance_gl_account_id, remarks=remarks, total_expected_loss=Decimal('0.00'), status=draft_status)
        session.add(run)
        session.flush()
        total = Decimal('0.00')
        for invoice in invoices:
            base_days = (as_of - (invoice.due_date or invoice.invoice_date)).days
            for line in invoice.lines:
                outstanding = Decimal(line.balance_amount)
                if outstanding <= 0:
                    continue
                bucket, rate = _loss_rate(max(base_days, 0))
                expected = (outstanding * rate).quantize(TWOPLACES)
                expense_gl = None
                if line.fee_item_id:
                    item = session.get(FeeItem, line.fee_item_id)
                    expense_gl = item.gl_ecl_account_id if item else None
                ecl_line = StudentECLLine(run_id=run.id, student_id=invoice.student_id, invoice_id=invoice.id, invoice_line_id=line.id, ecl_expense_gl_account_id=expense_gl, age_bucket=bucket, outstanding_amount=outstanding, loss_rate=rate, expected_loss_amount=expected)
                session.add(ecl_line)
                total += expected
        run.total_expected_loss = total
        session.commit(); run_id=run.id; run_no=run.run_no
    except Exception:
        session.rollback(); raise
    finally:
        session.close()
    if auto_post:
        approve_student_ecl_run(run_id)
    return {'run_id': run_id, 'run_no': run_no}


def approve_student_ecl_run(run_id: Any):
    run_id = _optional_int(run_id)
    if not run_id:
        raise StudentModuleError('ECL run ID si sahihi.')
    session = _new_session()
    try:
        run = session.query(StudentECLRun).options(joinedload(StudentECLRun.lines)).filter(StudentECLRun.id == run_id).first()
        if not run:
            raise StudentModuleError('ECL run haipo.')
        if run.status == 'posted':
            raise StudentModuleError('ECL run tayari imepostiwa.')
        if not run.allowance_gl_account_id:
            raise StudentModuleError('Allowance GL account inahitajika ili kupost ECL run.')
        grouped = defaultdict(lambda: Decimal('0.00'))
        for line in run.lines:
            if not line.ecl_expense_gl_account_id:
                continue
            grouped[int(line.ecl_expense_gl_account_id)] += Decimal(line.expected_loss_amount)
        if not grouped:
            raise StudentModuleError('Hakuna ECL expense GL mapping kwenye run hii.')
        journal_lines = []
        total = Decimal('0.00')
        for acct, amt in grouped.items():
            journal_lines.append({'gl_account_id': acct, 'description': f'ECL run {run.run_no}', 'debit_amount': amt, 'credit_amount': Decimal('0.00')})
            total += amt
        journal_lines.append({'gl_account_id': int(run.allowance_gl_account_id), 'description': f'ECL allowance {run.run_no}', 'debit_amount': Decimal('0.00'), 'credit_amount': total})
        batch_id = create_journal_draft(branch_id=1, journal_date=run.as_of_date, source_module='STUDENT_ECL', reference_no=run.run_no, narration=run.remarks or f'Student ECL run {run.run_no}', lines=_aggregate(journal_lines))
        post_journal(batch_id)
        run.journal_batch_id = batch_id
        run.status = 'posted'
        session.commit()
        return batch_id
    except Exception:
        session.rollback(); raise
    finally:
        session.close()


def list_student_ecl_runs():
    session = _new_session()
    try:
        return session.query(StudentECLRun).options(joinedload(StudentECLRun.lines)).order_by(StudentECLRun.id.desc()).all()
    finally:
        session.close()
