from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import text

import app.extensions as ext


def _get_conn():
    return ext.get_engine().connect()


def _table_exists(conn, table_name: str) -> bool:
    sql = text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table_name
        )
    """)
    return bool(conn.execute(sql, {"table_name": table_name}).scalar())


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    sql = text("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table_name AND column_name = :column_name
        )
    """)
    return bool(conn.execute(sql, {"table_name": table_name, "column_name": column_name}).scalar())


def _query_rows(conn, sql: str, params: dict[str, Any] | None = None):
    return [dict(row._mapping) for row in conn.execute(text(sql), params or {})]


def _query_scalar(conn, sql: str, params: dict[str, Any] | None = None):
    return conn.execute(text(sql), params or {}).scalar()


def _build_student_receivable_sql(conn) -> str | None:
    if not _table_exists(conn, 'student_invoices'):
        return None

    if _column_exists(conn, 'student_invoices', 'balance_amount'):
        return """
            SELECT COUNT(*) AS overdue_count
            FROM student_invoices si
            WHERE si.due_date < CURRENT_DATE
              AND COALESCE(si.balance_amount, 0) > 0
        """

    if not _table_exists(conn, 'student_invoice_lines') or not _table_exists(conn, 'student_payment_allocations'):
        return None

    invoice_line_invoice_col = 'invoice_id' if _column_exists(conn, 'student_invoice_lines', 'invoice_id') else ('student_invoice_id' if _column_exists(conn, 'student_invoice_lines', 'student_invoice_id') else None)
    allocation_line_col = 'invoice_line_id' if _column_exists(conn, 'student_payment_allocations', 'invoice_line_id') else ('student_invoice_line_id' if _column_exists(conn, 'student_payment_allocations', 'student_invoice_line_id') else None)
    allocation_amount_col = 'allocated_amount' if _column_exists(conn, 'student_payment_allocations', 'allocated_amount') else ('amount_allocated' if _column_exists(conn, 'student_payment_allocations', 'amount_allocated') else None)

    if not all([invoice_line_invoice_col, allocation_line_col, allocation_amount_col]):
        return None

    return f"""
        SELECT COUNT(*) AS overdue_count
        FROM (
            SELECT si.id,
                   si.due_date,
                   COALESCE(SUM(sil.amount), 0) - COALESCE(SUM(spa.{allocation_amount_col}), 0) AS balance_due
            FROM student_invoices si
            LEFT JOIN student_invoice_lines sil ON sil.{invoice_line_invoice_col} = si.id
            LEFT JOIN student_payment_allocations spa ON spa.{allocation_line_col} = sil.id
            GROUP BY si.id, si.due_date
        ) x
        WHERE x.due_date < CURRENT_DATE
          AND COALESCE(x.balance_due, 0) > 0
    """


