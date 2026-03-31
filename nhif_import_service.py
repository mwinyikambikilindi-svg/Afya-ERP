from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

import app.extensions as ext
from app.models.nhif_import_batch import NHIFImportBatch


class NHIFImportError(Exception):
    pass


FACILITY_ALIASES = {
    "KILWA ROAD POLISI TANZANIA": "Kilwa Road Police Hospital",
    "KILWA ROAD POLISI": "Kilwa Road Police Hospital",
    "KILWA ROAD HOSPITAL": "Kilwa Road Police Hospital",
    "TPS MOSHI": "Tanzania Police School Health Center (TPS Moshi)",
    "TANZANIA POLICE SCHOOL": "Tanzania Police School Health Center (TPS Moshi)",
    "ZANZIBAR POLICE ACADEMY": "Zanzibar Police Academy Dispensary",
    "ZPA": "Zanzibar Police Academy Dispensary",
    "ZPC": "Zanzibar Police Academy Dispensary",
    "MABATINI": "Mwanza Dispensary",
    "BUYEKRE": "Kagera Dispensary",
}


def _new_session():
    if ext.SessionLocal is None:
        raise RuntimeError("Database session factory is not initialized.")
    return ext.SessionLocal()


def _to_decimal(value: str | None) -> Decimal:
    if not value:
        return Decimal("0.00")
    cleaned = value.replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _normalize_facility_name(raw_name: str | None) -> str | None:
    if not raw_name:
        return None

    cleaned = re.sub(r"\s+", " ", raw_name).strip()
    upper = cleaned.upper()

    for key, value in FACILITY_ALIASES.items():
        if key in upper:
            return value

    # generic cleanup
    cleaned = cleaned.replace("Tanzania", "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_pdf_text(file_path: str) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise NHIFImportError("PDF import requires pypdf. Install with: pip install pypdf") from exc

    path = Path(file_path)
    if not path.exists():
        raise NHIFImportError("Uploaded NHIF PDF file was not found.")

    reader = PdfReader(str(path))
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            continue

    text = "\n".join(chunks).strip()
    if not text:
        raise NHIFImportError("No readable text found inside the NHIF PDF.")
    return text


def _find_first_money(text: str, patterns: list[str]) -> Decimal:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        if m:
            return _to_decimal(m.group(1))
    return Decimal("0.00")


def parse_nhif_receipt_text(text: str) -> dict:
    parsed = {
        "facility_name": None,
        "claim_month": None,
        "nhif_reference": None,
        "claim_date": None,
        "amount_claimed": Decimal("0.00"),
        "amount_paid": Decimal("0.00"),
        "claim_forms_count": None,
        "payment_reference": None,
        "adjustment_total": Decimal("0.00"),
        "raw_text_excerpt": text[:4000],
    }

    # Facility
    facility_patterns = [
        r"HUDUMA YA AFYA\s+(.+?)(?:\n|$)",
        r"Huduma ya Afya\s+(.+?)(?:\n|$)",
        r"Facility\s*[:\-]\s*(.+?)(?:\n|$)",
    ]
    for pat in facility_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            parsed["facility_name"] = _normalize_facility_name(m.group(1).strip())
            break

    # Claim month
    month_patterns = [
        r"Please refer to your claim submitted in\s+((?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})",
        r"submitted in\s+((?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})",
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})\b",
    ]
    for pat in month_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            parsed["claim_month"] = m.group(1).strip()
            break

    # NHIF reference
    ref_patterns = [
        r"Ref\.\s*([A-Z]\d{4}/[A-Z]{2,5}/\d{2}/\d{4}/\d{4})",
        r"\b([A-Z]\d{4}/[A-Z]{2,5}/\d{2}/\d{4}/\d{4})\b",
    ]
    for pat in ref_patterns:
        m = re.search(pat, text)
        if m:
            parsed["nhif_reference"] = m.group(1).strip()
            break

    # Claim date
    date_patterns = [
        r"\b([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\b",
    ]
    for pat in date_patterns:
        m = re.search(pat, text)
        if m:
            parsed["claim_date"] = m.group(1).strip()
            break

    # Claimed
    parsed["amount_claimed"] = _find_first_money(text, [
        r"AMOUNT CLAIMED\s+TZS\s*([0-9,]+(?:\.\d{2})?)",
        r"amount claimed\s*[:\-]?\s*(?:TZS|Tshs)\s*([0-9,]+(?:\.\d{2})?)",
        r"claimed amount\s*[:\-]?\s*(?:TZS|Tshs)\s*([0-9,]+(?:\.\d{2})?)",
    ])

    # Paid
    parsed["amount_paid"] = _find_first_money(text, [
        r"bank cheque numbered\s+[A-Z0-9]+\s+for\s+(?:Tshs|TZS)\s*([0-9,]+(?:\.\d{2})?)\s+being payment",
        r"for\s+(?:Tshs|TZS)\s*([0-9,]+(?:\.\d{2})?)\s+being payment",
        r"amount paid\s*[:\-]?\s*(?:TZS|Tshs)\s*([0-9,]+(?:\.\d{2})?)",
        r"paid amount\s*[:\-]?\s*(?:TZS|Tshs)\s*([0-9,]+(?:\.\d{2})?)",
    ])

    # Adjustment / rejection
    parsed["adjustment_total"] = _find_first_money(text, [
        r"Observed Anomalies.*?Total\s*([0-9,]+(?:\.\d{2})?)",
        r"List of Deductions.*?Total\s*([0-9,]+(?:\.\d{2})?)",
        r"amount adjusted\s*[:\-]?\s*(?:TZS|Tshs)\s*([0-9,]+(?:\.\d{2})?)",
        r"rejected amount\s*[:\-]?\s*(?:TZS|Tshs)\s*([0-9,]+(?:\.\d{2})?)",
    ])

    if parsed["adjustment_total"] == Decimal("0.00") and parsed["amount_claimed"] > parsed["amount_paid"] > Decimal("0.00"):
        parsed["adjustment_total"] = parsed["amount_claimed"] - parsed["amount_paid"]

    # Claim forms
    forms_patterns = [
        r"NUMBER OF CLAIM FORMS:\s*([0-9,]+)",
        r"(?:claim forms|forms count|number of claim forms)\s*[:\-]?\s*([0-9,]+)",
    ]
    for pat in forms_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            parsed["claim_forms_count"] = int(m.group(1).replace(",", ""))
            break

    # Payment ref
    payment_patterns = [
        r"bank cheque numbered\s*([A-Z0-9]+)",
        r"(?:cheque no|payment ref|remittance ref|cheque/payment ref(?:erence)?)\s*[:\-]?\s*([A-Z0-9/\-]+)",
    ]
    for pat in payment_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            parsed["payment_reference"] = m.group(1).strip()
            break

    return parsed


def save_import_batch(source_filename: str, parsed: dict, imported_by_user_id: int | None = None) -> int:
    session = _new_session()
    try:
        batch = NHIFImportBatch(
            facility_name=parsed.get("facility_name"),
            source_filename=source_filename,
            claim_month=parsed.get("claim_month"),
            nhif_reference=parsed.get("nhif_reference"),
            imported_by_user_id=imported_by_user_id,
            status="imported",
            raw_text_excerpt=parsed.get("raw_text_excerpt"),
        )
        session.add(batch)
        session.commit()
        return int(batch.id)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()