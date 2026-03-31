from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import has_request_context, session as flask_session

import app.extensions as ext
from app.models.accounting_period import AccountingPeriod
from app.models.branch import Branch
from app.models.fiscal_year import FiscalYear
from app.models.gl_account import GLAccount
from app.models.journal_batch import JournalBatch
from app.models.journal_line import JournalLine

TWOPLACES = Decimal("0.01")


class JournalServiceError(Exception):
    pass


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized. Call init_db(app) first.")
    return ext.SessionLocal()


def _normalize_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.strptime(value.strip(), "%Y-%m-%d").date()
        except ValueError as exc:
            raise JournalServiceError("Tarehe ya journal si sahihi. Tumia YYYY-MM-DD.") from exc
    raise JournalServiceError("Journal date si sahihi.")


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None


def to_decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0.00")
    try:
        cleaned = str(value).replace(",", "").strip()
        return Decimal(cleaned).quantize(TWOPLACES)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise JournalServiceError(f"Kiasi si sahihi: {value!r}") from exc


def generate_batch_no() -> str:
    return f"JV-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"


def _current_fiscal_year_id() -> int | None:
    if not has_request_context():
        return None

    raw_value = flask_session.get("current_fiscal_year_id")
    if raw_value in (None, ""):
        return None

    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def resolve_open_period(session, journal_date: Any) -> AccountingPeriod:
    normalized_date = _normalize_date(journal_date)
    current_fy_id = _current_fiscal_year_id()

    query = (
        session.query(AccountingPeriod)
        .join(FiscalYear, FiscalYear.id == AccountingPeriod.fiscal_year_id)
        .filter(
            AccountingPeriod.start_date <= normalized_date,
            AccountingPeriod.end_date >= normalized_date,
            AccountingPeriod.status == "open",
            FiscalYear.start_date <= normalized_date,
            FiscalYear.end_date >= normalized_date,
            FiscalYear.status == "open",
        )
    )

    if current_fy_id:
        query = query.filter(AccountingPeriod.fiscal_year_id == current_fy_id)

    period = query.order_by(AccountingPeriod.start_date.asc()).first()

    if not period:
        if current_fy_id:
            raise JournalServiceError(
                "Hakuna accounting period open kwa tarehe hiyo ndani ya fiscal year active."
            )
        raise JournalServiceError("Hakuna accounting period open kwa tarehe hiyo.")

    return period


def _validate_period_for_posting(session, period: AccountingPeriod, journal_date: date) -> None:
    if not period.contains_date(journal_date):
        raise JournalServiceError("Journal date iko nje ya accounting period uliyochagua.")

    if not period.is_open:
        raise JournalServiceError("Accounting period hii imefungwa. Posting hairuhusiwi.")

    fiscal_year = session.get(FiscalYear, period.fiscal_year_id)
    if not fiscal_year:
        raise JournalServiceError("Fiscal year ya accounting period haipo.")

    if not fiscal_year.contains_date(journal_date):
        raise JournalServiceError("Journal date iko nje ya fiscal year ya accounting period hii.")

    if not fiscal_year.is_open:
        raise JournalServiceError("Fiscal year hii imefungwa. Posting hairuhusiwi.")

    current_fy_id = _current_fiscal_year_id()
    if current_fy_id and fiscal_year.id != current_fy_id:
        raise JournalServiceError(
            "Journal haiwezi kuandikwa nje ya fiscal year active uliyochagua kwenye mfumo."
        )


def _validate_gl_accounts(session, lines: list[dict[str, Any]]) -> None:
    account_ids: list[int] = []

    for index, item in enumerate(lines, start=1):
        raw_id = item.get("gl_account_id")
        if raw_id in (None, ""):
            raise JournalServiceError(f"GL account inakosekana kwenye line ya {index}.")
        try:
            account_ids.append(int(raw_id))
        except (TypeError, ValueError) as exc:
            raise JournalServiceError(f"GL account si sahihi kwenye line ya {index}.") from exc

    existing_accounts = session.query(GLAccount).filter(GLAccount.id.in_(set(account_ids))).all()
    account_map = {account.id: account for account in existing_accounts}

    missing_ids = sorted(set(account_ids) - set(account_map.keys()))
    if missing_ids:
        raise JournalServiceError(f"Kuna GL account ambayo haipo: {missing_ids}")

    inactive_codes = [
        getattr(account, "code", str(account.id))
        for account in existing_accounts
        if getattr(account, "is_active", True) is False
    ]
    if inactive_codes:
        raise JournalServiceError(
            f"Huwezi kutumia GL account zilizofungwa/inactive: {', '.join(inactive_codes)}"
        )

    blocked_manual_codes = [
        getattr(account, "code", str(account.id))
        for account in existing_accounts
        if getattr(account, "allow_manual_posting", True) is False
    ]
    if blocked_manual_codes:
        raise JournalServiceError(
            "Accounts hizi haziruhusu manual posting: " + ", ".join(blocked_manual_codes)
        )


