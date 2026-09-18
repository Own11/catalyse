from django.db import models


class UniversityProfile(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

