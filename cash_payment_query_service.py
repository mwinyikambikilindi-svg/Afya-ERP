from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext


def list_cash_payments(status=None, payment_type=None):
    sql_text = """
        SELECT
            cp.id,
            cp.payment_no,
            cp.payment_date,
            cp.payment_type,
            cp.reference_no,
            cp.narration,
            cp.status,
            b.code AS branch_code,
            b.name AS branch_name,
            s.code AS supplier_code,
            s.name AS supplier_name,
            ga.code AS cash_account_code,
            ga.name AS cash_account_name,
            COALESCE(SUM(cpl.amount), 0) AS total_amount
        FROM cash_payments cp
        JOIN branches b
            ON b.id = cp.branch_id
        JOIN gl_accounts ga
            ON ga.id = cp.cash_account_id
        LEFT JOIN suppliers s
            ON s.id = cp.supplier_id
        LEFT JOIN cash_payment_lines cpl
            ON cpl.cash_payment_id = cp.id
        WHERE 1=1
    """

    params = {}

    if status:
        sql_text += " AND cp.status = :status"
        params["status"] = status

    if payment_type:
        sql_text += " AND cp.payment_type = :payment_type"
        params["payment_type"] = payment_type

    sql_text += """
        GROUP BY
            cp.id, cp.payment_no, cp.payment_date, cp.payment_type,
            cp.reference_no, cp.narration, cp.status,
            b.code, b.name,
            s.code, s.name,
            ga.code, ga.name
        ORDER BY cp.payment_date DESC, cp.id DESC
    """

    with ext.engine.connect() as conn:
        rows = conn.execute(text(sql_text), params).mappings().all()

    return {
        "rows": [dict(row) for row in rows],
        "count": len(rows),
    }


def get_cash_payment_detail(payment_id: int):
    header_sql = text("""
        SELECT
            cp.id,
            cp.payment_no,
            cp.payment_date,
            cp.payment_type,
            cp.reference_no,
            cp.narration,
            cp.status,
            b.code AS branch_code,
            b.name AS branch_name,
            s.code AS supplier_code,
            s.name AS supplier_name,
            ga.code AS cash_account_code,
            ga.name AS cash_account_name
        FROM cash_payments cp
        JOIN branches b
            ON b.id = cp.branch_id
        JOIN gl_accounts ga
            ON ga.id = cp.cash_account_id
        LEFT JOIN suppliers s
            ON s.id = cp.supplier_id
        WHERE cp.id = :payment_id
    """)

    lines_sql = text("""
        SELECT
            cpl.id,
            exp.code AS expense_account_code,
            exp.name AS expense_account_name,
            cpl.description,
            cpl.amount
        FROM cash_payment_lines cpl
        JOIN gl_accounts exp
            ON exp.id = cpl.expense_account_id
        WHERE cpl.cash_payment_id = :payment_id
        ORDER BY cpl.id
    """)

    journal_sql = text("""
        SELECT
            jb.id,
            jb.batch_no,
            jb.status
        FROM journal_batches jb
        WHERE jb.source_module = 'CASH_PAYMENT'
          AND jb.reference_no = (
              SELECT payment_no
              FROM cash_payments
              WHERE id = :payment_id
          )
        ORDER BY jb.id DESC
        LIMIT 1
    """)

    with ext.engine.connect() as conn:
        header = conn.execute(header_sql, {"payment_id": payment_id}).mappings().first()
        if not header:
            return None

        lines = conn.execute(lines_sql, {"payment_id": payment_id}).mappings().all()
        journal = conn.execute(journal_sql, {"payment_id": payment_id}).mappings().first()

    total_amount = sum(Decimal(row["amount"]) for row in lines)

    return {
        "header": dict(header),
        "lines": [dict(row) for row in lines],
        "journal": dict(journal) if journal else None,
        "total_amount": total_amount,
    }