from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import app.extensions as ext

from app.models.branch import Branch
from app.models.cash_payment import CashPayment
from app.models.cash_payment_line import CashPaymentLine
from app.models.gl_account import GLAccount
from app.models.supplier import Supplier
from app.services.journal_service import create_journal_draft, post_journal


class CashPaymentServiceError(Exception):
    pass


TWOPLACES = Decimal("0.01")


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized. Call init_db(app) first.")
    return ext.SessionLocal()


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def to_decimal(value: Any) -> Decimal:
    try:
        if value in (None, ""):
            return Decimal("0.00")
        return Decimal(str(value).replace(",", "").strip()).quantize(TWOPLACES)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CashPaymentServiceError("Amount lazima iwe namba sahihi.") from exc


def generate_payment_no() -> str:
    return f"CP-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _validate_active_branch(branch: Branch | None) -> None:
    if not branch:
        raise CashPaymentServiceError("Branch uliyochagua haipo.")
    if getattr(branch, "is_active", True) is False:
        raise CashPaymentServiceError("Branch uliyochagua imefungwa/inactive.")


def _validate_active_cash_account(account: GLAccount | None) -> None:
    if not account:
        raise CashPaymentServiceError("Cash/Bank account uliyochagua haipo.")
    if getattr(account, "is_active", True) is False:
        raise CashPaymentServiceError("Cash/Bank account uliyochagua imefungwa/inactive.")


def _validate_active_supplier(supplier: Supplier | None) -> None:
    if not supplier:
        raise CashPaymentServiceError("Supplier uliyochagua haipo.")
    if getattr(supplier, "is_active", True) is False:
        raise CashPaymentServiceError("Supplier uliyochagua amefungwa/inactive.")


def _validate_expense_account(account: GLAccount | None, line_no: int) -> None:
    if not account:
        raise CashPaymentServiceError(f"Expense account ya line {line_no} haipo.")
    if getattr(account, "is_active", True) is False:
        raise CashPaymentServiceError(f"Expense account ya line {line_no} imefungwa/inactive.")


def _set_payment_status(payment_id: int, status: str) -> None:
    session = _new_session()
    try:
        payment = session.get(CashPayment, payment_id)
        if not payment:
            raise CashPaymentServiceError("Cash payment haipo kwa ajili ya kusasisha status.")
        payment.status = status
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_cash_payment(
    branch_id: int,
    payment_date,
    payment_type: str,
    cash_account_id: int,
    reference_no: str | None,
    narration: str | None,
    supplier_id: int | None,
    lines: list,
    auto_post: bool = False,
):
    payment_type = _clean_text(payment_type)
    reference_no = _clean_text(reference_no)
    narration = _clean_text(narration)

    if not payment_type:
        raise CashPaymentServiceError("Payment type inahitajika.")

    if not lines:
        raise CashPaymentServiceError("Payment lazima iwe na angalau line moja.")

    session = _new_session()
    payment_id: int | None = None
    payment_no: str | None = None
    total_amount = Decimal("0.00")
    journal_lines: list[dict[str, Any]] = []

    try:
        branch = session.get(Branch, int(branch_id))
        _validate_active_branch(branch)

        cash_account = session.get(GLAccount, int(cash_account_id))
        _validate_active_cash_account(cash_account)

        if supplier_id:
            supplier = session.get(Supplier, int(supplier_id))
            _validate_active_supplier(supplier)

        payment = CashPayment(
            branch_id=int(branch_id),
            supplier_id=int(supplier_id) if supplier_id else None,
            cash_account_id=int(cash_account_id),
            payment_no=generate_payment_no(),
            payment_date=payment_date,
            payment_type=payment_type,
            reference_no=reference_no,
            narration=narration,
            status="draft",
        )
        session.add(payment)
        session.flush()

        valid_lines = 0

        for index, item in enumerate(lines, start=1):
            if not isinstance(item, dict):
                raise CashPaymentServiceError(f"Line ya payment {index} si sahihi.")

            expense_account_id_raw = item.get("expense_account_id")
            if expense_account_id_raw in (None, ""):
                raise CashPaymentServiceError(f"Chagua expense account kwenye line ya {index}.")

            try:
                expense_account_id = int(expense_account_id_raw)
            except (TypeError, ValueError) as exc:
                raise CashPaymentServiceError(f"Expense account ya line {index} si sahihi.") from exc

            description = _clean_text(item.get("description"))
            amount = to_decimal(item.get("amount", 0))

            if amount <= 0:
                raise CashPaymentServiceError(
                    f"Kila payment line lazima iwe na amount kubwa kuliko sifuri. Tatizo line ya {index}."
                )

            expense_account = session.get(GLAccount, expense_account_id)
            _validate_expense_account(expense_account, index)

            line = CashPaymentLine(
                cash_payment_id=payment.id,
                expense_account_id=expense_account_id,
                description=description,
                amount=amount,
            )
            session.add(line)

            total_amount += amount
            valid_lines += 1

            journal_lines.append(
                {
                    "gl_account_id": expense_account_id,
                    "description": description or f"Expense from payment {payment.payment_no}",
                    "debit_amount": amount,
                    "credit_amount": Decimal("0.00"),
                }
            )

        if valid_lines == 0:
            raise CashPaymentServiceError("Payment lazima iwe na angalau line moja yenye amount halali.")

        session.commit()
        payment_id = int(payment.id)
        payment_no = str(payment.payment_no)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    journal_batch_id = None

    if auto_post:
        try:
            journal_input_lines = journal_lines + [
                {
                    "gl_account_id": int(cash_account_id),
                    "description": f"Cash payment {payment_no}",
                    "debit_amount": Decimal("0.00"),
                    "credit_amount": total_amount,
                }
            ]

            journal_batch_id = create_journal_draft(
                branch_id=int(branch_id),
                journal_date=payment_date,
                source_module="CASH_PAYMENT",
                reference_no=payment_no,
                narration=narration or f"Cash payment {payment_no}",
                lines=journal_input_lines,
            )

            post_journal(journal_batch_id)
            _set_payment_status(payment_id, "posted")

        except Exception as exc:
            raise CashPaymentServiceError(
                f"Payment {payment_no} imehifadhiwa kama draft lakini posting ya journal imeshindikana: {exc}"
            ) from exc

    return {
        "payment_id": payment_id,
        "payment_no": payment_no,
        "journal_batch_id": journal_batch_id,
    }


