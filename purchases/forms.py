from django import forms
from django.forms import inlineformset_factory

from accounts_core.supplier_querysets import suppliers_for_select
from purchases.models import SupplierBill, SupplierBillLine


class SupplierBillForm(forms.ModelForm):
    class Meta:
        model = SupplierBill
        fields = ["bill_no", "supplier", "bill_date", "due_date", "currency"]
        widgets = {
            "bill_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        extra_pk = self.instance.supplier_id if self.instance.pk else None
        if self.is_bound:
            raw = self.data.get(self.add_prefix("supplier"))
            if raw:
                extra_pk = raw
        self.fields["supplier"].queryset = suppliers_for_select(extra_pk=extra_pk)
        self.fields["supplier"].widget.attrs.setdefault("class", "supplier-select-search")


class SupplierBillLineForm(forms.ModelForm):
    class Meta:
        model = SupplierBillLine
        fields = [
            "sales_invoice_line",
            "service_instance",
            "description",
            "cost_amount",
            "notes",
        ]

    def save(self, commit=True):
        obj = super().save(commit=False)
        obj.line_kind = SupplierBillLine.LineKind.SERVICE
        obj.expense_category = None
        if commit:
            obj.save()
        return obj


SupplierBillLineFormSet = inlineformset_factory(
    SupplierBill,
    SupplierBillLine,
    form=SupplierBillLineForm,
    fields=["sales_invoice_line", "service_instance", "description", "cost_amount", "notes"],
    extra=1,
    can_delete=True,
)