def search_global_records(query: str, limit_per_section: int = 5) -> dict[str, Any]:
    normalized = (query or '').strip()
    if len(normalized) < 2:
        return {"sections": []}

    q = f"%{normalized}%"
    sections: list[dict[str, Any]] = []

    with _get_conn() as conn:
        # Students
        if _table_exists(conn, 'students'):
            rows = _query_rows(conn, """
                SELECT id,
                       COALESCE(student_no, admission_no, CONCAT(first_name, ' ', last_name)) AS title,
                       TRIM(CONCAT(COALESCE(first_name, ''), ' ', COALESCE(last_name, ''))) AS full_name
                FROM students
                WHERE COALESCE(student_no, '') ILIKE :q
                   OR COALESCE(admission_no, '') ILIKE :q
                   OR COALESCE(first_name, '') ILIKE :q
                   OR COALESCE(last_name, '') ILIKE :q
                ORDER BY id DESC
                LIMIT :lim
            """, {"q": q, "lim": limit_per_section})
            if rows:
                sections.append({
                    "label": "Students",
                    "items": [
                        {"title": row["title"] or row["full_name"], "meta": row["full_name"], "url": f"/students?highlight={row['id']}"}
                        for row in rows
                    ]
                })

        # Journals
        if _table_exists(conn, 'journal_batches'):
            rows = _query_rows(conn, """
                SELECT id, batch_no, reference_no, narration, status
                FROM journal_batches
                WHERE COALESCE(batch_no, '') ILIKE :q
                   OR COALESCE(reference_no, '') ILIKE :q
                   OR COALESCE(narration, '') ILIKE :q
                ORDER BY id DESC
                LIMIT :lim
            """, {"q": q, "lim": limit_per_section})
            if rows:
                sections.append({
                    "label": "Journals",
                    "items": [
                        {"title": row["batch_no"], "meta": f"{row['status']} • {row['reference_no'] or 'No ref'}", "url": f"/journals/{row['id']}"}
                        for row in rows
                    ]
                })

        # Cash receipts
        if _table_exists(conn, 'cash_receipts'):
            rows = _query_rows(conn, """
                SELECT id, receipt_no, reference_no, status
                FROM cash_receipts
                WHERE COALESCE(receipt_no, '') ILIKE :q
                   OR COALESCE(reference_no, '') ILIKE :q
                ORDER BY id DESC
                LIMIT :lim
            """, {"q": q, "lim": limit_per_section})
            if rows:
                sections.append({
                    "label": "Cash Receipts",
                    "items": [
                        {"title": row["receipt_no"], "meta": f"{row['status']} • {row['reference_no'] or 'No ref'}", "url": f"/cash-receipts/{row['id']}"}
                        for row in rows
                    ]
                })

        # Cash payments
        if _table_exists(conn, 'cash_payments'):
            rows = _query_rows(conn, """
                SELECT id, payment_no, reference_no, status
                FROM cash_payments
                WHERE COALESCE(payment_no, '') ILIKE :q
                   OR COALESCE(reference_no, '') ILIKE :q
                ORDER BY id DESC
                LIMIT :lim
            """, {"q": q, "lim": limit_per_section})
            if rows:
                sections.append({
                    "label": "Cash Payments",
                    "items": [
                        {"title": row["payment_no"], "meta": f"{row['status']} • {row['reference_no'] or 'No ref'}", "url": f"/cash-payments/{row['id']}"}
                        for row in rows
                    ]
                })

        # Student invoices
        if _table_exists(conn, 'student_invoices'):
            rows = _query_rows(conn, """
                SELECT id, invoice_no, reference_no, status
                FROM student_invoices
                WHERE COALESCE(invoice_no, '') ILIKE :q
                   OR COALESCE(reference_no, '') ILIKE :q
                ORDER BY id DESC
                LIMIT :lim
            """, {"q": q, "lim": limit_per_section})
            if rows:
                sections.append({
                    "label": "Student Invoices",
                    "items": [
                        {"title": row["invoice_no"], "meta": f"{row['status']} • {row['reference_no'] or 'No ref'}", "url": "/student-invoices"}
                        for row in rows
                    ]
                })

        # Student payments
        if _table_exists(conn, 'student_payments'):
            rows = _query_rows(conn, """
                SELECT id, payment_no, reference_no, status
                FROM student_payments
                WHERE COALESCE(payment_no, '') ILIKE :q
                   OR COALESCE(reference_no, '') ILIKE :q
                ORDER BY id DESC
                LIMIT :lim
            """, {"q": q, "lim": limit_per_section})
            if rows:
                sections.append({
                    "label": "Student Payments",
                    "items": [
                        {"title": row["payment_no"], "meta": f"{row['status']} • {row['reference_no'] or 'No ref'}", "url": "/student-payments"}
                        for row in rows
                    ]
                })

        # Assets
        if _table_exists(conn, 'fixed_assets'):
            rows = _query_rows(conn, """
                SELECT id,
                       COALESCE(asset_code, asset_tag_no, asset_name) AS title,
                       COALESCE(asset_name, 'Fixed Asset') AS asset_name,
                       COALESCE(status, 'active') AS status
                FROM fixed_assets
                WHERE COALESCE(asset_code, '') ILIKE :q
                   OR COALESCE(asset_tag_no, '') ILIKE :q
                   OR COALESCE(asset_name, '') ILIKE :q
                ORDER BY id DESC
                LIMIT :lim
            """, {"q": q, "lim": limit_per_section})
            if rows:
                sections.append({
                    "label": "Assets",
                    "items": [
                        {"title": row["title"], "meta": f"{row['asset_name']} • {row['status']}", "url": "/fixed-assets"}
                        for row in rows
                    ]
                })

    return {"sections": sections}