def approve_cash_payment(payment_id: int):
    session = _new_session()
    try:
        payment = session.get(CashPayment, int(payment_id))
        if not payment:
            raise CashPaymentServiceError("Cash payment haipo.")

        if (payment.status or "").lower() == "posted":
            raise CashPaymentServiceError("Cash payment hii tayari imeshapost.")

        branch = session.get(Branch, int(payment.branch_id))
        _validate_active_branch(branch)

        cash_account = session.get(GLAccount, int(payment.cash_account_id))
        _validate_active_cash_account(cash_account)

        if getattr(payment, 'supplier_id', None):
            supplier = session.get(Supplier, int(payment.supplier_id))
            _validate_active_supplier(supplier)

        lines = (
            session.query(CashPaymentLine)
            .filter(CashPaymentLine.cash_payment_id == payment.id)
            .order_by(CashPaymentLine.id.asc())
            .all()
        )
        if not lines:
            raise CashPaymentServiceError("Cash payment haina lines za kuposti.")

        total_amount = Decimal("0.00")
        journal_input_lines: list[dict[str, Any]] = []

        for index, line in enumerate(lines, start=1):
            expense_account = session.get(GLAccount, int(line.expense_account_id))
            _validate_expense_account(expense_account, index)
            amount = to_decimal(line.amount)
            total_amount += amount
            journal_input_lines.append(
                {
                    "gl_account_id": int(line.expense_account_id),
                    "description": _clean_text(line.description) or f"Expense from payment {payment.payment_no}",
                    "debit_amount": amount,
                    "credit_amount": Decimal("0.00"),
                }
            )

        journal_input_lines.append(
            {
                "gl_account_id": int(payment.cash_account_id),
                "description": f"Cash payment {payment.payment_no}",
                "debit_amount": Decimal("0.00"),
                "credit_amount": total_amount,
            }
        )

        journal_batch_id = create_journal_draft(
            branch_id=int(payment.branch_id),
            journal_date=payment.payment_date,
            source_module="CASH_PAYMENT",
            reference_no=payment.payment_no,
            narration=_clean_text(payment.narration) or f"Cash payment {payment.payment_no}",
            lines=journal_input_lines,
        )
        post_journal(journal_batch_id)

        payment.status = "posted"
        session.commit()

        return {
            "payment_id": int(payment.id),
            "payment_no": str(payment.payment_no),
            "journal_batch_id": int(journal_batch_id),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
