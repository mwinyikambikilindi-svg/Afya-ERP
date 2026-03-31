from sqlalchemy import text
from app import create_app
import app.extensions as ext

app = create_app()

data = [
    ("1000", "Assets", "debit"),
    ("2000", "Liabilities", "credit"),
    ("3000", "Equity", "credit"),
    ("4000", "Income", "credit"),
    ("5000", "Expenses", "debit"),
]

with app.app_context():
    with ext.engine.connect() as conn:
        for code, name, normal_balance in data:
            conn.execute(
                text("""
                    INSERT INTO account_classes (code, name, normal_balance)
                    VALUES (:code, :name, :normal_balance)
                    ON CONFLICT (code) DO NOTHING
                """),
                {
                    "code": code,
                    "name": name,
                    "normal_balance": normal_balance
                }
            )
        conn.commit()

print("Account classes inserted successfully.")