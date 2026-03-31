from __future__ import annotations

from sqlalchemy import text
import app.extensions as ext


class BudgetWorkflowError(Exception):
    pass


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized.")
    return ext.SessionLocal()


def get_budget_header_status(header_id: int) -> str | None:
    session = _new_session()
    try:
        row = session.execute(text("""
            SELECT status
            FROM budget_headers
            WHERE id = :header_id
        """), {"header_id": header_id}).first()
        return row[0] if row else None
    finally:
        session.close()


def assert_budget_editable(session, header_id: int):
    row = session.execute(text("""
        SELECT status
        FROM budget_headers
        WHERE id = :header_id
    """), {"header_id": header_id}).first()

    if not row:
        raise BudgetWorkflowError("Budget header not found.")

    status = (row[0] or "").strip().lower()
    if status != "draft":
        raise BudgetWorkflowError(
            f"Budget is not editable because its status is '{status}'. Only draft budgets can be changed."
        )


def submit_budget(header_id: int):
    session = _new_session()
    try:
        row = session.execute(text("""
            SELECT status
            FROM budget_headers
            WHERE id = :header_id
        """), {"header_id": header_id}).first()

        if not row:
            raise BudgetWorkflowError("Budget header not found.")

        status = (row[0] or "").strip().lower()
        if status == "approved":
            raise BudgetWorkflowError("Approved budget cannot be submitted again.")
        if status == "submitted":
            raise BudgetWorkflowError("Budget is already submitted.")

        session.execute(text("""
            UPDATE budget_headers
            SET status = 'submitted',
                submitted_at = CURRENT_TIMESTAMP
            WHERE id = :header_id
        """), {"header_id": header_id})
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def return_budget_to_draft(header_id: int):
    session = _new_session()
    try:
        row = session.execute(text("""
            SELECT status
            FROM budget_headers
            WHERE id = :header_id
        """), {"header_id": header_id}).first()

        if not row:
            raise BudgetWorkflowError("Budget header not found.")

        status = (row[0] or "").strip().lower()
        if status == "approved":
            raise BudgetWorkflowError("Approved budget cannot be returned to draft directly.")

        session.execute(text("""
            UPDATE budget_headers
            SET status = 'draft'
            WHERE id = :header_id
        """), {"header_id": header_id})
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def approve_budget(header_id: int):
    session = _new_session()
    try:
        row = session.execute(text("""
            SELECT fiscal_year_id, status
            FROM budget_headers
            WHERE id = :header_id
        """), {"header_id": header_id}).first()

        if not row:
            raise BudgetWorkflowError("Budget header not found.")

        fiscal_year_id, status = row
        status = (status or "").strip().lower()

        if status == "draft":
            raise BudgetWorkflowError("Submit the budget before approval.")
        if status == "approved":
            raise BudgetWorkflowError("Budget is already approved.")

        session.execute(text("""
            UPDATE budget_headers
            SET status = 'submitted'
            WHERE fiscal_year_id = :fiscal_year_id
              AND status = 'approved'
              AND id <> :header_id
        """), {
            "fiscal_year_id": fiscal_year_id,
            "header_id": header_id,
        })

        session.execute(text("""
            UPDATE budget_headers
            SET status = 'approved',
                approved_at = CURRENT_TIMESTAMP
            WHERE id = :header_id
        """), {"header_id": header_id})
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
