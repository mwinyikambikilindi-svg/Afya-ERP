from sqlalchemy import text
from app import create_app
import app.extensions as ext

app = create_app()

data = [
    ("ADMIN", "System administrator"),
    ("ACCOUNTANT", "Accounting operations user"),
    ("MANAGER", "Management and approvals"),
    ("AUDITOR", "Read-only audit user"),
]

sql = text("""
    INSERT INTO roles (name, description, is_active)
    VALUES (:name, :description, TRUE)
    ON CONFLICT (name) DO NOTHING
""")

with app.app_context():
    with ext.engine.connect() as conn:
        for name, description in data:
            conn.execute(sql, {"name": name, "description": description})
        conn.commit()

print("Roles inserted successfully.")