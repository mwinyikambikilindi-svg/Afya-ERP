from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import text


def _to_float(value):
    if value is None:
        return 0.0
    return float(value)


def _to_int(value):
    if value is None:
        return 0
    return int(value)


def _normalize_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    raise ValueError(f"Unsupported date value: {value!r}")


def _table_exists(conn, table_name: str) -> bool:
    return bool(
        conn.execute(
            text("SELECT to_regclass(:table_name) IS NOT NULL"),
            {"table_name": table_name},
        ).scalar()
    )


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    sql = text(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = :table_name
              AND column_name = :column_name
        )
        """
    )
    return bool(conn.execute(sql, {"table_name": table_name, "column_name": column_name}).scalar())


def _query_scalar(conn, sql: str, params: dict | None = None):
    return conn.execute(text(sql), params or {}).scalar()


def _build_date_filters(column_sql: str, date_from=None, date_to=None):
    clauses = []
    params = {}

    normalized_from = _normalize_date(date_from)
    normalized_to = _normalize_date(date_to)

    if normalized_from is not None:
        clauses.append(f"{column_sql} >= :date_from")
        params["date_from"] = normalized_from

    if normalized_to is not None:
        clauses.append(f"{column_sql} <= :date_to")
        params["date_to"] = normalized_to

    return clauses, params


def _sum_amount(conn, header_table: str, line_table: str, header_fk: str, amount_column: str, date_column: str, date_from=None, date_to=None) -> float:
    if not (_table_exists(conn, header_table) and _table_exists(conn, line_table)):
        return 0.0

    where_clauses = ["h.status = 'posted'"] if _column_exists(conn, header_table, "status") else ["1=1"]
    date_clauses, params = _build_date_filters(f"h.{date_column}", date_from, date_to)
    where_clauses.extend(date_clauses)

    sql = f"""
        SELECT COALESCE(SUM(l.{amount_column}), 0)
        FROM {header_table} h
        JOIN {line_table} l ON l.{header_fk} = h.id
        WHERE {' AND '.join(where_clauses)}
    """
    return _to_float(_query_scalar(conn, sql, params))


def _count_records(conn, table_name: str, where_sql: str = "1=1", params: dict | None = None) -> int:
    if not _table_exists(conn, table_name):
        return 0
    return _to_int(_query_scalar(conn, f"SELECT COUNT(*) FROM {table_name} WHERE {where_sql}", params or {}))


def _sum_records(conn, table_name: str, value_sql: str, where_sql: str = "1=1", params: dict | None = None) -> float:
    if not _table_exists(conn, table_name):
        return 0.0
    return _to_float(_query_scalar(conn, f"SELECT COALESCE(SUM({value_sql}), 0) FROM {table_name} WHERE {where_sql}", params or {}))


def _count_posted_journals(conn, date_from=None, date_to=None) -> int:
    if not _table_exists(conn, "journal_batches"):
        return 0

    where_clauses = ["status = 'posted'"] if _column_exists(conn, "journal_batches", "status") else ["1=1"]
    if _column_exists(conn, "journal_batches", "journal_date"):
        date_clauses, params = _build_date_filters("journal_date", date_from, date_to)
        where_clauses.extend(date_clauses)
    else:
        params = {}

    sql = f"SELECT COUNT(*) FROM journal_batches WHERE {' AND '.join(where_clauses)}"
    return _to_int(_query_scalar(conn, sql, params))


def _monthly_series(conn, date_from=None, date_to=None):
    if not (
        _table_exists(conn, "cash_receipts")
        and _table_exists(conn, "cash_receipt_lines")
        and _table_exists(conn, "cash_payments")
        and _table_exists(conn, "cash_payment_lines")
    ):
        return []

    receipt_where = ["cr.status = 'posted'"] if _column_exists(conn, "cash_receipts", "status") else ["1=1"]
    payment_where = ["cp.status = 'posted'"] if _column_exists(conn, "cash_payments", "status") else ["1=1"]
    receipt_date_clauses, receipt_params = _build_date_filters("cr.receipt_date", date_from, date_to)
    payment_date_clauses, payment_params = _build_date_filters("cp.payment_date", date_from, date_to)
    receipt_where.extend(receipt_date_clauses)
    payment_where.extend(payment_date_clauses)

    params = {}
    params.update(receipt_params)
    params.update(payment_params)

    sql = f"""
        WITH posted_receipts AS (
            SELECT DATE_TRUNC('month', cr.receipt_date)::date AS month_start,
                   SUM(COALESCE(crl.amount, 0)) AS revenue
            FROM cash_receipts cr
            JOIN cash_receipt_lines crl ON crl.cash_receipt_id = cr.id
            WHERE {' AND '.join(receipt_where)}
            GROUP BY DATE_TRUNC('month', cr.receipt_date)::date
        ),
        posted_payments AS (
            SELECT DATE_TRUNC('month', cp.payment_date)::date AS month_start,
                   SUM(COALESCE(cpl.amount, 0)) AS expenditure
            FROM cash_payments cp
            JOIN cash_payment_lines cpl ON cpl.cash_payment_id = cp.id
            WHERE {' AND '.join(payment_where)}
            GROUP BY DATE_TRUNC('month', cp.payment_date)::date
        ),
        months AS (
            SELECT month_start FROM posted_receipts
            UNION
            SELECT month_start FROM posted_payments
        )
        SELECT
            TO_CHAR(m.month_start, 'Mon YYYY') AS label,
            COALESCE(r.revenue, 0) AS revenue,
            COALESCE(p.expenditure, 0) AS expenditure
        FROM months m
        LEFT JOIN posted_receipts r ON r.month_start = m.month_start
        LEFT JOIN posted_payments p ON p.month_start = m.month_start
        ORDER BY m.month_start ASC
    """

    rows = conn.execute(text(sql), params).mappings().all()
    return [
        {
            "label": row["label"],
            "revenue": _to_float(row["revenue"]),
            "expenditure": _to_float(row["expenditure"]),
        }
        for row in rows
    ]


def _student_receivables(conn, date_from=None, date_to=None) -> float:
    if not (_table_exists(conn, "student_invoices") and _table_exists(conn, "student_invoice_lines")):
        return 0.0

    invoice_fk = None
    for candidate in ("invoice_id", "student_invoice_id"):
        if _column_exists(conn, "student_invoice_lines", candidate):
            invoice_fk = candidate
            break
    if invoice_fk is None:
        return 0.0

    where_clauses = ["1=1"]
    params = {}
    if _column_exists(conn, "student_invoices", "status"):
        where_clauses.append("COALESCE(si.status, 'draft') <> 'cancelled'")
    if _column_exists(conn, "student_invoices", "invoice_date"):
        date_clauses, params = _build_date_filters("si.invoice_date", date_from, date_to)
        where_clauses.extend(date_clauses)

    if _column_exists(conn, "student_invoice_lines", "balance_amount"):
        sql = f"""
            SELECT COALESCE(SUM(COALESCE(sil.balance_amount, 0)), 0)
            FROM student_invoice_lines sil
            JOIN student_invoices si ON si.id = sil.{invoice_fk}
            WHERE {' AND '.join(where_clauses)}
        """
        return _to_float(_query_scalar(conn, sql, params))

    allocation_join = ""
    allocation_amount_expr = "0"
    if _table_exists(conn, "student_payment_allocations"):
        alloc_line_fk = None
        for candidate in ("invoice_line_id", "student_invoice_line_id"):
            if _column_exists(conn, "student_payment_allocations", candidate):
                alloc_line_fk = candidate
                break
        alloc_amount_col = None
        for candidate in ("allocated_amount", "amount_allocated"):
            if _column_exists(conn, "student_payment_allocations", candidate):
                alloc_amount_col = candidate
                break
        if alloc_line_fk and alloc_amount_col:
            allocation_join = (
                "LEFT JOIN ("
                f" SELECT {alloc_line_fk} AS alloc_invoice_line_id, SUM(COALESCE({alloc_amount_col}, 0)) AS allocated_amount "
                " FROM student_payment_allocations "
                f" GROUP BY {alloc_line_fk}"
                ") spa ON spa.alloc_invoice_line_id = sil.id"
            )
            allocation_amount_expr = "COALESCE(spa.allocated_amount, 0)"

    amount_col = "amount" if _column_exists(conn, "student_invoice_lines", "amount") else None
    if amount_col is None:
        return 0.0

    sql = f"""
        SELECT COALESCE(SUM(COALESCE(sil.{amount_col}, 0) - {allocation_amount_expr}), 0)
        FROM student_invoice_lines sil
        JOIN student_invoices si ON si.id = sil.{invoice_fk}
        {allocation_join}
        WHERE {' AND '.join(where_clauses)}
    """
    return _to_float(_query_scalar(conn, sql, params))


def _student_overdue_snapshot(conn):
    if not _table_exists(conn, "student_invoices"):
        return {"count": 0, "amount": 0.0}
    if not _column_exists(conn, "student_invoices", "due_date"):
        return {"count": 0, "amount": 0.0}

    balance_col = "balance_amount" if _column_exists(conn, "student_invoices", "balance_amount") else None
    if balance_col is None:
        return {"count": 0, "amount": 0.0}

    params = {"today": date.today()}
    count_sql = f"""
        SELECT COUNT(*)
        FROM student_invoices
        WHERE COALESCE({balance_col}, 0) > 0
          AND due_date < :today
          AND COALESCE(status, 'draft') NOT IN ('cancelled', 'paid')
    """
    amount_sql = f"""
        SELECT COALESCE(SUM(COALESCE({balance_col}, 0)), 0)
        FROM student_invoices
        WHERE COALESCE({balance_col}, 0) > 0
          AND due_date < :today
          AND COALESCE(status, 'draft') NOT IN ('cancelled', 'paid')
    """
    return {
        "count": _to_int(_query_scalar(conn, count_sql, params)),
        "amount": _to_float(_query_scalar(conn, amount_sql, params)),
    }


def _student_unallocated_cash(conn):
    if not _table_exists(conn, "student_payments"):
        return {"count": 0, "amount": 0.0}
    if not _column_exists(conn, "student_payments", "unallocated_amount"):
        return {"count": 0, "amount": 0.0}

    where_sql = "COALESCE(unallocated_amount, 0) > 0 AND COALESCE(status, 'draft') <> 'cancelled'"
    return {
        "count": _count_records(conn, "student_payments", where_sql),
        "amount": _sum_records(conn, "student_payments", "COALESCE(unallocated_amount, 0)", where_sql),
    }


def _asset_summary(conn) -> tuple[float, int, int]:
    if not _table_exists(conn, "fixed_assets"):
        return 0.0, 0, 0

    cost_candidates = ["cost", "acquisition_cost", "purchase_cost", "capitalized_cost"]
    existing_cost_columns = [c for c in cost_candidates if _column_exists(conn, "fixed_assets", c)]

    if existing_cost_columns:
        cost_expr = "COALESCE(" + ", ".join(existing_cost_columns) + ", 0)"
        total_cost = _to_float(_query_scalar(conn, f"SELECT COALESCE(SUM({cost_expr}), 0) FROM fixed_assets", {}))
    else:
        total_cost = 0.0

    active_count = 0
    disposed_count = 0
    if _column_exists(conn, "fixed_assets", "status"):
        active_count = _count_records(conn, "fixed_assets", "COALESCE(status, 'active') NOT IN ('disposed', 'retired', 'inactive')")
        disposed_count = _count_records(conn, "fixed_assets", "COALESCE(status, '') IN ('disposed', 'retired')")
    else:
        active_count = _count_records(conn, "fixed_assets")

    return total_cost, active_count, disposed_count


def _active_units(conn) -> int:
    if _table_exists(conn, "facilities"):
        if _column_exists(conn, "facilities", "is_active"):
            return _count_records(conn, "facilities", "COALESCE(is_active, TRUE) = TRUE")
        return _count_records(conn, "facilities")

    if _table_exists(conn, "branches"):
        if _column_exists(conn, "branches", "is_active"):
            return _count_records(conn, "branches", "COALESCE(is_active, TRUE) = TRUE")
        return _count_records(conn, "branches")

    return 0


def _approval_queue(conn):
    queue = []

    def add(label, route, count):
        queue.append({"label": label, "route": route, "count": count})

    if _table_exists(conn, "journal_batches") and _column_exists(conn, "journal_batches", "status"):
        add("Journal Approvals", "/journals?status=pending_approval", _count_records(conn, "journal_batches", "status = 'pending_approval'"))

    if _table_exists(conn, "cash_receipts") and _column_exists(conn, "cash_receipts", "status"):
        add("Receipt Reviews", "/cash-receipts?status=draft_pending_review", _count_records(conn, "cash_receipts", "status = 'draft_pending_review'"))

    if _table_exists(conn, "cash_payments") and _column_exists(conn, "cash_payments", "status"):
        add("Payment Reviews", "/cash-payments?status=draft_pending_review", _count_records(conn, "cash_payments", "status = 'draft_pending_review'"))

    if _table_exists(conn, "student_invoices") and _column_exists(conn, "student_invoices", "status"):
        add("Student Invoice Reviews", "/student-invoices", _count_records(conn, "student_invoices", "status IN ('draft_pending_review', 'pending_approval')"))

    if _table_exists(conn, "student_payments") and _column_exists(conn, "student_payments", "status"):
        add("Student Payment Reviews", "/student-payments", _count_records(conn, "student_payments", "status IN ('draft_pending_review', 'pending_approval')"))

    if _table_exists(conn, "asset_acquisitions") and _column_exists(conn, "asset_acquisitions", "status"):
        add("Asset Acquisition Reviews", "/asset-acquisitions", _count_records(conn, "asset_acquisitions", "status IN ('draft', 'draft_pending_review', 'pending_approval')"))

    if _table_exists(conn, "asset_disposals") and _column_exists(conn, "asset_disposals", "status"):
        add("Asset Disposal Reviews", "/asset-disposals", _count_records(conn, "asset_disposals", "status IN ('draft', 'draft_pending_review', 'pending_approval')"))

    if _table_exists(conn, "asset_depreciation_runs") and _column_exists(conn, "asset_depreciation_runs", "status"):
        add("Depreciation Reviews", "/asset-depreciation", _count_records(conn, "asset_depreciation_runs", "status IN ('draft', 'draft_pending_review', 'pending_approval')"))

    total = sum(item["count"] for item in queue)
    return total, queue


def _student_aging(conn):
    if not _table_exists(conn, "student_invoices"):
        return []
    if not (_column_exists(conn, "student_invoices", "due_date") and _column_exists(conn, "student_invoices", "balance_amount")):
        return []

    sql = """
        SELECT
            CASE
                WHEN due_date IS NULL THEN 'No Due Date'
                WHEN due_date >= CURRENT_DATE THEN 'Current'
                WHEN CURRENT_DATE - due_date BETWEEN 1 AND 30 THEN '1-30 Days'
                WHEN CURRENT_DATE - due_date BETWEEN 31 AND 60 THEN '31-60 Days'
                WHEN CURRENT_DATE - due_date BETWEEN 61 AND 90 THEN '61-90 Days'
                ELSE '91+ Days'
            END AS bucket,
            COUNT(*) AS invoice_count,
            COALESCE(SUM(COALESCE(balance_amount, 0)), 0) AS balance
        FROM student_invoices
        WHERE COALESCE(balance_amount, 0) > 0
          AND COALESCE(status, 'draft') NOT IN ('cancelled', 'paid')
        GROUP BY 1
    """
    rows = conn.execute(text(sql)).mappings().all()
    order = ["Current", "1-30 Days", "31-60 Days", "61-90 Days", "91+ Days", "No Due Date"]
    bucket_map = {row["bucket"]: row for row in rows}
    result = []
    max_balance = max([1.0] + [_to_float(row["balance"]) for row in rows])
    for bucket in order:
        row = bucket_map.get(bucket)
        balance = _to_float(row["balance"]) if row else 0.0
        count = _to_int(row["invoice_count"]) if row else 0
        result.append({
            "bucket": bucket,
            "invoice_count": count,
            "balance": balance,
            "pct": round((balance / max_balance) * 100, 2) if max_balance else 0,
        })
    return result


def _recent_student_activity(conn):
    items = []
    if _table_exists(conn, "student_invoices") and _column_exists(conn, "student_invoices", "invoice_no") and _column_exists(conn, "student_invoices", "invoice_date"):
        rows = conn.execute(text("""
            SELECT invoice_no AS ref_no, invoice_date AS action_date, COALESCE(total_amount, 0) AS amount, COALESCE(status, 'draft') AS status, 'Invoice' AS item_type
            FROM student_invoices
            ORDER BY invoice_date DESC, id DESC
            LIMIT 3
        """)).mappings().all()
        items.extend(dict(row) for row in rows)

    if _table_exists(conn, "student_payments") and _column_exists(conn, "student_payments", "payment_no") and _column_exists(conn, "student_payments", "payment_date"):
        rows = conn.execute(text("""
            SELECT payment_no AS ref_no, payment_date AS action_date, COALESCE(total_amount, 0) AS amount, COALESCE(status, 'draft') AS status, 'Payment' AS item_type
            FROM student_payments
            ORDER BY payment_date DESC, id DESC
            LIMIT 3
        """)).mappings().all()
        items.extend(dict(row) for row in rows)

    items.sort(key=lambda x: (x["action_date"], x["ref_no"]), reverse=True)
    return items[:5]


def get_dashboard_summary(date_from=None, date_to=None):
    from app import ext

    normalized_from = _normalize_date(date_from)
    normalized_to = _normalize_date(date_to)

    engine = ext.get_engine() if hasattr(ext, "get_engine") else ext.engine
    if engine is None:
        raise RuntimeError("Database engine is not initialized.")

    with engine.connect() as conn:
        total_receipts = _sum_amount(
            conn,
            header_table="cash_receipts",
            line_table="cash_receipt_lines",
            header_fk="cash_receipt_id",
            amount_column="amount",
            date_column="receipt_date",
            date_from=normalized_from,
            date_to=normalized_to,
        )
        total_payments = _sum_amount(
            conn,
            header_table="cash_payments",
            line_table="cash_payment_lines",
            header_fk="cash_payment_id",
            amount_column="amount",
            date_column="payment_date",
            date_from=normalized_from,
            date_to=normalized_to,
        )
        total_journals = _count_posted_journals(conn, normalized_from, normalized_to)
        monthly_series = _monthly_series(conn, normalized_from, normalized_to)
        student_receivables = _student_receivables(conn, normalized_from, normalized_to)
        overdue_students = _student_overdue_snapshot(conn)
        unallocated_student_cash = _student_unallocated_cash(conn)
        total_assets_cost, active_assets, disposed_assets = _asset_summary(conn)
        active_units = _active_units(conn)
        approvals_total, approvals_queue = _approval_queue(conn)
        aging_buckets = _student_aging(conn)
        recent_student_activity = _recent_student_activity(conn)

    net_position = total_receipts - total_payments

    max_value = max(
        [1.0]
        + [item["revenue"] for item in monthly_series]
        + [item["expenditure"] for item in monthly_series]
    )
    chart_series = [
        {
            **item,
            "revenue_pct": round((item["revenue"] / max_value) * 100, 2) if max_value else 0,
            "expenditure_pct": round((item["expenditure"] / max_value) * 100, 2) if max_value else 0,
        }
        for item in monthly_series
    ]

    high_alerts = []
    if overdue_students["count"]:
        high_alerts.append({
            "label": "Overdue Student Balances",
            "count": overdue_students["count"],
            "amount": overdue_students["amount"],
            "route": "/student-aging",
            "tone": "danger",
        })
    if approvals_total:
        high_alerts.append({
            "label": "Pending Approvals",
            "count": approvals_total,
            "amount": None,
            "route": "/student-approvals" if approvals_total else "/",
            "tone": "warning",
        })
    if unallocated_student_cash["count"]:
        high_alerts.append({
            "label": "Unallocated Student Cash",
            "count": unallocated_student_cash["count"],
            "amount": unallocated_student_cash["amount"],
            "route": "/student-payments",
            "tone": "info",
        })

    return {
        "total_revenue": total_receipts,
        "total_expenditure": total_payments,
        "net_position": net_position,
        "active_facilities": active_units,
        "student_receivables": student_receivables,
        "student_overdue_count": overdue_students["count"],
        "student_overdue_amount": overdue_students["amount"],
        "student_unallocated_count": unallocated_student_cash["count"],
        "student_unallocated_amount": unallocated_student_cash["amount"],
        "total_assets_cost": total_assets_cost,
        "active_assets": active_assets,
        "disposed_assets": disposed_assets,
        "total_journals": total_journals,
        "total_pending_approvals": approvals_total,
        "approvals_queue": approvals_queue,
        "monthly_series": chart_series,
        "aging_buckets": aging_buckets,
        "recent_student_activity": recent_student_activity,
        "high_alerts": high_alerts,
        # backward compatibility keys
        "total_receipts": total_receipts,
        "total_payments": total_payments,
        "total_income": total_receipts,
        "total_expenses": total_payments,
        "surplus_deficit": net_position,
    }
