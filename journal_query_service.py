from decimal import Decimal
from sqlalchemy import text
import app.extensions as ext


def list_journals(status=None, source_module=None):
    sql_text = """
        SELECT
            jb.id,
            jb.batch_no,
            jb.journal_date,
            jb.source_module,
            jb.reference_no,
            jb.narration,
            jb.status,
            b.code AS branch_code,
            b.name AS branch_name,
            COALESCE(SUM(jl.debit_amount), 0) AS total_debit,
            COALESCE(SUM(jl.credit_amount), 0) AS total_credit
        FROM journal_batches jb
        JOIN branches b
            ON b.id = jb.branch_id
        LEFT JOIN journal_lines jl
            ON jl.journal_batch_id = jb.id
        WHERE 1=1
    """

    params = {}

    if status:
        sql_text += " AND jb.status = :status"
        params["status"] = status

    if source_module:
        sql_text += " AND jb.source_module = :source_module"
        params["source_module"] = source_module

    sql_text += """
        GROUP BY
            jb.id, jb.batch_no, jb.journal_date, jb.source_module,
            jb.reference_no, jb.narration, jb.status,
            b.code, b.name
        ORDER BY jb.journal_date DESC, jb.id DESC
    """

    with ext.engine.connect() as conn:
        rows = conn.execute(text(sql_text), params).mappings().all()

    return {
        "rows": [dict(row) for row in rows],
        "count": len(rows),
    }


def get_journal_detail(batch_id: int):
    header_sql = text("""
        SELECT
            jb.id,
            jb.batch_no,
            jb.journal_date,
            jb.source_module,
            jb.reference_no,
            jb.narration,
            jb.status,
            b.code AS branch_code,
            b.name AS branch_name
        FROM journal_batches jb
        JOIN branches b
            ON b.id = jb.branch_id
        WHERE jb.id = :batch_id
    """)

    lines_sql = text("""
        SELECT
            jl.id,
            ga.code AS account_code,
            ga.name AS account_name,
            jl.description,
            jl.debit_amount,
            jl.credit_amount
        FROM journal_lines jl
        JOIN gl_accounts ga
            ON ga.id = jl.gl_account_id
        WHERE jl.journal_batch_id = :batch_id
        ORDER BY jl.id
    """)

    with ext.engine.connect() as conn:
        header = conn.execute(header_sql, {"batch_id": batch_id}).mappings().first()
        if not header:
            return None

        lines = conn.execute(lines_sql, {"batch_id": batch_id}).mappings().all()

    total_debit = sum(Decimal(row["debit_amount"]) for row in lines)
    total_credit = sum(Decimal(row["credit_amount"]) for row in lines)

    return {
        "header": dict(header),
        "lines": [dict(row) for row in lines],
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": total_debit == total_credit,
    }