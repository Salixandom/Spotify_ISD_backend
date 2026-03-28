from django.db import models


class Playlist(models.Model):
    VISIBILITY_CHOICES = [('public', 'Public'), ('private', 'Private')]
    TYPE_CHOICES       = [('solo', 'Solo'), ('collaborative', 'Collaborative')]

    owner_id      = models.IntegerField()
    name          = models.CharField(max_length=255)
    description   = models.TextField(blank=True, default='')
    visibility    = models.CharField(
                        max_length=10,
                        choices=VISIBILITY_CHOICES,
                        default='public'
                    )
    playlist_type = models.CharField(
                        max_length=15,
                        choices=TYPE_CHOICES,
                        default='solo'
                    )
    cover_url     = models.URLField(max_length=500, blank=True, default='')
    max_songs     = models.PositiveIntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['owner_id']),
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['playlist_type']),
        ]

    def __str__(self):
        return self.name


class UserPlaylistArchive(models.Model):
    user_id     = models.IntegerField()
    playlist    = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='archived_by')
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_id', 'playlist')
