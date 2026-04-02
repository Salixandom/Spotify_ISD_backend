from django.db import models


class AudioFile(models.Model):
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255, blank=True, default="")
    file = models.FileField(upload_to="audio/")
    duration_seconds = models.IntegerField(default=0)
    uploaded_by_id = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["uploaded_by_id"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.title
