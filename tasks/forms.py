from django import forms
from .models import Task, LeadTask, Payment, Attachment, Service, TaskAttachment, Supplier


# users should not edit the task except for
# some specific fields that are made  for them
class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = '__all__'
        widgets = {
            'due_time': forms.DateTimeInput(attrs={'type': 'date'}),
            'is_checked': forms.CheckboxInput(attrs={'onclick': 'this.form.submit();'}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'date']
        widgets = {
            'date': forms.DateTimeInput(attrs={'type': 'date'}),
        }


class LeadTaskForm(forms.ModelForm):
    service_checked = forms.BooleanField(required=False)
    payment_checked = forms.BooleanField(required=False)
    # Stored on related Lead.finalization_notes; saved in edit_lead_task view
    finalization_notes = forms.CharField(
        required=False,
        label='What Happened',
        widget=forms.Textarea(attrs={'rows': 4, 'id': 'id_finalization_notes'}),
    )

    class Meta:
        model = LeadTask
        fields = ['payment', 'status', 'notes', 'travel_date', 'return_date', 'date_of_birth', 'passport_expiry_date', 'service_checked', 'payment_checked', 'assigned_to']
        widgets = {
            'travel_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'return_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'passport_expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and getattr(self.instance, 'pk', None) and getattr(self.instance, 'lead_id', None):
            self.fields['finalization_notes'].initial = self.instance.lead.finalization_notes or ''


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = [
            'service_name', 'supplier', 'details', 'net', 'selling',
            'due_time', 'voucher_id', 'is_checked', 'send_to_client',
        ]
        widgets = {
            'due_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'is_checked': forms.CheckboxInput(attrs={'onclick': 'this.form.submit();' }),
        }


class AttachmentForm(forms.ModelForm):
    class Meta:
        model = Attachment
        fields = [ 'attachment_name', 'file']


class TaskAttachmentForm(forms.ModelForm):
    class Meta:
        model = TaskAttachment
        fields = ['attachment_name', 'file']


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier name'}),
            'is_active': forms.CheckboxInput(attrs={'checked': True}),
        }
