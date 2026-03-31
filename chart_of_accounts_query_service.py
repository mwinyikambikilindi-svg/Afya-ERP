from sqlalchemy import text
import app.extensions as ext


def list_gl_accounts():
    sql = text("""
        SELECT
            ga.id,
            ga.code,
            ga.name,
            ga.account_type,
            ga.allow_manual_posting,
            ga.requires_subledger,
            ga.requires_cost_center,
            ga.requires_department,
            ga.is_control_account,
            ga.is_active,
            ag.code AS group_code,
            ag.name AS group_name,
            ac.code AS class_code,
            ac.name AS class_name
        FROM gl_accounts ga
        JOIN account_groups ag
            ON ag.id = ga.account_group_id
        JOIN account_classes ac
            ON ac.id = ag.account_class_id
        ORDER BY ga.code
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]