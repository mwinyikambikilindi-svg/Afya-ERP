from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash
import app.extensions as ext


class ProfileServiceError(Exception):
    pass


def get_user_profile(user_id: int):
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
        WHERE u.id = :user_id
        LIMIT 1
    """)

    with ext.engine.connect() as conn:
        row = conn.execute(sql, {"user_id": user_id}).mappings().first()

    return dict(row) if row else None


def change_user_password(user_id: int, current_password: str, new_password: str, confirm_password: str):
    if not current_password:
        raise ProfileServiceError("Weka current password.")

    if not new_password:
        raise ProfileServiceError("Weka new password.")

    if len(new_password) < 8:
        raise ProfileServiceError("New password lazima iwe na angalau characters 8.")

    if new_password != confirm_password:
        raise ProfileServiceError("New password na confirm password hazifanani.")

    sql_get = text("""
        SELECT id, password_hash
        FROM users
        WHERE id = :user_id
        LIMIT 1
    """)

    sql_update = text("""
        UPDATE users
        SET password_hash = :password_hash
        WHERE id = :user_id
    """)

    with ext.engine.connect() as conn:
        user = conn.execute(sql_get, {"user_id": user_id}).mappings().first()

        if not user:
            raise ProfileServiceError("User haipo.")

        if not check_password_hash(user["password_hash"], current_password):
            raise ProfileServiceError("Current password si sahihi.")

        conn.execute(
            sql_update,
            {
                "user_id": user_id,
                "password_hash": generate_password_hash(new_password),
            }
        )
        conn.commit()