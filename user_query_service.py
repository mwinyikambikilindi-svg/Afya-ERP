from sqlalchemy import text
import app.extensions as ext


def list_users():
    sql = text("""
        SELECT
            u.id,
            u.full_name,
            u.username,
            u.email,
            u.phone,
            u.is_active,
            r.name AS role_name,
            b.code AS branch_code,
            b.name AS branch_name
        FROM users u
        JOIN roles r
            ON r.id = u.role_id
        LEFT JOIN branches b
            ON b.id = u.branch_id
        ORDER BY u.full_name
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]