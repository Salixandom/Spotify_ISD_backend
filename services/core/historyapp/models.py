from django.db import models
from searchapp.models import Song


class Play(models.Model):
    user_id   = models.IntegerField()
    song      = models.ForeignKey(
                    Song,
                    on_delete=models.CASCADE,
                    related_name='plays'
                )
    played_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id', '-played_at']),
            models.Index(fields=['song', '-played_at']),
        ]

    def __str__(self):
        return f"User {self.user_id} played {self.song.title}"
