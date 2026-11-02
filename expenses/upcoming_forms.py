from datetime import date
from django import forms

from expenses.models import UpcomingExpensePayment, UpcomingExpensePlan, UpcomingExpenseType


class PaymentFieldsMixin:
    def style_fields(self):
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "ep-input")


class UpcomingExpenseForm(PaymentFieldsMixin, forms.ModelForm):
    class Meta:
        model = UpcomingExpensePlan
        fields = ["payment_type", "description", "amount", "start_date", "frequency"]
        labels = {"start_date": "First due date", "amount": "Amount (USD)", "frequency": "Repeat"}
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "What is this payment for?"}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_start_date(self):
        value = self.cleaned_data["start_date"]
        if not date(2000, 1, 1) <= value <= date(2100, 12, 31):
            raise forms.ValidationError("Choose a date between 2000 and 2100.")
        return value


class UpcomingPaymentEditForm(PaymentFieldsMixin, forms.ModelForm):
    class Meta:
        model = UpcomingExpensePayment
        fields = ["payment_type", "description", "amount", "due_date"]
        labels = {"amount": "Amount (USD)"}
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "description": forms.Textarea(attrs={"rows": 3}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class UpcomingTypeForm(PaymentFieldsMixin, forms.ModelForm):
    class Meta:
        model = UpcomingExpenseType
        fields = ["name"]
        labels = {"name": "Payment type name"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if UpcomingExpenseType.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This payment type already exists.")
        return name


class UpcomingFilterForm(PaymentFieldsMixin, forms.Form):
    payment_type = forms.ModelChoiceField(queryset=UpcomingExpenseType.objects.all(), required=False, empty_label="All payment types")
    due_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    due_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(choices=[("unpaid", "Unpaid (default)"), ("paid", "Paid"), ("all", "All payments")], required=False)
    repeat = forms.ChoiceField(choices=[("", "All frequencies"), ("once", "One time"), ("monthly", "Monthly")], required=False)
    sort = forms.ChoiceField(choices=[("due", "Due date · earliest"), ("-due", "Due date · latest"), ("amount", "Amount · highest")], required=False)
    search = forms.CharField(required=False, max_length=200, widget=forms.TextInput(attrs={"placeholder": "Search descriptions or payment types…"}))
    overdue = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean(self):
        data = super().clean()
        if data.get("due_from") and data.get("due_to") and data["due_from"] > data["due_to"]:
            raise forms.ValidationError("Due from must be before or equal to Due to.")
        return data
