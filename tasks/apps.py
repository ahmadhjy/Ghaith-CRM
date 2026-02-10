from django.apps import AppConfig


class TasksConfig(AppConfig):
    # Ensure this matches the dotted path of your app package
    # e.g. if the app lives in `system/tasks`, the installed app
    # name is typically just "tasks".
    name = "tasks"

    def ready(self):
        """
        Import signal handlers when Django starts.

        Using a relative import here is more robust than relying on the
        project-level Python path configuration.
        """
        from . import signals  # noqa: F401  - imported for side effects
