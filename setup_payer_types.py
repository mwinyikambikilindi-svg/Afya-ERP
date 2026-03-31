from sqlalchemy import text
from app import create_app
import app.extensions as ext

app = create_app()

data = [
    ("CASH", "Cash Clients"),
    ("NHIF", "NHIF"),
    ("CHIF", "CHIF/ZHIF"),
    ("STUDENT", "Students"),
    ("CHURCH", "Church"),
    ("GRANT", "Grant Donors"),
    ("OTHER", "Other Payers"),
]

sql = text("""
    INSERT INTO payer_types (code, name, is_active)
    VALUES (:code, :name, TRUE)
    ON CONFLICT (code) DO NOTHING
""")

with app.app_context():
    with ext.engine.connect() as conn:
        for code, name in data:
            conn.execute(sql, {"code": code, "name": name})
        conn.commit()

print("Payer types inserted successfully.")