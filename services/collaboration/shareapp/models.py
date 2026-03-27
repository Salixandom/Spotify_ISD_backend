import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone


def default_expires_at():
    return timezone.now() + timedelta(days=30)


class ShareLink(models.Model):
    playlist_id   = models.IntegerField()
    token         = models.UUIDField(
                        default=uuid.uuid4,
                        unique=True,
                        editable=False
                    )
    created_by_id = models.IntegerField()
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField(default=default_expires_at)

    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['playlist_id', 'is_active']),
        ]

    @property
    def is_valid(self):
        return self.is_active and timezone.now() <= self.expires_at

    def __str__(self):
        return f"ShareLink {self.token} for playlist {self.playlist_id}"
