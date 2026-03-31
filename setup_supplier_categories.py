from sqlalchemy import text
from app import create_app
import app.extensions as ext

app = create_app()

data = [
    ("DRUGS", "Drug Suppliers"),
    ("MEDICAL", "Medical Supplies Suppliers"),
    ("REAGENTS", "Reagents Suppliers"),
    ("SERVICES", "Service Providers"),
    ("UTILITIES", "Utilities"),
    ("OTHER", "Other Suppliers"),
]

sql = text("""
    INSERT INTO supplier_categories (code, name, is_active)
    VALUES (:code, :name, TRUE)
    ON CONFLICT (code) DO NOTHING
""")

with app.app_context():
    with ext.engine.connect() as conn:
        for code, name in data:
            conn.execute(sql, {"code": code, "name": name})
        conn.commit()

print("Supplier categories inserted successfully.")