from sqlalchemy import text
from app import create_app
import app.extensions as ext

app = create_app()

data = [
    ("1100", "Current Assets", "1000"),
    ("1200", "Non Current Assets", "1000"),
    ("2100", "Current Liabilities", "2000"),
    ("2200", "Non Current Liabilities", "2000"),
    ("3100", "Capital and Reserves", "3000"),
    ("4100", "Operating Income", "4000"),
    ("4200", "Non Operating Income", "4000"),
    ("5100", "Direct Costs", "5000"),
    ("5200", "Administrative Expenses", "5000"),
    ("5300", "Finance and Other Expenses", "5000"),
]

sql = text("""
    INSERT INTO account_groups (account_class_id, parent_id, code, name)
    VALUES (
        (SELECT id FROM account_classes WHERE code = :class_code),
        NULL,
        :code,
        :name
    )
    ON CONFLICT (code) DO NOTHING
""")

with app.app_context():
    with ext.engine.connect() as conn:
        for code, name, class_code in data:
            conn.execute(
                sql,
                {
                    "code": code,
                    "name": name,
                    "class_code": class_code,
                }
            )
        conn.commit()

print("Account groups inserted successfully.")