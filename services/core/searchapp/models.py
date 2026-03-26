from django.db import models


class Song(models.Model):
    title = models.CharField(max_length=255)
    artist = models.CharField(max_length=255)
    album = models.CharField(max_length=255, blank=True)
    genre = models.CharField(max_length=100, blank=True)
    duration_seconds = models.IntegerField(default=0)
    cover_url = models.URLField(blank=True)
    audio_url = models.URLField(blank=True)

    def __str__(self):
        return f"{self.title} - {self.artist}"
