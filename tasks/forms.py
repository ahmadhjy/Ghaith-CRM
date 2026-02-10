from django import forms
from .models import Task, LeadTask, Payment, Attachment, Service, TaskAttachment


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

    class Meta:
        model = LeadTask
        fields = ['payment', 'status', 'notes', 'travel_date', 'date_of_birth', 'passport_expiry_date', 'service_checked', 'payment_checked','assigned_to']
        widgets = {
            'travel_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'passport_expiry_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ['service_name', 'supplier', 'details', 'net', 'selling', 'due_time', 'voucher_id', 'is_checked']
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
