from django.db import models


class Playlist(models.Model):
    VISIBILITY_CHOICES = [("public", "Public"), ("private", "Private")]
    TYPE_CHOICES = [("solo", "Solo"), ("collaborative", "Collaborative")]
    owner_id = models.IntegerField()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=10, choices=VISIBILITY_CHOICES, default="public"
    )
    playlist_type = models.CharField(
        max_length=15, choices=TYPE_CHOICES, default="solo"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
