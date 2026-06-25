from decimal import Decimal

from django import forms

from expenses.models import EmployeeSalaryEntry


class EmployeeSalaryEntryForm(forms.ModelForm):
    class Meta:
        model = EmployeeSalaryEntry
        fields = ["base_salary", "bonus", "notes"]
        widgets = {
            "base_salary": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "bonus": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Adjustments, overdue notes…"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["base_salary"].label = "Base salary (USD)"
        self.fields["bonus"].label = "Bonus / extra (USD)"


class SalaryPaymentForm(forms.Form):
    amount = forms.DecimalField(
        min_value=Decimal("0.01"),
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        label="Amount paid (USD)",
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        label="Payment date",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optional note on this payment"}),
        label="Note",
    )

    def __init__(self, *args, entry: EmployeeSalaryEntry | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.entry = entry
        if entry and not self.is_bound:
            from expenses.salary_services import entry_balance_due

            balance = entry_balance_due(entry)
            if balance > 0:
                self.fields["amount"].initial = balance

    def clean_amount(self):
        val = self.cleaned_data.get("amount")
        if val is None:
            return val
        return Decimal(val).quantize(Decimal("0.01"))
