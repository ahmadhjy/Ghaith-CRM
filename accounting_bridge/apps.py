from django.apps import AppConfig


class AccountingBridgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounting_bridge'
    verbose_name = 'CRM ↔ Accounting bridge'

    def ready(self):
        import accounting_bridge.signals  # noqa: F401
