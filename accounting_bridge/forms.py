from decimal import Decimal

from django import forms

from accounting_bridge.models import PartyOpeningBalance
from accounts_core.models import Client, Supplier


class OpeningBalanceForm(forms.ModelForm):
    class Meta:
        model = PartyOpeningBalance
        fields = ['party_type', 'client', 'supplier', 'as_of_date', 'debit_usd', 'credit_usd', 'notes']
        widgets = {
            'as_of_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'debit_usd': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'credit_usd': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.order_by('name_en')
        self.fields['supplier'].queryset = Supplier.objects.order_by('name')
        self.fields['client'].required = False
        self.fields['supplier'].required = False
        self.fields['debit_usd'].label = 'Debit (USD)'
        self.fields['credit_usd'].label = 'Credit (USD)'
        self.fields['debit_usd'].min_value = Decimal('0')
        self.fields['credit_usd'].min_value = Decimal('0')
        self.fields['debit_usd'].help_text = (
            'Client: what they owe you. Supplier: reductions / payments on account.'
        )
        self.fields['credit_usd'].help_text = (
            'Client: prepayments / credits. Supplier: what you owe them.'
        )

    def clean(self):
        data = super().clean()
        party_type = data.get('party_type')
        client = data.get('client')
        supplier = data.get('supplier')
        debit = data.get('debit_usd') or Decimal('0.00')
        credit = data.get('credit_usd') or Decimal('0.00')
        if debit == 0 and credit == 0:
            self.add_error(None, 'Enter a debit and/or credit amount.')
        if party_type == PartyOpeningBalance.PartyType.CLIENT:
            if not client:
                self.add_error('client', 'Select a client.')
            data['supplier'] = None
        elif party_type == PartyOpeningBalance.PartyType.SUPPLIER:
            if not supplier:
                self.add_error('supplier', 'Select a supplier.')
            data['client'] = None
        return data
