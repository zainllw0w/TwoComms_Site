from django.db import models
from django.utils import timezone


class DurableTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    task_name = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=180, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    available_at = models.DateTimeField(default=timezone.now, db_index=True)
    lease_token = models.CharField(max_length=64, blank=True, default="")
    lease_expires_at = models.DateTimeField(null=True, blank=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    worker_id = models.CharField(max_length=128, blank=True, default="")
    last_error = models.CharField(max_length=1000, blank=True, default="")
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=("status", "available_at", "id"), name="task_runtime_due"),
            models.Index(fields=("lease_expires_at", "id"), name="task_runtime_lease"),
        ]

    def __str__(self):
        return f"{self.task_name}:{self.idempotency_key}:{self.status}"
