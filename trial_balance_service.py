from datetime import datetime
from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext


def get_trial_balance(as_of_date=None):
    if isinstance(as_of_date, str):
        as_of_date = as_of_date.strip()
        if as_of_date:
            as_of_date = datetime.strptime(as_of_date, "%Y-%m-%d").date()
        else:
            as_of_date = None

    sql_text = """
        SELECT
            ac.code AS class_code,
            ac.name AS class_name,
            ga.code AS account_code,
            ga.name AS account_name,
            COALESCE(SUM(jl.debit_amount), 0) AS total_debit,
            COALESCE(SUM(jl.credit_amount), 0) AS total_credit,
            CASE
                WHEN ac.normal_balance = 'debit'
                    THEN COALESCE(SUM(jl.debit_amount), 0) - COALESCE(SUM(jl.credit_amount), 0)
                ELSE
                    COALESCE(SUM(jl.credit_amount), 0) - COALESCE(SUM(jl.debit_amount), 0)
            END AS balance
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
    """

    params = {}

    if as_of_date is not None:
        sql_text += " AND jb.journal_date <= :as_of_date"
        params["as_of_date"] = as_of_date

    sql_text += """
        GROUP BY
            ac.code, ac.name, ac.normal_balance,
            ga.code, ga.name
        ORDER BY ga.code
    """

    sql = text(sql_text)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    total_debit = sum(Decimal(row["total_debit"]) for row in rows)
    total_credit = sum(Decimal(row["total_credit"]) for row in rows)

    return {
        "rows": [dict(row) for row in rows],
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "is_balanced": total_debit == total_credit,
    }