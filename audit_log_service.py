from sqlalchemy import text
import app.extensions as ext


def log_audit_event(
    user_id=None,
    module_name="GENERAL",
    record_table=None,
    record_id=None,
    action_name="ACTION",
    details=None,
):
    sql = text("""
        INSERT INTO audit_logs (
            user_id,
            module_name,
            record_table,
            record_id,
            action_name,
            details,
            created_at
        )
        VALUES (
            :user_id,
            :module_name,
            :record_table,
            :record_id,
            :action_name,
            :details,
            NOW()
        )
    """)

    with ext.engine.connect() as conn:
        conn.execute(
            sql,
            {
                "user_id": user_id,
                "module_name": module_name,
                "record_table": record_table,
                "record_id": record_id,
                "action_name": action_name,
                "details": details,
            }
        )
        conn.commit()


def list_audit_logs():
    sql = text("""
        SELECT
            al.id,
            al.module_name,
            al.record_table,
            al.record_id,
            al.action_name,
            al.details,
            al.created_at,
            u.username,
            u.full_name
        FROM audit_logs al
        LEFT JOIN users u
            ON u.id = al.user_id
        ORDER BY al.id DESC
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]