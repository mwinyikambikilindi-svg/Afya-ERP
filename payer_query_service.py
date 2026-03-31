from sqlalchemy import text
import app.extensions as ext


def list_payers():
    sql = text("""
        SELECT
            p.id,
            p.code,
            p.name,
            p.phone,
            p.email,
            p.contact_person,
            p.tin,
            p.is_active,
            pt.code AS payer_type_code,
            pt.name AS payer_type_name
        FROM payers p
        JOIN payer_types pt
            ON pt.id = p.payer_type_id
        ORDER BY p.name
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]