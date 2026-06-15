from django.apps import AppConfig


class DisplayConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'display'

    def ready(self):
        import display.signals  # noqa: F401
