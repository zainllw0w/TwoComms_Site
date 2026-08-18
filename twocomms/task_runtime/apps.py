from django.apps import AppConfig


class TaskRuntimeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "task_runtime"

    def ready(self):
        from . import tasks  # noqa: F401
