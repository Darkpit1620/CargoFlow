from django.conf import settings
from django.db import models


class StaffAction(models.Model):
    """A minimal operational activity trail, not a legal/compliance audit log.

    Never store POST data, passwords, session keys, tokens, IP addresses,
    complete request URLs or customer details in these records.
    """

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        related_name="cargoflow_staff_actions", null=True, blank=True,
    )
    http_method = models.CharField(max_length=6)
    view_name = models.CharField(max_length=140)
    response_status = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-pk"]
        indexes = [models.Index(fields=["created_at"], name="staffact_created_idx")]

    def __str__(self):
        return f"{self.http_method} {self.view_name} ({self.response_status})"
