from django import forms
from .models import Lead, Attachment, DailyReport, Offer

class CreateLeadForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'name', 'country_code', 'phone', 'channel', 'reason_of_travel', 
            'assigned_to', 'takeover', 'destination', 'type_of_service',
            'offer_prepared', 'offer_details'
        ]
        widgets = {
            'reason_of_travel': forms.Textarea(attrs={'class': 'form-control'}),
            'destination': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'country_code': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'channel': forms.Select(attrs={'class': 'form-control'}),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'takeover': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'type_of_service': forms.Select(attrs={'class': 'form-control'}),
            'offer_prepared': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'offer_details': forms.Textarea(attrs={'class': 'form-control', 'style': 'display:none;'}),
        }


class QualificationForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            'destination', 'date_notes',
            'special_request', 'urgent', 'assignment_notes',
            'assigned_to', 'follow_up', 'reason_of_travel',
            'why_this_destination',
            'budget_range_from', 'budget_range_to', 'finalization_notes',
            'offer_prepared'
        ]
        widgets = {
            'follow_up': forms.DateInput(attrs={'type': 'date'}),
            'offer_prepared': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

class SendOfferForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['finalization_notes', 'assigned_to', 'offer_details']

class CloseDealForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ['selling_price', 'net', 'profit', 'sold', 'lost',
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
        }

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
