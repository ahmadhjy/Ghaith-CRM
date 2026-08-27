"""Group filtered purchase lines into per-supplier totals."""

from __future__ import annotations

from collections import defaultdict

from tasks.constants import effective_service_net, parse_money
from tasks.purchases_filters import (
    SORT_DUE_ASC,
    SORT_DUE_DESC,
    SORT_TRAVEL_ASC,
    SORT_TRAVEL_DESC,
)

NO_SUPPLIER = "No supplier"


def group_purchases_by_supplier(services, sort=SORT_DUE_ASC):
    """Collapse purchase service lines into one row per supplier.

    Amounts use issue price when set, otherwise net — same as Purchases / analytics.
    """
    buckets = defaultdict(lambda: {
        "supplier": "",
        "count": 0,
        "unissued": 0.0,
        "issued": 0.0,
        "total": 0.0,
        "earliest_due": None,
        "earliest_travel": None,
    })
    for service in services:
        key = (service.supplier or "").strip() or NO_SUPPLIER
        amount = parse_money(effective_service_net(service))
        row = buckets[key]
        row["supplier"] = key
        row["count"] += 1
        row["total"] += amount
        if service.is_checked:
            row["issued"] += amount
        else:
            row["unissued"] += amount
        due = service.due_time
        if due and (row["earliest_due"] is None or due < row["earliest_due"]):
            row["earliest_due"] = due
        travel = getattr(getattr(service, "leadtask", None), "travel_date", None)
        if travel and (row["earliest_travel"] is None or travel < row["earliest_travel"]):
            row["earliest_travel"] = travel

    rows = list(buckets.values())
    return order_supplier_totals(rows, sort)


def order_supplier_totals(rows, sort=SORT_DUE_ASC):
    sort = (sort or SORT_DUE_ASC).strip()

    def _dated(key, reverse=False):
        dated = [row for row in rows if row.get(key)]
        undated = [row for row in rows if not row.get(key)]
        dated.sort(key=lambda row: row[key], reverse=reverse)
        return dated + undated

    if sort == SORT_DUE_DESC:
        return _dated("earliest_due", reverse=True)
    if sort == SORT_TRAVEL_ASC:
        return _dated("earliest_travel")
    if sort == SORT_TRAVEL_DESC:
        return _dated("earliest_travel", reverse=True)
    if sort == SORT_DUE_ASC:
        return _dated("earliest_due")
    rows.sort(key=lambda row: (-row["total"], row["supplier"].casefold()))
    return rows


def money_label(value):
    return f"{value:,.2f}"
