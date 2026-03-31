from __future__ import annotations

from typing import Any

from sqlalchemy import text

import app.extensions as ext


class FacilityServiceError(Exception):
    pass


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized.")
    return ext.SessionLocal()


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    return v or None


def _get_columns(session) -> set[str]:
    rows = session.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'branches'
    """)).fetchall()
    return {r[0] for r in rows}


def list_facilities():
    session = _new_session()
    try:
        cols = _get_columns(session)

        select_parts = ["id"]
        select_parts.append("code AS facility_code" if "code" in cols else "'' AS facility_code")
        select_parts.append("name AS facility_name" if "name" in cols else "'' AS facility_name")
        select_parts.append("'' AS facility_type")
        select_parts.append("location AS region" if "location" in cols else "'' AS region")
        select_parts.append("location AS district" if "location" in cols else "'' AS district")
        select_parts.append("COALESCE(is_active, true) AS is_active" if "is_active" in cols else "true AS is_active")
        select_parts.append("organization_id" if "organization_id" in cols else "NULL::integer AS organization_id")

        sql = f"""
            SELECT {", ".join(select_parts)}
            FROM branches
            ORDER BY name
        """

        rows = session.execute(text(sql)).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


def create_facility(
    facility_code: str | None,
    facility_name: str,
    facility_type: str | None,
    region: str | None,
    district: str | None,
    organization_id: int | None = None,
):
    session = _new_session()
    try:
        cols = _get_columns(session)

        payload = {}
        ordered = []

        if "organization_id" in cols:
            payload["organization_id"] = organization_id if organization_id is not None else 1
            ordered.append("organization_id")

        if "code" in cols:
            payload["code"] = _clean(facility_code)
            ordered.append("code")

        if "name" in cols:
            payload["name"] = _clean(facility_name)
            ordered.append("name")
        else:
            raise FacilityServiceError("Branches table haina column ya name.")

        if "location" in cols:
            # tunatumia region kama primary location field kwa sasa
            payload["location"] = _clean(region) or _clean(district)
            ordered.append("location")

        if "is_active" in cols:
            payload["is_active"] = True
            ordered.append("is_active")

        sql = f"""
            INSERT INTO branches ({", ".join(ordered)})
            VALUES ({", ".join(":" + c for c in ordered)})
        """
        session.execute(text(sql), payload)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_facility(facility_pk: int):
    session = _new_session()
    try:
        cols = _get_columns(session)

        sql = f"""
            SELECT
                id,
                {"code AS facility_code" if "code" in cols else "'' AS facility_code"},
                {"name AS facility_name" if "name" in cols else "'' AS facility_name"},
                '' AS facility_type,
                {"location AS region" if "location" in cols else "'' AS region"},
                {"location AS district" if "location" in cols else "'' AS district"},
                {"organization_id" if "organization_id" in cols else "NULL::integer AS organization_id"},
                {"COALESCE(is_active, true) AS is_active" if "is_active" in cols else "true AS is_active"}
            FROM branches
            WHERE id = :id
        """
        row = session.execute(text(sql), {"id": facility_pk}).mappings().first()
        return dict(row) if row else None
    finally:
        session.close()


def update_facility(
    facility_pk: int,
    facility_code: str | None,
    facility_name: str,
    facility_type: str | None,
    region: str | None,
    district: str | None,
    organization_id: int | None = None,
):
    session = _new_session()
    try:
        cols = _get_columns(session)

        updates = []
        payload = {"id": facility_pk}

        if "organization_id" in cols and organization_id is not None:
            updates.append("organization_id = :organization_id")
            payload["organization_id"] = organization_id

        if "code" in cols:
            updates.append("code = :code")
            payload["code"] = _clean(facility_code)

        if "name" in cols:
            updates.append("name = :name")
            payload["name"] = _clean(facility_name)
        else:
            raise FacilityServiceError("Branches table haina column ya name.")

        if "location" in cols:
            updates.append("location = :location")
            payload["location"] = _clean(region) or _clean(district)

        sql = f"""
            UPDATE branches
            SET {", ".join(updates)}
            WHERE id = :id
        """
        session.execute(text(sql), payload)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_facility(facility_pk: int):
    session = _new_session()
    try:
        cols = _get_columns(session)

        # safer approach: if is_active exists, deactivate instead of hard delete
        if "is_active" in cols:
            session.execute(
                text("UPDATE branches SET is_active = false WHERE id = :id"),
                {"id": facility_pk},
            )
        else:
            session.execute(
                text("DELETE FROM branches WHERE id = :id"),
                {"id": facility_pk},
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()