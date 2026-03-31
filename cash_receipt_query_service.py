from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext


def list_cash_receipts(status=None, receipt_type=None):
    sql_text = """
        SELECT
            cr.id,
            cr.receipt_no,
            cr.receipt_date,
            cr.receipt_type,
            cr.reference_no,
            cr.narration,
            cr.status,
            b.code AS branch_code,
            b.name AS branch_name,
            p.code AS payer_code,
            p.name AS payer_name,
            ga.code AS cash_account_code,
            ga.name AS cash_account_name,
            COALESCE(SUM(crl.amount), 0) AS total_amount
        FROM cash_receipts cr
        JOIN branches b
            ON b.id = cr.branch_id
        JOIN gl_accounts ga
            ON ga.id = cr.cash_account_id
        LEFT JOIN payers p
            ON p.id = cr.payer_id
        LEFT JOIN cash_receipt_lines crl
            ON crl.cash_receipt_id = cr.id
        WHERE 1=1
    """

    params = {}

    if status:
        sql_text += " AND cr.status = :status"
        params["status"] = status

    if receipt_type:
        sql_text += " AND cr.receipt_type = :receipt_type"
        params["receipt_type"] = receipt_type

    sql_text += """
        GROUP BY
            cr.id, cr.receipt_no, cr.receipt_date, cr.receipt_type,
            cr.reference_no, cr.narration, cr.status,
            b.code, b.name,
            p.code, p.name,
            ga.code, ga.name
        ORDER BY cr.receipt_date DESC, cr.id DESC
    """

    with ext.engine.connect() as conn:
        rows = conn.execute(text(sql_text), params).mappings().all()

    return {
        "rows": [dict(row) for row in rows],
        "count": len(rows),
    }


def get_cash_receipt_detail(receipt_id: int):
    header_sql = text("""
        SELECT
            cr.id,
            cr.receipt_no,
            cr.receipt_date,
            cr.receipt_type,
            cr.reference_no,
            cr.narration,
            cr.status,
            b.code AS branch_code,
            b.name AS branch_name,
            p.code AS payer_code,
            p.name AS payer_name,
            ga.code AS cash_account_code,
            ga.name AS cash_account_name
        FROM cash_receipts cr
        JOIN branches b
            ON b.id = cr.branch_id
        JOIN gl_accounts ga
            ON ga.id = cr.cash_account_id
        LEFT JOIN payers p
            ON p.id = cr.payer_id
        WHERE cr.id = :receipt_id
    """)

    lines_sql = text("""
        SELECT
            crl.id,
            rev.code AS revenue_account_code,
            rev.name AS revenue_account_name,
            crl.description,
            crl.amount
        FROM cash_receipt_lines crl
        JOIN gl_accounts rev
            ON rev.id = crl.revenue_account_id
        WHERE crl.cash_receipt_id = :receipt_id
        ORDER BY crl.id
    """)

    journal_sql = text("""
        SELECT
            jb.id,
            jb.batch_no,
            jb.status
        FROM journal_batches jb
        WHERE jb.source_module = 'CASH_RECEIPT'
          AND jb.reference_no = (
              SELECT receipt_no
              FROM cash_receipts
              WHERE id = :receipt_id
          )
        ORDER BY jb.id DESC
        LIMIT 1
    """)

    with ext.engine.connect() as conn:
        header = conn.execute(header_sql, {"receipt_id": receipt_id}).mappings().first()
        if not header:
            return None

        lines = conn.execute(lines_sql, {"receipt_id": receipt_id}).mappings().all()
        journal = conn.execute(journal_sql, {"receipt_id": receipt_id}).mappings().first()

    total_amount = sum(Decimal(row["amount"]) for row in lines)

    return {
        "header": dict(header),
        "lines": [dict(row) for row in lines],
        "journal": dict(journal) if journal else None,
        "total_amount": total_amount,
    }