from __future__ import annotations

from decimal import Decimal
from typing import Any


PMU_NOTE_TEMPLATE_MAP = {
    "23": "reports/notes/note_cash_and_cash_equivalents.html",
    "24": "reports/notes/note_receivables.html",
    "25": "reports/notes/note_inventories.html",
    "26": "reports/notes/note_ppe.html",
    "27": "reports/notes/note_payables.html",
    "10": "reports/notes/note_performance_generic.html",
    "12": "reports/notes/note_performance_generic.html",
    "14": "reports/notes/note_performance_generic.html",
    "16": "reports/notes/note_performance_generic.html",
    "17": "reports/notes/note_performance_generic.html",
    "18": "reports/notes/note_performance_generic.html",
    "19": "reports/notes/note_performance_generic.html",
    "20": "reports/notes/note_performance_generic.html",
}


PMU_NOTE_TITLE_MAP = {
    "23": "Cash and Cash Equivalents",
    "24": "Receivables",
    "25": "Inventories",
    "26": "Property, Plant and Equipment",
    "27": "Payables and Accruals",
    "10": "Revenue Grants",
    "12": "Other Revenue",
    "14": "Revenue from User Contribution",
    "16": "Wages, Salaries and Employee Benefits",
    "17": "Use of Goods and Services",
    "18": "Maintenance Expenses",
    "19": "Depreciation of Property, Plant and Equipment",
    "20": "Other Expenses",
}


def get_note_template(note_no: str) -> str:
    return PMU_NOTE_TEMPLATE_MAP.get(str(note_no), "reports/notes/note_generic.html")


def get_note_title(note_no: str) -> str:
    return PMU_NOTE_TITLE_MAP.get(str(note_no), f"Note {note_no} Schedule")


def group_note_rows_for_pmu(note_no: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Adds PMU-friendly grouping hints without changing underlying numbers.
    """
    note_no = str(note_no)
    grouped: dict[str, list[dict[str, Any]]] = {}

    def add(group_name: str, row: dict[str, Any]):
        grouped.setdefault(group_name, []).append(row)

    for row in rows:
        name = str(row.get("gfs_name", "") or "")
        gl_name = str(row.get("gl_name", "") or "")
        probe = f"{name} {gl_name}".lower()

        if note_no == "24":
            if "nhif" in probe:
                add("NHIF Receivables", row)
            elif "chif" in probe or "zhif" in probe:
                add("CHIF/ZHIF Receivables", row)
            elif "student" in probe:
                add("Student Fees Receivables", row)
            elif "pharmacy" in probe:
                add("Community Pharmacy Receivables", row)
            elif "other receivable" in probe:
                add("Other Receivables", row)
            else:
                add("Receivables - Other", row)

        elif note_no == "25":
            if "medicine" in probe or "drug" in probe:
                add("Medicine and Drugs", row)
            elif "medical supplies" in probe or "supplies" in probe:
                add("Medical Supplies", row)
            else:
                add("Inventory - Other", row)

        elif note_no == "26":
            if "building" in probe:
                add("Buildings", row)
            elif "vehicle" in probe:
                add("Motor Vehicles", row)
            elif "scientific" in probe or "medical equipment" in probe:
                add("Scientific / Medical Equipment", row)
            elif "office equipment" in probe:
                add("Office Equipment", row)
            elif "furniture" in probe or "fittings" in probe:
                add("Furniture and Fittings", row)
            elif "machine" in probe:
                add("Equipment and Machine", row)
            elif "depreciation" in probe:
                add("Accumulated Depreciation", row)
            else:
                add("PPE - Other", row)

        elif note_no == "27":
            if "msd" in probe:
                add("Payables to MSD", row)
            elif "statutory" in probe:
                add("Statutory Payables", row)
            elif "payroll" in probe:
                add("Payroll Payables", row)
            elif "accrued" in probe:
                add("Accrued Expenses", row)
            elif "trade payable" in probe or "supplier" in probe:
                add("Trade and Supplier Payables", row)
            else:
                add("Payables - Other", row)

        else:
            add("Composition", row)

    grouped_sections = []
    for title, items in grouped.items():
        current_total = sum(Decimal(str(r.get("current_amount", 0) or 0)) for r in items)
        prior_total = sum(Decimal(str(r.get("prior_amount", 0) or 0)) for r in items)
        grouped_sections.append({
            "title": title,
            "rows": items,
            "current_total": current_total,
            "prior_total": prior_total,
        })

    return {
        "grouped_sections": grouped_sections,
        "note_title": get_note_title(note_no),
        "template_name": get_note_template(note_no),
    }
