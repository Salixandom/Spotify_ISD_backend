from django.db import models


class Track(models.Model):
    playlist_id = models.IntegerField()
    added_by_id = models.IntegerField()
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    album = models.CharField(max_length=255, blank=True)
    duration_seconds = models.IntegerField(default=0)
    cover_url = models.URLField(blank=True)
    audio_url = models.URLField(blank=True)
    position = models.IntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position"]

    def __str__(self):
        return f"{self.title} - {self.artist}"
