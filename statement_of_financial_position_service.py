from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext


def get_statement_of_financial_position(as_of_date=None):
    if isinstance(as_of_date, str):
        as_of_date = as_of_date.strip()
        as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d").date() if as_of_date else None

    sql_text = """
        SELECT
            ac.code AS class_code,
            ac.name AS class_name,
            ag.code AS group_code,
            ag.name AS group_name,
            ga.code AS account_code,
            ga.name AS account_name,
            CASE
                WHEN ac.normal_balance = 'debit'
                    THEN COALESCE(SUM(jl.debit_amount), 0) - COALESCE(SUM(jl.credit_amount), 0)
                ELSE
                    COALESCE(SUM(jl.credit_amount), 0) - COALESCE(SUM(jl.debit_amount), 0)
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
        WHERE jb.status = 'posted'
          AND ac.code IN ('1000', '2000', '3000')
    """

    params = {}

    if as_of_date is not None:
        sql_text += " AND jb.journal_date <= :as_of_date"
        params["as_of_date"] = as_of_date

    sql_text += """
        GROUP BY
            ac.code, ac.name,
            ag.code, ag.name,
            ga.code, ga.name,
            ac.normal_balance
        HAVING
            CASE
                WHEN ac.normal_balance = 'debit'
                    THEN COALESCE(SUM(jl.debit_amount), 0) - COALESCE(SUM(jl.credit_amount), 0)
                ELSE
                    COALESCE(SUM(jl.credit_amount), 0) - COALESCE(SUM(jl.debit_amount), 0)
            END <> 0
        ORDER BY ga.code
    """

    pnl_sql = """
        SELECT
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
        WHERE jb.status = 'posted'
          AND ac.code IN ('4000', '5000')
    """

    pnl_params = {}

    if as_of_date is not None:
        pnl_sql += " AND jb.journal_date <= :as_of_date"
        pnl_params["as_of_date"] = as_of_date

    pnl_sql += """
        GROUP BY ac.code, ac.normal_balance
    """

    with ext.engine.connect() as conn:
        rows = conn.execute(text(sql_text), params).mappings().all()
        pnl_rows = conn.execute(text(pnl_sql), pnl_params).mappings().all()

    asset_rows = []
    liability_rows = []
    equity_rows = []

    total_assets = Decimal("0.00")
    total_liabilities = Decimal("0.00")
    total_equity = Decimal("0.00")

    for row in rows:
        item = dict(row)
        item["amount"] = Decimal(item["amount"])

        if item["class_code"] == "1000":
            asset_rows.append(item)
            total_assets += item["amount"]
        elif item["class_code"] == "2000":
            liability_rows.append(item)
            total_liabilities += item["amount"]
        elif item["class_code"] == "3000":
            equity_rows.append(item)
            total_equity += item["amount"]

    total_income = Decimal("0.00")
    total_expenses = Decimal("0.00")

    for row in pnl_rows:
        amount = Decimal(row["amount"])
        if row["class_code"] == "4000":
            total_income += amount
        elif row["class_code"] == "5000":
            total_expenses += amount

    current_period_result = total_income - total_expenses
    total_equity_and_result = total_equity + current_period_result
    is_balanced = total_assets == (total_liabilities + total_equity_and_result)

    return {
        "asset_rows": asset_rows,
        "liability_rows": liability_rows,
        "equity_rows": equity_rows,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "current_period_result": current_period_result,
        "total_equity_and_result": total_equity_and_result,
        "is_balanced": is_balanced,
        "as_of_date": as_of_date,
    }