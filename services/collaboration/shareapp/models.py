import uuid
from django.db import models
from django.utils import timezone


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
    expires_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['playlist_id', 'is_active']),
        ]

    @property
    def is_valid(self):
        """
        Use this instead of checking is_active alone.
        Returns False if deactivated OR if the expiry time has passed.
        """
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def __str__(self):
        return f"ShareLink {self.token} for playlist {self.playlist_id}"
