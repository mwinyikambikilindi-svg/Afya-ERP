from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import app.extensions as ext

from app.models.branch import Branch
from app.models.cash_receipt import CashReceipt
from app.models.cash_receipt_line import CashReceiptLine
from app.models.gl_account import GLAccount
from app.models.payer import Payer
from app.services.journal_service import create_journal_draft, post_journal


class CashReceiptServiceError(Exception):
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
        raise CashReceiptServiceError("Amount lazima iwe namba sahihi.") from exc


def generate_receipt_no() -> str:
    return f"CR-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _validate_active_branch(branch: Branch | None) -> None:
    if not branch:
        raise CashReceiptServiceError("Branch uliyochagua haipo.")
    if getattr(branch, "is_active", True) is False:
        raise CashReceiptServiceError("Branch uliyochagua imefungwa/inactive.")


def _validate_active_cash_account(account: GLAccount | None) -> None:
    if not account:
        raise CashReceiptServiceError("Cash/Bank account uliyochagua haipo.")
    if getattr(account, "is_active", True) is False:
        raise CashReceiptServiceError("Cash/Bank account uliyochagua imefungwa/inactive.")


def _validate_active_payer(payer: Payer | None) -> None:
    if not payer:
        raise CashReceiptServiceError("Payer uliyochagua haipo.")
    if getattr(payer, "is_active", True) is False:
        raise CashReceiptServiceError("Payer uliyochagua amefungwa/inactive.")


def _validate_revenue_account(account: GLAccount | None, line_no: int) -> None:
    if not account:
        raise CashReceiptServiceError(f"Revenue account ya line {line_no} haipo.")
    if getattr(account, "is_active", True) is False:
        raise CashReceiptServiceError(f"Revenue account ya line {line_no} imefungwa/inactive.")


def _set_receipt_status(receipt_id: int, status: str) -> None:
    session = _new_session()
    try:
        receipt = session.get(CashReceipt, receipt_id)
        if not receipt:
            raise CashReceiptServiceError("Cash receipt haipo kwa ajili ya kusasisha status.")
        receipt.status = status
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_cash_receipt(
    branch_id: int,
    receipt_date,
    receipt_type: str,
    cash_account_id: int,
    reference_no: str | None,
    narration: str | None,
    payer_id: int | None,
    lines: list,
    auto_post: bool = False,
):
    receipt_type = _clean_text(receipt_type)
    reference_no = _clean_text(reference_no)
    narration = _clean_text(narration)

    if not receipt_type:
        raise CashReceiptServiceError("Receipt type inahitajika.")

    if not lines:
        raise CashReceiptServiceError("Receipt lazima iwe na angalau line moja.")

    session = _new_session()
    receipt_id: int | None = None
    receipt_no: str | None = None
    total_amount = Decimal("0.00")
    journal_lines: list[dict[str, Any]] = []

    try:
        branch = session.get(Branch, int(branch_id))
        _validate_active_branch(branch)

        cash_account = session.get(GLAccount, int(cash_account_id))
        _validate_active_cash_account(cash_account)

        if payer_id:
            payer = session.get(Payer, int(payer_id))
            _validate_active_payer(payer)

        receipt = CashReceipt(
            branch_id=int(branch_id),
            payer_id=int(payer_id) if payer_id else None,
            cash_account_id=int(cash_account_id),
            receipt_no=generate_receipt_no(),
            receipt_date=receipt_date,
            receipt_type=receipt_type,
            reference_no=reference_no,
            narration=narration,
            status="draft",
        )
        session.add(receipt)
        session.flush()

        valid_lines = 0

        for index, item in enumerate(lines, start=1):
            if not isinstance(item, dict):
                raise CashReceiptServiceError(f"Line ya receipt {index} si sahihi.")

            revenue_account_id_raw = item.get("revenue_account_id")
            if revenue_account_id_raw in (None, ""):
                raise CashReceiptServiceError(f"Chagua revenue account kwenye line ya {index}.")

            try:
                revenue_account_id = int(revenue_account_id_raw)
            except (TypeError, ValueError) as exc:
                raise CashReceiptServiceError(f"Revenue account ya line {index} si sahihi.") from exc

            description = _clean_text(item.get("description"))
            amount = to_decimal(item.get("amount", 0))

            if amount <= 0:
                raise CashReceiptServiceError(
                    f"Kila receipt line lazima iwe na amount kubwa kuliko sifuri. Tatizo line ya {index}."
                )

            revenue_account = session.get(GLAccount, revenue_account_id)
            _validate_revenue_account(revenue_account, index)

            line = CashReceiptLine(
                cash_receipt_id=receipt.id,
                revenue_account_id=revenue_account_id,
                description=description,
                amount=amount,
            )
            session.add(line)

            total_amount += amount
            valid_lines += 1

            journal_lines.append(
                {
                    "gl_account_id": revenue_account_id,
                    "description": description or f"Revenue from receipt {receipt.receipt_no}",
                    "debit_amount": Decimal("0.00"),
                    "credit_amount": amount,
                }
            )

        if valid_lines == 0:
            raise CashReceiptServiceError("Receipt lazima iwe na angalau line moja yenye amount halali.")

        session.commit()
        receipt_id = int(receipt.id)
        receipt_no = str(receipt.receipt_no)

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    journal_batch_id = None

    if auto_post:
        try:
            journal_input_lines = [
                {
                    "gl_account_id": int(cash_account_id),
                    "description": f"Cash receipt {receipt_no}",
                    "debit_amount": total_amount,
                    "credit_amount": Decimal("0.00"),
                }
            ] + journal_lines

            journal_batch_id = create_journal_draft(
                branch_id=int(branch_id),
                journal_date=receipt_date,
                source_module="CASH_RECEIPT",
                reference_no=receipt_no,
                narration=narration or f"Cash receipt {receipt_no}",
                lines=journal_input_lines,
            )

            post_journal(journal_batch_id)
            _set_receipt_status(receipt_id, "posted")

        except Exception as exc:
            raise CashReceiptServiceError(
                f"Receipt {receipt_no} imehifadhiwa kama draft lakini posting ya journal imeshindikana: {exc}"
            ) from exc

    return {
        "receipt_id": receipt_id,
        "receipt_no": receipt_no,
        "journal_batch_id": journal_batch_id,
    }


