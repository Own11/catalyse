from django.db import models


class UniversityProfile(models.Model):
    name = models.CharField(max_length=255, blank=True, null=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.name or f"UniversityProfile #{self.pk}"


class Comment(models.Model):
    profile = models.ForeignKey(UniversityProfile, on_delete=models.CASCADE, related_name="comments")
    author_name = models.CharField(max_length=100, blank=True, default="Аноним")
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Comment by {self.author_name} on {self.profile.name or self.profile.pk}"


