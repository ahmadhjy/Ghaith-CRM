from django.forms import ModelForm, DateInput
from .models import Event


class EventForm(ModelForm):
    class Meta:
        model = Event
        # datetime-local is a HTML5 input type, format to make date time show on fields
        widgets = {
          'when': DateInput(attrs={'type': 'date'})
        }
        exclude = ['user']

    def __init__(self, *args, **kwargs):
        super(EventForm, self).__init__(*args, **kwargs)