def approve_cash_receipt(receipt_id: int):
    session = _new_session()
    try:
        receipt = session.get(CashReceipt, int(receipt_id))
        if not receipt:
            raise CashReceiptServiceError("Cash receipt haipo.")

        if (receipt.status or "").lower() == "posted":
            raise CashReceiptServiceError("Cash receipt hii tayari imeshapost.")

        branch = session.get(Branch, int(receipt.branch_id))
        _validate_active_branch(branch)

        cash_account = session.get(GLAccount, int(receipt.cash_account_id))
        _validate_active_cash_account(cash_account)

        if getattr(receipt, 'payer_id', None):
            payer = session.get(Payer, int(receipt.payer_id))
            _validate_active_payer(payer)

        lines = (
            session.query(CashReceiptLine)
            .filter(CashReceiptLine.cash_receipt_id == receipt.id)
            .order_by(CashReceiptLine.id.asc())
            .all()
        )
        if not lines:
            raise CashReceiptServiceError("Cash receipt haina lines za kuposti.")

        total_amount = Decimal("0.00")
        journal_input_lines: list[dict[str, Any]] = [
            {
                "gl_account_id": int(receipt.cash_account_id),
                "description": f"Cash receipt {receipt.receipt_no}",
                "debit_amount": Decimal("0.00"),
                "credit_amount": Decimal("0.00"),
            }
        ]

        for index, line in enumerate(lines, start=1):
            revenue_account = session.get(GLAccount, int(line.revenue_account_id))
            _validate_revenue_account(revenue_account, index)
            amount = to_decimal(line.amount)
            total_amount += amount
            journal_input_lines.append(
                {
                    "gl_account_id": int(line.revenue_account_id),
                    "description": _clean_text(line.description) or f"Revenue from receipt {receipt.receipt_no}",
                    "debit_amount": Decimal("0.00"),
                    "credit_amount": amount,
                }
            )

        journal_input_lines[0]["debit_amount"] = total_amount

        journal_batch_id = create_journal_draft(
            branch_id=int(receipt.branch_id),
            journal_date=receipt.receipt_date,
            source_module="CASH_RECEIPT",
            reference_no=receipt.receipt_no,
            narration=_clean_text(receipt.narration) or f"Cash receipt {receipt.receipt_no}",
            lines=journal_input_lines,
        )
        post_journal(journal_batch_id)

        receipt.status = "posted"
        session.commit()

        return {
            "receipt_id": int(receipt.id),
            "receipt_no": str(receipt.receipt_no),
            "journal_batch_id": int(journal_batch_id),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
