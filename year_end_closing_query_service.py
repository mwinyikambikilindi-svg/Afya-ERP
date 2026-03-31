from sqlalchemy import text
import app.extensions as ext


def list_year_end_closings():
    sql = text("""
        SELECT
            yec.id,
            fy.year_name,
            yec.closing_date,
            yec.status,
            yec.remarks,
            ga.code AS retained_account_code,
            ga.name AS retained_account_name,
            jb.id AS journal_id,
            jb.batch_no
        FROM year_end_closings yec
        JOIN fiscal_years fy
            ON fy.id = yec.fiscal_year_id
        JOIN gl_accounts ga
            ON ga.id = yec.retained_surplus_account_id
        JOIN journal_batches jb
            ON jb.id = yec.closing_journal_batch_id
        ORDER BY yec.id DESC
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]