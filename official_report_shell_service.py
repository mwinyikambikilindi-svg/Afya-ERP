from __future__ import annotations

from datetime import datetime
from sqlalchemy import text

import app.extensions as ext


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized.")
    return ext.SessionLocal()


def _get_columns(session, table_name: str) -> set[str]:
    rows = session.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
            ORDER BY ordinal_position
        """),
        {"table_name": table_name},
    ).fetchall()
    return {r[0] for r in rows}


def _pick_first_existing(columns: set[str], *candidates: str) -> str:
    for c in candidates:
        if c in columns:
            return c
    return ""


def _get_fiscal_year_name(session, fiscal_year_id: int | None) -> str:
    if not fiscal_year_id:
        return ""
    fy_cols = _get_columns(session, "fiscal_years")
    name_col = _pick_first_existing(fy_cols, "name", "year_name")
    if not name_col:
        return str(fiscal_year_id)
    row = session.execute(
        text(f"SELECT {name_col} AS name FROM fiscal_years WHERE id = :id"),
        {"id": fiscal_year_id},
    ).mappings().first()
    return str(row["name"]) if row else ""


def _resolve_facility_name(session, facility_id: int | None = None, branch_id: int | None = None) -> str:
    target_id = facility_id or branch_id
    if not target_id:
        return ""

    branch_cols = _get_columns(session, "branches")
    if branch_cols:
        name_col = _pick_first_existing(branch_cols, "name")
        if name_col:
            row = session.execute(
                text(f"SELECT {name_col} AS name FROM branches WHERE id = :id"),
                {"id": target_id},
            ).mappings().first()
            if row and row.get("name"):
                return str(row["name"])

    facility_cols = _get_columns(session, "facilities")
    if facility_cols:
        name_col = _pick_first_existing(facility_cols, "name", "facility_name")
        if name_col:
            row = session.execute(
                text(f"SELECT {name_col} AS name FROM facilities WHERE id = :id"),
                {"id": target_id},
            ).mappings().first()
            if row and row.get("name"):
                return str(row["name"])

    return ""


def build_official_shell_context(
    report_title: str,
    fiscal_year_id: int | None = None,
    facility_id: int | None = None,
    branch_id: int | None = None,
    period_label: str | None = None,
) -> dict:
    session = _new_session()
    try:
        facility_name = _resolve_facility_name(session, facility_id=facility_id, branch_id=branch_id)
        fiscal_year_name = _get_fiscal_year_name(session, fiscal_year_id)

        if period_label:
            resolved_period = period_label
        elif fiscal_year_name:
            resolved_period = f"FOR THE FISCAL YEAR / PERIOD {fiscal_year_name}"
        else:
            resolved_period = ""

        return {
            "header": {
                "country_line": "THE UNITED REPUBLIC OF TANZANIA",
                "vote_line": "VOTE 28 - MINISTRY OF HOME AFFAIRS",
                "subvote_line": "SUB VOTE 5001 - POLICE MEDICAL UNIT",
                "facility_line": facility_name or "",
                "report_title": report_title,
                "period_line": resolved_period,
                "currency_line": "Amounts are presented in Tanzanian Shillings (TZS)",
            },
            "footer": {
                "system_name": "AFYA ERP - Police Medical Unit",
                "generated_at": datetime.now().strftime("%d %b %Y %H:%M"),
            },
        }
    finally:
        session.close()