def get_notification_payload() -> dict[str, Any]:
    items: list[dict[str, Any]] = []

    with _get_conn() as conn:
        # Pending approvals
        checks = [
            ('journal_batches', "SELECT COUNT(*) FROM journal_batches WHERE status = 'pending_approval'", 'Pending journal approvals', '/journals', 'warning', 'Journal batches waiting for admin approval.'),
            ('cash_receipts', "SELECT COUNT(*) FROM cash_receipts WHERE status = 'draft_pending_review'", 'Receipts pending review', '/cash-receipts', 'info', 'Cash receipts saved for admin review.'),
            ('cash_payments', "SELECT COUNT(*) FROM cash_payments WHERE status = 'draft_pending_review'", 'Payments pending review', '/cash-payments', 'info', 'Cash payments saved for admin review.'),
            ('student_invoices', "SELECT COUNT(*) FROM student_invoices WHERE status = 'draft_pending_review'", 'Student invoices pending review', '/student-invoices', 'warning', 'Student invoices waiting for approval/posting.'),
            ('student_payments', "SELECT COUNT(*) FROM student_payments WHERE status = 'draft_pending_review'", 'Student payments pending review', '/student-payments', 'warning', 'Student payments waiting for approval/posting.'),
            ('asset_acquisitions', "SELECT COUNT(*) FROM asset_acquisitions WHERE status IN ('draft_pending_review', 'pending_approval')", 'Asset acquisitions pending review', '/asset-acquisitions', 'info', 'Asset acquisition records need approval.'),
            ('asset_disposals', "SELECT COUNT(*) FROM asset_disposals WHERE status IN ('draft_pending_review', 'pending_approval')", 'Asset disposals pending review', '/asset-disposals', 'danger', 'Asset disposal records need approval.'),
        ]
        for table_name, sql, title, url, severity, description in checks:
            if _table_exists(conn, table_name):
                count = int(_query_scalar(conn, sql) or 0)
                if count > 0:
                    items.append({"title": title, "count": count, "url": url, "severity": severity, "description": description})

        overdue_sql = _build_student_receivable_sql(conn)
        if overdue_sql:
            count = int(_query_scalar(conn, overdue_sql) or 0)
            if count > 0:
                items.append({
                    "title": 'Overdue student balances',
                    "count": count,
                    "url": '/student-aging',
                    "severity": 'danger',
                    "description": 'Students or sponsors with balances past due date.',
                })

        if _table_exists(conn, 'asset_maintenance') and _column_exists(conn, 'asset_maintenance', 'next_due_date'):
            count = int(_query_scalar(conn, """
                SELECT COUNT(*)
                FROM asset_maintenance
                WHERE next_due_date < CURRENT_DATE
                  AND COALESCE(status, 'open') NOT IN ('completed', 'closed')
            """) or 0)
            if count > 0:
                items.append({
                    "title": 'Maintenance overdue',
                    "count": count,
                    "url": '/asset-maintenance',
                    "severity": 'warning',
                    "description": 'Assets that require maintenance attention.',
                })

        if _table_exists(conn, 'accounting_periods'):
            count = int(_query_scalar(conn, "SELECT COUNT(*) FROM accounting_periods WHERE status = 'closed'") or 0)
            if count > 0:
                items.append({
                    "title": 'Closed accounting periods',
                    "count": count,
                    "url": '/periods',
                    "severity": 'info',
                    "description": 'Closed periods affect posting and corrections.',
                })

    items.sort(key=lambda item: (0 if item['severity'] == 'danger' else 1 if item['severity'] == 'warning' else 2, -item['count']))
    cards = items[:4]
    return {"total": sum(item['count'] for item in items), "items": items, "cards": cards}
