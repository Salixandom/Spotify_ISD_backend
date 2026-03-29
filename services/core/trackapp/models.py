from django.db import models
from playlistapp.models import Playlist
from searchapp.models import Song


class Track(models.Model):
    playlist = models.ForeignKey(
        Playlist,
        on_delete=models.CASCADE,
        related_name='tracks'
    )
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        related_name='playlist_entries'
    )
    added_by_id = models.IntegerField()
    position = models.IntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # unique_together on (playlist, song) prevents the same song appearing twice.
        # The (playlist, position) index is a performance index for fast ordering lookups.
        # Contiguous 0-based positions are maintained purely by TrackReorderRemoveView logic,
        # not by any database constraint — models.Index does not enforce uniqueness.
        unique_together = ('playlist', 'song')
        ordering = ['position']
        indexes = [
            models.Index(fields=['playlist', 'position']),
            models.Index(fields=['playlist', 'added_at']),
            models.Index(fields=['added_by_id']),
        ]

    def __str__(self):
        return f"{self.song.title} in {self.playlist.name} @ pos {self.position}"


class UserTrackHide(models.Model):
    user_id = models.IntegerField()
    track = models.ForeignKey(Track, on_delete=models.CASCADE, related_name='hidden_by')
    hidden_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_id', 'track')
