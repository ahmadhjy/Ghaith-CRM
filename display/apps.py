from django.apps import AppConfig


class DisplayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'display'
    verbose_name = 'CRM & WhatsApp'

    def ready(self):
        import display.signals  # noqa: F401
