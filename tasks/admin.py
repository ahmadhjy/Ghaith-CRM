from django.contrib import admin
from .models import Task, LeadTask, Payment, Tag

admin.site.register(Task)
admin.site.register(Tag)
admin.site.register(LeadTask)