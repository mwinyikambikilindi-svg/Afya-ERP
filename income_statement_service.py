from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext


def get_income_statement(date_from=None, date_to=None):
    if isinstance(date_from, str):
        date_from = date_from.strip()
        date_from = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else None

    if isinstance(date_to, str):
        date_to = date_to.strip()
        date_to = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else None

    sql_text = """
        SELECT
            ac.code AS class_code,
            ac.name AS class_name,
            ag.code AS group_code,
            ag.name AS group_name,
            ga.code AS account_code,
            ga.name AS account_name,
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

    params = {}

    if date_from is not None:
        sql_text += " AND jb.journal_date >= :date_from"
        params["date_from"] = date_from

    if date_to is not None:
        sql_text += " AND jb.journal_date <= :date_to"
        params["date_to"] = date_to

    sql_text += """
        GROUP BY
            ac.code, ac.name,
            ag.code, ag.name,
            ga.code, ga.name,
            ac.normal_balance
        HAVING
            CASE
                WHEN ac.normal_balance = 'credit'
                    THEN COALESCE(SUM(jl.credit_amount), 0) - COALESCE(SUM(jl.debit_amount), 0)
                ELSE
                    COALESCE(SUM(jl.debit_amount), 0) - COALESCE(SUM(jl.credit_amount), 0)
            END <> 0
        ORDER BY ga.code
    """

    with ext.engine.connect() as conn:
        rows = conn.execute(text(sql_text), params).mappings().all()

    income_rows = []
    expense_rows = []

    total_income = Decimal("0.00")
    total_expenses = Decimal("0.00")

    for row in rows:
        item = dict(row)
        item["amount"] = Decimal(item["amount"])

        if item["class_code"] == "4000":
            income_rows.append(item)
            total_income += item["amount"]
        elif item["class_code"] == "5000":
            expense_rows.append(item)
            total_expenses += item["amount"]

    surplus_deficit = total_income - total_expenses

    return {
        "income_rows": income_rows,
        "expense_rows": expense_rows,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "surplus_deficit": surplus_deficit,
        "date_from": date_from,
        "date_to": date_to,
    }