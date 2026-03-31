from sqlalchemy import text
import app.extensions as ext


def list_suppliers():
    sql = text("""
        SELECT
            s.id,
            s.code,
            s.name,
            s.tin,
            s.vrn,
            s.phone,
            s.email,
            s.contact_person,
            s.is_active,
            sc.code AS supplier_category_code,
            sc.name AS supplier_category_name
        FROM suppliers s
        LEFT JOIN supplier_categories sc
            ON sc.id = s.supplier_category_id
        ORDER BY s.name
    """)

    with ext.engine.connect() as conn:
        rows = conn.execute(sql).mappings().all()

    return [dict(row) for row in rows]