from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext

from app.services.journal_service import create_journal_draft, post_journal


class YearEndClosingError(Exception):
    pass


def run_year_end_closing(
    fiscal_year_id: int,
    closing_date,
    retained_surplus_account_id: int,
    branch_id: int,
    remarks: str | None = None,
):
    session = ext.SessionLocal()

    try:
        existing = session.execute(
            text("""
                SELECT id
                FROM year_end_closings
                WHERE fiscal_year_id = :fiscal_year_id
                LIMIT 1
            """),
            {"fiscal_year_id": fiscal_year_id},
        ).fetchone()

        if existing:
            raise YearEndClosingError("Fiscal year hii tayari imefanyiwa closing.")

        rows = session.execute(
            text("""
                SELECT
                    ga.id AS gl_account_id,
                    ac.code AS class_code,
                    CASE
                        WHEN ac.normal_balance = 'credit'
                            THEN COALESCE(SUM(jl.credit_amount), 0) - COALESCE(SUM(jl.debit_amount), 0)
                        ELSE
                            COALESCE(SUM(jl.debit_amount), 0) - COALESCE(SUM(jl.credit_amount), 0)
                    END AS amount
                FROM journal_lines jl
                JOIN journal_batches jb
                    ON jb.id = jl.journal_batch_id
                JOIN gl_accounts ga
                    ON ga.id = jl.gl_account_id
                JOIN account_groups ag
                    ON ag.id = ga.account_group_id
                JOIN account_classes ac
                    ON ac.id = ag.account_class_id
                JOIN fiscal_years fy
                    ON jb.journal_date BETWEEN fy.start_date AND fy.end_date
                WHERE jb.status = 'posted'
                  AND fy.id = :fiscal_year_id
                  AND ac.code IN ('4000', '5000')
                GROUP BY ga.id, ac.code, ac.normal_balance
                HAVING
                    CASE
                        WHEN ac.normal_balance = 'credit'
                            THEN COALESCE(SUM(jl.credit_amount), 0) - COALESCE(SUM(jl.debit_amount), 0)
                        ELSE
                            COALESCE(SUM(jl.debit_amount), 0) - COALESCE(SUM(jl.credit_amount), 0)
                    END <> 0
                ORDER BY ga.id
            """),
            {"fiscal_year_id": fiscal_year_id},
        ).mappings().all()

        if not rows:
            raise YearEndClosingError("Hakuna income/expense balances za kufunga kwenye fiscal year hii.")

        lines = []
        total_income = Decimal("0.00")
        total_expenses = Decimal("0.00")

        for row in rows:
            account_id = row["gl_account_id"]
            class_code = row["class_code"]
            amount = Decimal(row["amount"])

            if class_code == "4000":
                total_income += amount
                # close income by debiting it
                lines.append(
                    {
                        "gl_account_id": account_id,
                        "description": "Year-end closing of income account",
                        "debit_amount": amount,
                        "credit_amount": Decimal("0.00"),
                    }
                )
            elif class_code == "5000":
                total_expenses += amount
                # close expense by crediting it
                lines.append(
                    {
                        "gl_account_id": account_id,
                        "description": "Year-end closing of expense account",
                        "debit_amount": Decimal("0.00"),
                        "credit_amount": amount,
                    }
                )

        net_result = total_income - total_expenses

        if net_result > 0:
            # surplus -> credit retained surplus
            lines.append(
                {
                    "gl_account_id": retained_surplus_account_id,
                    "description": "Transfer of current year surplus to retained surplus",
                    "debit_amount": Decimal("0.00"),
                    "credit_amount": net_result,
                }
            )
        elif net_result < 0:
            # deficit -> debit retained surplus
            lines.append(
                {
                    "gl_account_id": retained_surplus_account_id,
                    "description": "Transfer of current year deficit to retained surplus",
                    "debit_amount": abs(net_result),
                    "credit_amount": Decimal("0.00"),
                }
            )
        else:
            raise YearEndClosingError("Net result ni zero; hakuna closing balance ya kuhamisha.")

        batch_id = create_journal_draft(
            branch_id=branch_id,
            journal_date=closing_date,
            source_module="YEAR_END_CLOSING",
            reference_no=f"YEC-{fiscal_year_id}",
            narration=remarks or "Year-end closing entry",
            lines=lines,
        )

        post_journal(batch_id)

        session.execute(
            text("""
                INSERT INTO year_end_closings (
                    fiscal_year_id,
                    closing_date,
                    retained_surplus_account_id,
                    closing_journal_batch_id,
                    status,
                    remarks
                )
                VALUES (
                    :fiscal_year_id,
                    :closing_date,
                    :retained_surplus_account_id,
                    :closing_journal_batch_id,
                    'posted',
                    :remarks
                )
            """),
            {
                "fiscal_year_id": fiscal_year_id,
                "closing_date": closing_date,
                "retained_surplus_account_id": retained_surplus_account_id,
                "closing_journal_batch_id": batch_id,
                "remarks": remarks,
            }
        )
        session.commit()

        return {
            "closing_journal_batch_id": batch_id,
            "net_result": net_result,
            "total_income": total_income,
            "total_expenses": total_expenses,
        }

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()