from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext

from app.models.branch import Branch
from app.models.fiscal_year import FiscalYear
from app.services.journal_service import create_journal_draft, post_journal


class OpeningBalanceError(Exception):
    pass


def list_opening_balance_accounts():
    sql = text("""
        SELECT
            ga.id,
            ga.code,
            ga.name,
            ag.code AS group_code,
            ag.name AS group_name,
            ac.code AS class_code,
            ac.name AS class_name
        FROM gl_accounts ga
        JOIN account_groups ag
            ON ag.id = ga.account_group_id
        JOIN account_classes ac
            ON ac.id = ag.account_class_id
        WHERE ga.is_active = TRUE
          AND ga.account_type = 'posting'
          AND ac.code IN ('1000', '2000', '3000')
        ORDER BY ga.code
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def list_opening_balance_history():
    sql = text("""
        SELECT
            ob.id,
            fy.year_name,
            b.code AS branch_code,
            b.name AS branch_name,
            ob.opening_date,
            ob.status,
            ob.remarks,
            jb.id AS journal_id,
            jb.batch_no
        FROM opening_balance_batches ob
        JOIN fiscal_years fy
            ON fy.id = ob.fiscal_year_id
        JOIN branches b
            ON b.id = ob.branch_id
        JOIN journal_batches jb
            ON jb.id = ob.journal_batch_id
        ORDER BY ob.id DESC
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]


def create_opening_balances(
    fiscal_year_id: int,
    branch_id: int,
    opening_date,
    remarks: str | None,
    lines: list,
):
    session = ext.SessionLocal()

    try:
        fy = session.get(FiscalYear, fiscal_year_id)
        if not fy:
            raise OpeningBalanceError("Fiscal year haipo.")

        branch = session.get(Branch, branch_id)
        if not branch:
            raise OpeningBalanceError("Branch haipo.")

        if opening_date != fy.start_date:
            raise OpeningBalanceError("Opening date lazima iwe sawa na start date ya fiscal year.")

        existing = session.execute(
            text("""
                SELECT id
                FROM opening_balance_batches
                WHERE fiscal_year_id = :fiscal_year_id
                  AND branch_id = :branch_id
                LIMIT 1
            """),
            {
                "fiscal_year_id": fiscal_year_id,
                "branch_id": branch_id,
            }
        ).fetchone()

        if existing:
            raise OpeningBalanceError("Opening balances za branch hii kwenye fiscal year hii tayari ziliingizwa.")

        if not lines or len(lines) < 2:
            raise OpeningBalanceError("Opening balance lazima iwe na angalau lines mbili.")

        account_ids = [line["gl_account_id"] for line in lines]

        invalid_accounts = session.execute(
            text("""
                SELECT ga.code, ga.name
                FROM gl_accounts ga
                JOIN account_groups ag
                    ON ag.id = ga.account_group_id
                JOIN account_classes ac
                    ON ac.id = ag.account_class_id
                WHERE ga.id = ANY(:account_ids)
                  AND ac.code IN ('4000', '5000')
            """),
            {"account_ids": account_ids}
        ).fetchall()

        if invalid_accounts:
            raise OpeningBalanceError("Opening balances ziruhusiwe kwa Assets, Liabilities, na Equity tu.")

        batch_id = create_journal_draft(
            branch_id=branch_id,
            journal_date=opening_date,
            source_module="OPENING_BALANCE",
            reference_no=f"OB-{fiscal_year_id}-{branch_id}",
            narration=remarks or "Opening balances",
            lines=lines,
        )

        post_journal(batch_id)

        session.execute(
            text("""
                INSERT INTO opening_balance_batches (
                    fiscal_year_id,
                    branch_id,
                    opening_date,
                    journal_batch_id,
                    status,
                    remarks
                )
                VALUES (
                    :fiscal_year_id,
                    :branch_id,
                    :opening_date,
                    :journal_batch_id,
                    'posted',
                    :remarks
                )
            """),
            {
                "fiscal_year_id": fiscal_year_id,
                "branch_id": branch_id,
                "opening_date": opening_date,
                "journal_batch_id": batch_id,
                "remarks": remarks,
            }
        )
        session.commit()

        return batch_id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()