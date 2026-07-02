from django import forms
from .models import Lead, Attachment, DailyReport, Offer, Department

class CreateLeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'name', 'country_code', 'phone', 'email', 'channel',
            'whatsapp_received_on', 'department', 'chat_summary',
            'assigned_to', 'takeover', 'destination', 'type_of_service',
        ]
        widgets = {
            'reason_of_travel': forms.Textarea(attrs={'class': 'form-control'}),
            'destination': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'country_code': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'channel': forms.Select(attrs={'class': 'form-control'}),
            'whatsapp_received_on': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+96171111000'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'chat_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'AI chat summary or initial notes'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'takeover': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'type_of_service': forms.Select(attrs={'class': 'form-control'}),
            'offer_prepared': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'offer_details': forms.Textarea(attrs={'class': 'form-control', 'style': 'display:none;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('sort_order', 'name')
        self.fields['department'].required = False


class QualificationForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'name', 'destination', 'date_notes',
            'special_request', 'urgent', 'assignment_notes',
            'assigned_to', 'follow_up',
            'why_this_destination',
            'budget_range_from', 'budget_range_to', 'finalization_notes',
            'whatsapp_received_on', 'email', 'department', 'chat_summary',
        ]
        widgets = {
            'follow_up': forms.DateInput(attrs={'type': 'date'}),
            'offer_prepared': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'whatsapp_received_on': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'chat_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('sort_order', 'name')
        self.fields['department'].required = False

class SendOfferForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['name', 'finalization_notes', 'assigned_to', 'offer_details']

class CloseDealForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['name', 'selling_price', 'net', 'profit', 'sold', 'lost',
                  'finalization_notes', 'follow_up']
        widgets = {
            'follow_up': forms.DateInput(attrs={'type': 'date'}),
            'selling_price': forms.TextInput(attrs={'class': 'form-control'}),
            'net': forms.TextInput(attrs={'class': 'form-control'}),
            'profit': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

class CreateLeadDetailsForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['type_of_service', 'destination', 'pax', 'duration',
                  'travel_date_from', 'travel_date_to',
                  'date_notes', 'special_request', 'urgent',
                  'assignment_notes', 'assigned_to']

class LeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = '__all__'
        widgets = {
            'travel_date_from': forms.DateInput(attrs={'type': 'date'}),
            'travel_date_to': forms.DateInput(attrs={'type': 'date'}),
            'follow_up': forms.DateInput(attrs={'type': 'date'}),
            'whatsapp_received_on': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'chat_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'external_id': forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('sort_order', 'name')

class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = ['attachment_name', 'file']

class SearchLeadsForm(forms.Form):
    query = forms.CharField(label="Search Leads")

class DailyReportForm(forms.ModelForm):
    class Meta:
        model = DailyReport
        fields = ['notes']

class OfferForm(forms.ModelForm):
    class Meta:
        model = Offer
        fields = ['title', 'description', 'inclusions', 'exclusions', 'itinerary', 'accommodation_options', 'flight_details', 'pricing_usd', 'sent', 'sold']
        widgets = {
            'inclusions': forms.Textarea(attrs={'rows': 4}),
            'exclusions': forms.Textarea(attrs={'rows': 4}),
            'itinerary': forms.Textarea(attrs={'rows': 8}),
            'accommodation_options': forms.Textarea(attrs={'rows': 4}),
            'flight_details': forms.Textarea(attrs={'rows': 4}),
            'pricing_usd': forms.Textarea(attrs={'rows': 4}),
        }