def _prepare_lines(lines: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Decimal, Decimal]:
    if not lines or len(lines) < 2:
        raise JournalServiceError("Journal lazima iwe na angalau mistari miwili.")

    prepared_lines: list[dict[str, Any]] = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for index, item in enumerate(lines, start=1):
        if not isinstance(item, dict):
            raise JournalServiceError(f"Line ya {index} si sahihi.")

        try:
            gl_account_id = int(item.get("gl_account_id"))
        except (TypeError, ValueError) as exc:
            raise JournalServiceError(f"GL account si sahihi kwenye line ya {index}.") from exc

        debit = to_decimal(item.get("debit_amount", 0))
        credit = to_decimal(item.get("credit_amount", 0))

        if debit < 0 or credit < 0:
            raise JournalServiceError("Debit au Credit haiwezi kuwa negative.")
        if debit > 0 and credit > 0:
            raise JournalServiceError("Line moja haiwezi kuwa na debit na credit kwa pamoja.")
        if debit == 0 and credit == 0:
            raise JournalServiceError("Line moja lazima iwe na debit au credit.")

        prepared_lines.append(
            {
                "gl_account_id": gl_account_id,
                "description": _clean_text(item.get("description")),
                "debit_amount": debit,
                "credit_amount": credit,
            }
        )

        total_debit += debit
        total_credit += credit

    if total_debit != total_credit:
        raise JournalServiceError(
            f"Debit na Credit havilingani. Debit={total_debit}, Credit={total_credit}"
        )

    return prepared_lines, total_debit, total_credit


def _line_signature(lines: list[dict[str, Any]]) -> list[tuple[int, str, str, str]]:
    signature: list[tuple[int, str, str, str]] = []

    for item in lines:
        signature.append(
            (
                int(item["gl_account_id"]),
                f"{item['debit_amount']:.2f}",
                f"{item['credit_amount']:.2f}",
                (item.get("description") or "").strip().lower(),
            )
        )

    return sorted(signature, key=lambda x: (x[0], x[1], x[2], x[3]))


def _batch_line_signature(session, batch_id: int) -> list[tuple[int, str, str, str]]:
    rows = (
        session.query(JournalLine)
        .filter(JournalLine.journal_batch_id == batch_id)
        .order_by(JournalLine.id.asc())
        .all()
    )

    signature: list[tuple[int, str, str, str]] = []
    for row in rows:
        signature.append(
            (
                int(row.gl_account_id),
                f"{Decimal(row.debit_amount):.2f}",
                f"{Decimal(row.credit_amount):.2f}",
                (row.description or "").strip().lower(),
            )
        )

    return sorted(signature, key=lambda x: (x[0], x[1], x[2], x[3]))


def _find_duplicate_by_reference(session, branch_id: int, source_module: str, reference_no: str | None, period_id: int | None):
    if not reference_no:
        return None

    query = (
        session.query(JournalBatch)
        .filter(
            JournalBatch.branch_id == branch_id,
            JournalBatch.source_module == source_module,
            JournalBatch.reference_no == reference_no,
            JournalBatch.status != JournalBatch.STATUS_REJECTED,
        )
    )

    if period_id is not None:
        query = query.filter(JournalBatch.period_id == period_id)

    return query.order_by(JournalBatch.id.desc()).first()


def _find_duplicate_by_content(session, branch_id: int, period_id: int | None, journal_date: date, source_module: str, narration: str | None, prepared_lines: list[dict[str, Any]]):
    candidates_query = (
        session.query(JournalBatch)
        .filter(
            JournalBatch.branch_id == branch_id,
            JournalBatch.journal_date == journal_date,
            JournalBatch.source_module == source_module,
            JournalBatch.status != JournalBatch.STATUS_REJECTED,
        )
    )

    if period_id is not None:
        candidates_query = candidates_query.filter(JournalBatch.period_id == period_id)

    candidates = candidates_query.order_by(JournalBatch.id.desc()).limit(20).all()
    incoming_signature = _line_signature(prepared_lines)
    normalized_narration = (narration or "").strip().lower()

    for candidate in candidates:
        if (candidate.narration or "").strip().lower() != normalized_narration:
            continue
        if _batch_line_signature(session, candidate.id) == incoming_signature:
            return candidate

    return None


def ensure_not_duplicate(session, branch_id: int, period_id: int | None, journal_date: date, source_module: str, reference_no: str | None, narration: str | None, prepared_lines: list[dict[str, Any]]) -> None:
    by_reference = _find_duplicate_by_reference(
        session=session,
        branch_id=branch_id,
        source_module=source_module,
        reference_no=reference_no,
        period_id=period_id,
    )
    if by_reference:
        raise JournalServiceError(
            f"Duplicate warning: reference {reference_no} tayari ipo kwenye batch {by_reference.batch_no} (status: {by_reference.status})."
        )

    by_content = _find_duplicate_by_content(
        session=session,
        branch_id=branch_id,
        period_id=period_id,
        journal_date=journal_date,
        source_module=source_module,
        narration=narration,
        prepared_lines=prepared_lines,
    )
    if by_content:
        raise JournalServiceError(
            f"Duplicate warning: journal yenye content zinazofanana tayari ipo kwenye batch {by_content.batch_no} (status: {by_content.status})."
        )


