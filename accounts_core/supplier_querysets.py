"""Supplier list visibility: show financially active suppliers by default, all when searching."""

from django.db.models import Exists, OuterRef, Q

from accounts_core.models import Supplier


def _has_invoice_line():
    from sales.models import SalesInvoice, SalesInvoiceLine

    return Exists(
        SalesInvoiceLine.objects.filter(
            supplier_id=OuterRef("pk"),
            invoice__status__in=SalesInvoice.reporting_statuses(),
        )
    )


def _has_posted_bill():
    from purchases.models import SupplierBill

    return Exists(
        SupplierBill.objects.filter(
            supplier_id=OuterRef("pk"),
            status=SupplierBill.Status.POSTED,
        )
    )


def _has_opening_balance():
    from accounting_bridge.models import PartyOpeningBalance

    return Exists(
        PartyOpeningBalance.objects.filter(
            supplier_id=OuterRef("pk"),
            party_type=PartyOpeningBalance.PartyType.SUPPLIER,
        ).exclude(debit_usd=0, credit_usd=0)
    )


def _has_supplier_payment():
    from treasury.models import Payment

    return Exists(
        Payment.objects.filter(
            supplier_id=OuterRef("pk"),
            party_type=Payment.PartyType.SUPPLIER,
        )
    )


def suppliers_with_accounting_activity():
    """Suppliers with invoice lines, bills, opening balances, or payments (non-empty statement)."""
    return (
        Supplier.objects.annotate(
            _has_line=_has_invoice_line(),
            _has_bill=_has_posted_bill(),
            _has_ob=_has_opening_balance(),
            _has_pay=_has_supplier_payment(),
        )
        .filter(Q(_has_line=True) | Q(_has_bill=True) | Q(_has_ob=True) | Q(_has_pay=True))
        .distinct()
    )


def suppliers_for_select(*, extra_pk=None):
    """Dropdown options: active suppliers plus the currently selected row (if any)."""
    active_ids = suppliers_with_accounting_activity().values_list("pk", flat=True)
    qs = Supplier.objects.filter(pk__in=active_ids)
    if extra_pk:
        qs = Supplier.objects.filter(Q(pk=extra_pk) | Q(pk__in=active_ids))
    return qs.order_by("name").distinct()


def search_suppliers(q: str = "", *, limit: int = 50):
    """Search all suppliers by name or code (for typeahead in dropdowns and list search)."""
    qs = Supplier.objects.all().order_by("name")
    q = (q or "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(supplier_code__icontains=q)
            | Q(email__icontains=q)
        )
    return qs[:limit]


def supplier_choice_label(supplier: Supplier) -> str:
    return f"{supplier.supplier_code} — {supplier.name}"
