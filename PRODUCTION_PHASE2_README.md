# Production Hardening Phase 2

## Files to replace/add
- `app/__init__.py`
- `app/config.py`
- `app/extensions.py`
- `app/logging_config.py` (new)
- `serve_waitress.py` (new)
- `wsgi.py` (new)
- `.env.example` (reference only)
- `requirements-phase2.txt` (install additions)

## What this phase does
- Validates environment before app startup.
- Adds production-safe config flags.
- Adds rotating application/error logs.
- Keeps `create_all_tables()` available for development, but disables it by default in production.
- Adds Waitress entrypoint for non-debug serving.

## Recommended order
1. Backup project and database.
2. Replace/add the files above.
3. Create a real `.env` from `.env.example`.
4. Install new requirements.
5. Start with `python serve_waitress.py` for production-like serving.

## Important
- Keep `AUTO_CREATE_TABLES=1` only in development/testing.
- Set `AUTO_CREATE_TABLES=0` in production after your schema is stable.
- Use a strong `SECRET_KEY` in production.
- Do not use `python run.py` for internet-facing deployment.