def create_journal_draft(branch_id: int, journal_date: Any, source_module: str, reference_no: str | None, narration: str | None, lines: list[dict[str, Any]], period_id: int | None = None):
    normalized_date = _normalize_date(journal_date)
    source_module = (source_module or "").strip().upper()
    reference_no = _clean_text(reference_no)
    narration = _clean_text(narration)

    if not source_module:
        raise JournalServiceError("Source module inahitajika.")

    prepared_lines, _, _ = _prepare_lines(lines)

    session = _new_session()
    try:
        branch = session.get(Branch, int(branch_id))
        if not branch:
            raise JournalServiceError("Branch uliyochagua haipo.")
        if getattr(branch, "is_active", True) is False:
            raise JournalServiceError("Branch uliyochagua imefungwa/inactive.")

        if period_id is None:
            period = resolve_open_period(session, normalized_date)
            period_id = period.id
        else:
            try:
                period_id = int(period_id)
            except (TypeError, ValueError) as exc:
                raise JournalServiceError("Accounting period si sahihi.") from exc
            period = session.get(AccountingPeriod, period_id)

        if not period:
            raise JournalServiceError("Accounting period haipo.")

        _validate_period_for_posting(session, period, normalized_date)
        _validate_gl_accounts(session, prepared_lines)

        ensure_not_duplicate(
            session=session,
            branch_id=int(branch_id),
            period_id=period_id,
            journal_date=normalized_date,
            source_module=source_module,
            reference_no=reference_no,
            narration=narration,
            prepared_lines=prepared_lines,
        )

        batch = JournalBatch(
            branch_id=int(branch_id),
            period_id=period_id,
            batch_no=generate_batch_no(),
            journal_date=normalized_date,
            source_module=source_module,
            reference_no=reference_no,
            narration=narration,
            status=JournalBatch.STATUS_DRAFT,
        )
        session.add(batch)
        session.flush()

        for item in prepared_lines:
            session.add(
                JournalLine(
                    journal_batch_id=batch.id,
                    gl_account_id=item["gl_account_id"],
                    branch_id=int(branch_id),
                    description=item["description"],
                    debit_amount=item["debit_amount"],
                    credit_amount=item["credit_amount"],
                )
            )

        session.commit()
        return batch.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def submit_journal_for_approval(batch_id: int):
    session = _new_session()
    try:
        batch = session.get(JournalBatch, int(batch_id))
        if not batch:
            raise JournalServiceError("Journal batch haipo.")

        if batch.status != JournalBatch.STATUS_DRAFT:
            raise JournalServiceError("Ni draft journal tu inaweza kutumwa approval.")

        lines = session.query(JournalLine).filter_by(journal_batch_id=batch.id).all()
        if not lines:
            raise JournalServiceError("Journal haina mistari ya posting.")

        total_debit = sum((Decimal(line.debit_amount) for line in lines), Decimal("0.00"))
        total_credit = sum((Decimal(line.credit_amount) for line in lines), Decimal("0.00"))

        if total_debit != total_credit:
            raise JournalServiceError(
                f"Journal haipo balanced. Debit={total_debit}, Credit={total_credit}"
            )

        batch.status = JournalBatch.STATUS_PENDING_APPROVAL
        session.commit()
        return batch.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def post_journal(batch_id: int):
    session = _new_session()
    try:
        batch = session.get(JournalBatch, int(batch_id))
        if not batch:
            raise JournalServiceError("Journal batch haipo.")

        if batch.status not in (JournalBatch.STATUS_DRAFT, JournalBatch.STATUS_PENDING_APPROVAL):
            raise JournalServiceError("Journal hii haiwezi kupostiwa katika status yake ya sasa.")

        period = session.get(AccountingPeriod, batch.period_id) if batch.period_id else None
        if not period:
            raise JournalServiceError("Journal haina accounting period sahihi.")

        _validate_period_for_posting(session, period, batch.journal_date)

        lines = session.query(JournalLine).filter_by(journal_batch_id=batch.id).all()
        if not lines:
            raise JournalServiceError("Journal haina mistari ya posting.")

        total_debit = sum((Decimal(line.debit_amount) for line in lines), Decimal("0.00"))
        total_credit = sum((Decimal(line.credit_amount) for line in lines), Decimal("0.00"))

        if total_debit != total_credit:
            raise JournalServiceError(
                f"Journal haipo balanced. Debit={total_debit}, Credit={total_credit}"
            )

        batch.status = JournalBatch.STATUS_POSTED
        session.commit()
        return batch.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
