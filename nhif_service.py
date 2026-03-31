from __future__ import annotations
from decimal import Decimal, InvalidOperation
from typing import Any
from sqlalchemy import text
import app.extensions as ext

class NHIFServiceError(Exception):
    pass

def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized.")
    return ext.SessionLocal()

def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text_value = str(value).strip()
    return text_value or None

def _to_decimal(value: Any) -> Decimal:
    try:
        if value in (None, ""):
            return Decimal("0.00")
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise NHIFServiceError("Amount lazima iwe namba sahihi.") from exc

def _get_table_columns(session, table_name: str) -> set[str]:
    rows = session.execute(
        text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
        """),
        {"table_name": table_name},
    ).fetchall()
    return {r[0] for r in rows}

def _pick_first_existing(columns: set[str], *candidates: str) -> str:
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return ""

def _get_claim_context(session, claim_id: int) -> dict:
    claim_cols = _get_table_columns(session, "nhif_claims")
    batch_col = _pick_first_existing(claim_cols, "batch_id")
    claimed_col = _pick_first_existing(claim_cols, "amount_claimed", "gross_amount")
    paid_col = _pick_first_existing(claim_cols, "amount_paid", "net_amount", "approved_amount")
    facility_col = _pick_first_existing(claim_cols, "facility_name", "facility")
    month_col = _pick_first_existing(claim_cols, "claim_month", "claim_period")
    ref_col = _pick_first_existing(claim_cols, "nhif_reference", "reference_no", "claim_no")
    select_parts = ["id"]
    select_parts.append(f"{batch_col} AS batch_id" if batch_col else "NULL::integer AS batch_id")
    select_parts.append(f"COALESCE({claimed_col}, 0) AS amount_claimed" if claimed_col else "0 AS amount_claimed")
    select_parts.append(f"COALESCE({paid_col}, 0) AS amount_paid" if paid_col else "0 AS amount_paid")
    select_parts.append(f"COALESCE({facility_col}, '') AS facility_name" if facility_col else "'' AS facility_name")
    select_parts.append(f"COALESCE({month_col}, '') AS claim_month" if month_col else "'' AS claim_month")
    select_parts.append(f"COALESCE({ref_col}, '') AS nhif_reference" if ref_col else "'' AS nhif_reference")
    sql = f"SELECT {', '.join(select_parts)} FROM nhif_claims WHERE id = :claim_id"
    row = session.execute(text(sql), {"claim_id": claim_id}).mappings().first()
    if not row:
        raise NHIFServiceError("NHIF claim haipo.")
    return dict(row)

def list_nhif_claims():
    session = _new_session()
    try:
        claim_cols = _get_table_columns(session, "nhif_claims")
        import_cols = _get_table_columns(session, "nhif_import_batches")
        facility_col = _pick_first_existing(claim_cols, "facility_name", "facility")
        month_col = _pick_first_existing(claim_cols, "claim_month", "claim_period")
        ref_col = _pick_first_existing(claim_cols, "nhif_reference", "reference_no", "claim_no")
        claimed_col = _pick_first_existing(claim_cols, "amount_claimed", "gross_amount")
        paid_col = _pick_first_existing(claim_cols, "amount_paid", "net_amount", "approved_amount")
        status_col = _pick_first_existing(claim_cols, "status")
        adjudication_col = _pick_first_existing(claim_cols, "adjudication_status")
        import_batch_col = _pick_first_existing(claim_cols, "import_batch_id")
        source_filename_col = _pick_first_existing(import_cols, "source_filename")
        select_parts = ["c.id"]
        select_parts.append(f"COALESCE(c.{facility_col}, '') AS facility_name" if facility_col else "'' AS facility_name")
        select_parts.append(f"COALESCE(c.{month_col}, '') AS claim_month" if month_col else "'' AS claim_month")
        select_parts.append(f"COALESCE(c.{ref_col}, '') AS nhif_reference" if ref_col else "'' AS nhif_reference")
        select_parts.append("c.claim_date" if "claim_date" in claim_cols else "NULL::date AS claim_date")
        select_parts.append(f"COALESCE(c.{claimed_col}, 0) AS amount_claimed" if claimed_col else "0 AS amount_claimed")
        select_parts.append(f"COALESCE(c.{paid_col}, 0) AS amount_paid" if paid_col else "0 AS amount_paid")
        select_parts.append(f"COALESCE(c.{status_col}, 'draft') AS status" if status_col else "'draft' AS status")
        select_parts.append(f"COALESCE(c.{adjudication_col}, 'pending') AS adjudication_status" if adjudication_col else "'pending' AS adjudication_status")
        if import_batch_col and source_filename_col:
            select_parts.append(f"ib.{source_filename_col} AS source_filename")
            sql = f"SELECT {', '.join(select_parts)} FROM nhif_claims c LEFT JOIN nhif_import_batches ib ON ib.id = c.{import_batch_col} ORDER BY c.id DESC"
        else:
            select_parts.append("NULL::varchar AS source_filename")
            sql = f"SELECT {', '.join(select_parts)} FROM nhif_claims c ORDER BY c.id DESC"
        result = session.execute(text(sql)).mappings().all()
        return [dict(r) for r in result]
    finally:
        session.close()

def create_nhif_claim(facility_name: str, claim_month: str, nhif_reference: str | None, claim_date: str | None, amount_claimed: Any, amount_paid: Any, claim_forms_count: int | None, payment_reference: str | None, import_batch_id: int | None = None):
    facility_name = _clean_text(facility_name)
    claim_month = _clean_text(claim_month)
    nhif_reference = _clean_text(nhif_reference)
    payment_reference = _clean_text(payment_reference)
    claim_date = _clean_text(claim_date)
    if not facility_name:
        raise NHIFServiceError("Facility name inahitajika.")
    if not claim_month:
        raise NHIFServiceError("Claim month inahitajika.")
    amount_claimed = _to_decimal(amount_claimed)
    amount_paid = _to_decimal(amount_paid)
    session = _new_session()
    try:
        columns = _get_table_columns(session, "nhif_claims")
        rejection_gap = amount_claimed - amount_paid if amount_claimed > amount_paid else Decimal("0.00")
        approved_amount = amount_paid if amount_paid > 0 else amount_claimed
        payload = {
            "facility_name": facility_name,
            "claim_month": claim_month,
            "nhif_reference": nhif_reference,
            "claim_date": claim_date if claim_date else None,
            "amount_claimed": amount_claimed,
            "amount_paid": amount_paid,
            "claim_forms_count": claim_forms_count,
            "payment_reference": payment_reference,
            "import_batch_id": import_batch_id,
            "status": "draft",
        }
        if "gross_amount" in columns: payload["gross_amount"] = amount_claimed
        if "net_amount" in columns: payload["net_amount"] = approved_amount
        if "approved_amount" in columns: payload["approved_amount"] = approved_amount
        if "adjusted_amount" in columns: payload["adjusted_amount"] = rejection_gap
        if "rejected_amount" in columns: payload["rejected_amount"] = rejection_gap
        if "deduction_amount" in columns: payload["deduction_amount"] = rejection_gap
        if "adjudication_status" in columns: payload["adjudication_status"] = "approved" if amount_paid > 0 else "pending"
        if "claim_no" in columns and nhif_reference: payload["claim_no"] = nhif_reference
        if "reference_no" in columns and nhif_reference: payload["reference_no"] = nhif_reference
        if "facility" in columns and facility_name: payload["facility"] = facility_name
        if "claim_period" in columns and claim_month: payload["claim_period"] = claim_month
        ordered = ["claim_no","reference_no","facility","facility_name","claim_period","claim_month","nhif_reference","claim_date","gross_amount","approved_amount","adjusted_amount","rejected_amount","deduction_amount","amount_claimed","net_amount","amount_paid","claim_forms_count","payment_reference","import_batch_id","adjudication_status","status"]
        cols = [c for c in ordered if c in columns and c in payload]
        sql = f"INSERT INTO nhif_claims ({', '.join(cols)}) VALUES ({', '.join(':'+c for c in cols)}) RETURNING id"
        result = session.execute(text(sql), payload).scalar_one()
        session.commit()
        return int(result)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def create_nhif_collection(claim_id: int, collection_date: str, amount_collected: Any, receipt_reference: str | None, bank_reference: str | None):
    amount_collected = _to_decimal(amount_collected)
    collection_date = _clean_text(collection_date)
    receipt_reference = _clean_text(receipt_reference)
    bank_reference = _clean_text(bank_reference)
    session = _new_session()
    try:
        columns = _get_table_columns(session, "nhif_collections")
        claim_ctx = _get_claim_context(session, claim_id)
        effective_ref = receipt_reference or bank_reference or f"NHIF-COL-{claim_id}"
        payload = {
            "claim_id": claim_id,
            "collection_date": collection_date if collection_date else None,
            "amount_collected": amount_collected,
            "receipt_reference": effective_ref,
            "bank_reference": bank_reference or effective_ref,
        }
        if "batch_id" in columns: payload["batch_id"] = claim_ctx.get("batch_id") or 1
        if "amount" in columns and "amount_collected" not in columns: payload["amount"] = amount_collected
        if "reference_no" in columns: payload["reference_no"] = effective_ref
        if "receipt_no" in columns: payload["receipt_no"] = effective_ref
        if "payment_reference" in columns: payload["payment_reference"] = effective_ref
        if "bank_date" in columns: payload["bank_date"] = collection_date if collection_date else None
        if "receipt_date" in columns: payload["receipt_date"] = collection_date if collection_date else None
        if "deposit_date" in columns: payload["deposit_date"] = collection_date if collection_date else None
        if "facility_name" in columns: payload["facility_name"] = claim_ctx.get("facility_name")
        if "facility" in columns: payload["facility"] = claim_ctx.get("facility_name")
        if "claim_month" in columns: payload["claim_month"] = claim_ctx.get("claim_month")
        if "claim_period" in columns: payload["claim_period"] = claim_ctx.get("claim_month")
        ordered = ["batch_id","claim_id","facility","facility_name","claim_period","claim_month","collection_date","receipt_date","bank_date","deposit_date","amount","amount_collected","receipt_no","receipt_reference","reference_no","payment_reference","bank_reference"]
        cols = [c for c in ordered if c in columns and c in payload]
        sql = f"INSERT INTO nhif_collections ({', '.join(cols)}) VALUES ({', '.join(':'+c for c in cols)}) RETURNING id"
        result = session.execute(text(sql), payload).scalar_one()
        session.commit()
        return int(result)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def create_nhif_rejection(claim_id: int, rejection_date: str, rejection_reason: str, amount_rejected: Any):
    amount_rejected = _to_decimal(amount_rejected)
    rejection_reason = _clean_text(rejection_reason)
    rejection_date = _clean_text(rejection_date)
    if not rejection_reason:
        raise NHIFServiceError("Rejection reason inahitajika.")
    session = _new_session()
    try:
        columns = _get_table_columns(session, "nhif_rejections")
        claim_ctx = _get_claim_context(session, claim_id)
        effective_date = rejection_date if rejection_date else None
        payload = {
            "claim_id": claim_id,
            "rejection_date": effective_date,
            "rejection_reason": rejection_reason,
            "amount_rejected": amount_rejected,
        }
        if "batch_id" in columns: payload["batch_id"] = claim_ctx.get("batch_id") or 1
        if "amount" in columns and "amount_rejected" not in columns: payload["amount"] = amount_rejected
        if "reason" in columns and "rejection_reason" not in columns: payload["reason"] = rejection_reason
        if "loss_date" in columns: payload["loss_date"] = effective_date
        if "adjustment_date" in columns: payload["adjustment_date"] = effective_date
        if "facility_name" in columns: payload["facility_name"] = claim_ctx.get("facility_name")
        if "facility" in columns: payload["facility"] = claim_ctx.get("facility_name")
        if "claim_month" in columns: payload["claim_month"] = claim_ctx.get("claim_month")
        if "claim_period" in columns: payload["claim_period"] = claim_ctx.get("claim_month")
        ordered = ["batch_id","claim_id","facility","facility_name","claim_period","claim_month","rejection_date","loss_date","adjustment_date","reason","rejection_reason","amount","amount_rejected"]
        cols = [c for c in ordered if c in columns and c in payload]
        sql = f"INSERT INTO nhif_rejections ({', '.join(cols)}) VALUES ({', '.join(':'+c for c in cols)}) RETURNING id"
        result = session.execute(text(sql), payload).scalar_one()
        session.commit()
        return int(result)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def set_nhif_claim_status(claim_id: int, new_status: str, adjudication_status: str | None = None):
    session = _new_session()
    try:
        columns = _get_table_columns(session, "nhif_claims")
        updates = []
        params = {"claim_id": claim_id}
        if "status" in columns:
            updates.append("status = :status")
            params["status"] = new_status
        if adjudication_status and "adjudication_status" in columns:
            updates.append("adjudication_status = :adjudication_status")
            params["adjudication_status"] = adjudication_status
        if not updates:
            return
        sql = f"UPDATE nhif_claims SET {', '.join(updates)} WHERE id = :claim_id"
        session.execute(text(sql), params)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

def get_nhif_reconciliation():
    session = _new_session()
    try:
        claim_cols = _get_table_columns(session, "nhif_claims")
        collection_cols = _get_table_columns(session, "nhif_collections")
        rejection_cols = _get_table_columns(session, "nhif_rejections")
        facility_col = _pick_first_existing(claim_cols, "facility_name", "facility")
        month_col = _pick_first_existing(claim_cols, "claim_month", "claim_period")
        ref_col = _pick_first_existing(claim_cols, "nhif_reference", "reference_no", "claim_no")
        claimed_col = _pick_first_existing(claim_cols, "amount_claimed", "gross_amount")
        collected_col = _pick_first_existing(collection_cols, "amount_collected", "amount")
        rejected_col = _pick_first_existing(rejection_cols, "amount_rejected", "amount")
        if collected_col and rejected_col:
            sql = f"""
                SELECT
                    c.id,
                    {"COALESCE(c." + facility_col + ", '') AS facility_name" if facility_col else "'' AS facility_name"},
                    {"COALESCE(c." + month_col + ", '') AS claim_month" if month_col else "'' AS claim_month"},
                    {"COALESCE(c." + ref_col + ", '') AS nhif_reference" if ref_col else "'' AS nhif_reference"},
                    {"COALESCE(c." + claimed_col + ", 0) AS amount_claimed" if claimed_col else "0 AS amount_claimed"},
                    COALESCE(col.total_collected, 0) AS total_collected,
                    COALESCE(r.total_rejected, 0) AS total_rejected,
                    {"COALESCE(c." + claimed_col + ", 0)" if claimed_col else "0"} - COALESCE(col.total_collected, 0) - COALESCE(r.total_rejected, 0) AS outstanding_balance
                FROM nhif_claims c
                LEFT JOIN (SELECT claim_id, SUM({collected_col}) AS total_collected FROM nhif_collections GROUP BY claim_id) col ON col.claim_id = c.id
                LEFT JOIN (SELECT claim_id, SUM({rejected_col}) AS total_rejected FROM nhif_rejections GROUP BY claim_id) r ON r.claim_id = c.id
                ORDER BY c.id DESC
            """
        else:
            sql = f"""
                SELECT
                    c.id,
                    {"COALESCE(c." + facility_col + ", '') AS facility_name" if facility_col else "'' AS facility_name"},
                    {"COALESCE(c." + month_col + ", '') AS claim_month" if month_col else "'' AS claim_month"},
                    {"COALESCE(c." + ref_col + ", '') AS nhif_reference" if ref_col else "'' AS nhif_reference"},
                    {"COALESCE(c." + claimed_col + ", 0) AS amount_claimed" if claimed_col else "0 AS amount_claimed"},
                    0 AS total_collected, 0 AS total_rejected,
                    {"COALESCE(c." + claimed_col + ", 0)" if claimed_col else "0"} AS outstanding_balance
                FROM nhif_claims c
                ORDER BY c.id DESC
            """
        result = session.execute(text(sql)).mappings().all()
        return [dict(r) for r in result]
    finally:
        session.close()

def get_nhif_dashboard():
    session = _new_session()
    try:
        claim_cols = _get_table_columns(session, "nhif_claims")
        collection_cols = _get_table_columns(session, "nhif_collections")
        rejection_cols = _get_table_columns(session, "nhif_rejections")
        claimed_col = _pick_first_existing(claim_cols, "amount_claimed", "gross_amount")
        facility_col = _pick_first_existing(claim_cols, "facility_name", "facility")
        collected_col = _pick_first_existing(collection_cols, "amount_collected", "amount")
        rejected_col = _pick_first_existing(rejection_cols, "amount_rejected", "amount")
        reason_col = _pick_first_existing(rejection_cols, "rejection_reason", "reason")
        summary_sql = f"SELECT COALESCE((SELECT SUM({claimed_col}) FROM nhif_claims),0) AS total_claimed, COALESCE((SELECT SUM({collected_col}) FROM nhif_collections),0) AS total_collected, COALESCE((SELECT SUM({rejected_col}) FROM nhif_rejections),0) AS total_rejected, COALESCE((SELECT COUNT(id) FROM nhif_claims),0) AS total_claims" if claimed_col and collected_col and rejected_col else "SELECT 0 AS total_claimed,0 AS total_collected,0 AS total_rejected,0 AS total_claims"
        summary = session.execute(text(summary_sql)).mappings().first()
        facility_rows = []
        if facility_col and claimed_col:
            facility_sql = f"SELECT COALESCE(c.{facility_col}, '') AS facility_name, COALESCE(SUM(c.{claimed_col}),0) AS total_claimed FROM nhif_claims c GROUP BY COALESCE(c.{facility_col}, '') ORDER BY total_claimed DESC LIMIT 10"
            facility_rows = [dict(r) for r in session.execute(text(facility_sql)).mappings().all()]
        reason_rows = []
        if reason_col and rejected_col:
            reason_sql = f"SELECT COALESCE({reason_col}, 'Unspecified') AS rejection_reason, COUNT(id) AS item_count, COALESCE(SUM({rejected_col}),0) AS total_amount FROM nhif_rejections GROUP BY COALESCE({reason_col}, 'Unspecified') ORDER BY total_amount DESC LIMIT 10"
            reason_rows = [dict(r) for r in session.execute(text(reason_sql)).mappings().all()]
        return {"summary": dict(summary) if summary else {"total_claimed":0,"total_collected":0,"total_rejected":0,"total_claims":0}, "facility_rows": facility_rows, "reason_rows": reason_rows}
    finally:
        session.close()
