from sqlalchemy import text
from werkzeug.security import generate_password_hash
from app import create_app
import app.extensions as ext

app = create_app()

FULL_NAME = "System Administrator"
USERNAME = "admin"
EMAIL = "admin@afyaerp.local"
PHONE = ""
ROLE_NAME = "ADMIN"
BRANCH_CODE = "HQ"
PASSWORD = "Admin12345"

with app.app_context():
    with ext.engine.connect() as conn:
        role = conn.execute(
            text("SELECT id FROM roles WHERE name = :name"),
            {"name": ROLE_NAME}
        ).fetchone()

        if not role:
            raise Exception("Role ya ADMIN haipo. Run setup_roles.py kwanza.")

        branch = conn.execute(
            text("SELECT id FROM branches WHERE code = :code"),
            {"code": BRANCH_CODE}
        ).fetchone()

        if not branch:
            raise Exception("Branch ya HQ haipo. Hakikisha branch yako ipo.")

        conn.execute(
            text("""
                INSERT INTO users (
                    full_name, username, email, phone,
                    password_hash, role_id, branch_id, is_active
                )
                VALUES (
                    :full_name, :username, :email, :phone,
                    :password_hash, :role_id, :branch_id, TRUE
                )
                ON CONFLICT (username) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    password_hash = EXCLUDED.password_hash,
                    role_id = EXCLUDED.role_id,
                    branch_id = EXCLUDED.branch_id,
                    is_active = EXCLUDED.is_active
            """),
            {
                "full_name": FULL_NAME,
                "username": USERNAME,
                "email": EMAIL,
                "phone": PHONE,
                "password_hash": generate_password_hash(PASSWORD),
                "role_id": role[0],
                "branch_id": branch[0],
            }
        )
        conn.commit()

print("Admin user created/updated successfully.")