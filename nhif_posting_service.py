from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text

import app.extensions as ext


class NHIFPostingError(Exception):
    pass


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized.")
    return ext.SessionLocal()


def _to_decimal(value: Any) -> Decimal:
    try:
        if value in (None, ""):
            return Decimal("0.00")
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise NHIFPostingError("Amount lazima iwe namba sahihi.") from exc


def get_nhif_posting_preview(claim_id: int) -> dict:
    session = _new_session()
    try:
        claim = session.execute(
            text(
                """
                SELECT
                    id,
                    facility_name,
                    claim_month,
                    nhif_reference,
                    COALESCE(amount_claimed, 0) AS amount_claimed
                FROM nhif_claims
                WHERE id = :claim_id
                """
            ),
            {"claim_id": claim_id},
        ).mappings().first()

        if not claim:
            raise NHIFPostingError("NHIF claim haipo.")

        return {
            "claim_id": claim["id"],
            "facility_name": claim["facility_name"],
            "claim_month": claim["claim_month"],
            "nhif_reference": claim["nhif_reference"],
            "amount_claimed": claim["amount_claimed"],
            "entries": [
                {
                    "entry_type": "Claim Recognition",
                    "debit_account": "Receivable from NHIF",
                    "credit_account": "User Contribution NHIF",
                    "amount": claim["amount_claimed"],
                }
            ],
        }
    finally:
        session.close()


def get_collection_posting_preview(collection_id: int) -> dict:
    session = _new_session()
    try:
        row = session.execute(
            text(
                """
                SELECT
                    col.id,
                    c.facility_name,
                    c.claim_month,
                    c.nhif_reference,
                    COALESCE(col.amount_collected, 0) AS amount_collected
                FROM nhif_collections col
                JOIN nhif_claims c ON c.id = col.claim_id
                WHERE col.id = :collection_id
                """
            ),
            {"collection_id": collection_id},
        ).mappings().first()

        if not row:
            raise NHIFPostingError("NHIF collection haipo.")

        return {
            "collection_id": row["id"],
            "facility_name": row["facility_name"],
            "claim_month": row["claim_month"],
            "nhif_reference": row["nhif_reference"],
            "amount_collected": row["amount_collected"],
            "entries": [
                {
                    "entry_type": "NHIF Collection",
                    "debit_account": "Bank Balance",
                    "credit_account": "Receivable from NHIF",
                    "amount": row["amount_collected"],
                }
            ],
        }
    finally:
        session.close()


def get_rejection_posting_preview(rejection_id: int) -> dict:
    session = _new_session()
    try:
        row = session.execute(
            text(
                """
                SELECT
                    r.id,
                    c.facility_name,
                    c.claim_month,
                    c.nhif_reference,
                    r.rejection_reason,
                    COALESCE(r.amount_rejected, 0) AS amount_rejected
                FROM nhif_rejections r
                JOIN nhif_claims c ON c.id = r.claim_id
                WHERE r.id = :rejection_id
                """
            ),
            {"rejection_id": rejection_id},
        ).mappings().first()

        if not row:
            raise NHIFPostingError("NHIF rejection haipo.")

        return {
            "rejection_id": row["id"],
            "facility_name": row["facility_name"],
            "claim_month": row["claim_month"],
            "nhif_reference": row["nhif_reference"],
            "rejection_reason": row["rejection_reason"],
            "amount_rejected": row["amount_rejected"],
            "entries": [
                {
                    "entry_type": "NHIF Rejection/Loss",
                    "debit_account": "Loss on User Contribution NHIF",
                    "credit_account": "Receivable from NHIF",
                    "amount": row["amount_rejected"],
                }
            ],
        }
    finally:
        session.close()


def get_rejection_reason_analysis():
    session = _new_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT
                    COALESCE(rejection_reason, 'Unspecified') AS rejection_reason,
                    COUNT(id) AS item_count,
                    COALESCE(SUM(amount_rejected), 0) AS total_amount
                FROM nhif_rejections
                GROUP BY COALESCE(rejection_reason, 'Unspecified')
                ORDER BY total_amount DESC, item_count DESC
                """
            )
        ).mappings().all()
        return [dict(r) for r in rows]
    finally:
        session.close()


def get_facility_nhif_performance():
    session = _new_session()
    try:
        rows = session.execute(
            text(
                """
                SELECT
                    c.facility_name,
                    COALESCE(SUM(c.amount_claimed), 0) AS total_claimed,
                    COALESCE(SUM(col.amount_collected), 0) AS total_collected,
                    COALESCE(SUM(r.amount_rejected), 0) AS total_rejected,
                    COALESCE(SUM(c.amount_claimed), 0)
                      - COALESCE(SUM(col.amount_collected), 0)
                      - COALESCE(SUM(r.amount_rejected), 0) AS total_outstanding
                FROM nhif_claims c
                LEFT JOIN nhif_collections col ON col.claim_id = c.id
                LEFT JOIN nhif_rejections r ON r.claim_id = c.id
                GROUP BY c.facility_name
                ORDER BY total_claimed DESC
                """
            )
        ).mappings().all()

        result = []
        for row in rows:
            claimed = Decimal(str(row["total_claimed"] or 0))
            collected = Decimal(str(row["total_collected"] or 0))
            rejected = Decimal(str(row["total_rejected"] or 0))
            efficiency = (collected / claimed * Decimal("100")) if claimed > 0 else Decimal("0")
            rejection_rate = (rejected / claimed * Decimal("100")) if claimed > 0 else Decimal("0")

            result.append({
                "facility_name": row["facility_name"],
                "total_claimed": claimed,
                "total_collected": collected,
                "total_rejected": rejected,
                "total_outstanding": Decimal(str(row["total_outstanding"] or 0)),
                "collection_efficiency_pct": efficiency,
                "rejection_rate_pct": rejection_rate,
            })
        return result
    finally:
        session.close()
