from functools import wraps
from flask import session, redirect, url_for, render_template
from sqlalchemy import text
from werkzeug.security import check_password_hash
import app.extensions as ext


def authenticate_user(username: str, password: str):
    sql = text("""
        SELECT
            u.id,
            u.full_name,
            u.username,
            u.password_hash,
            u.is_active,
            r.name AS role_name,
            b.code AS branch_code,
            b.name AS branch_name
        FROM users u
        JOIN roles r
            ON r.id = u.role_id
        LEFT JOIN branches b
            ON b.id = u.branch_id
        WHERE u.username = :username
        LIMIT 1
    """)

    with ext.engine.connect() as conn:
        user = conn.execute(sql, {"username": username}).mappings().first()

    if not user:
        return None

    if not user["is_active"]:
        return None

    if not check_password_hash(user["password_hash"], password):
        return None

    return dict(user)


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapper


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))

            role_name = session.get("role_name")
            if role_name not in allowed_roles:
                return render_template(
                    "forbidden.html",
                    allowed_roles=allowed_roles,
                    current_role=role_name,
                ), 403

            return view_func(*args, **kwargs)
        return wrapper
    return decorator