from django.db import models


class Playlist(models.Model):
    VISIBILITY_CHOICES = [('public', 'Public'), ('private', 'Private')]
    TYPE_CHOICES = [('solo', 'Solo'), ('collaborative', 'Collaborative')]

    owner_id = models.IntegerField()
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    visibility = models.CharField(
        max_length=10,
        choices=VISIBILITY_CHOICES,
        default='public'
    )
    playlist_type = models.CharField(
        max_length=15,
        choices=TYPE_CHOICES,
        default='solo'
    )
    cover_url = models.URLField(max_length=500, blank=True, default='')
    max_songs = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
    user_id = models.IntegerField()
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='archived_by')
    archived_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_id', 'playlist')


class UserPlaylistFollow(models.Model):
    """Users can follow playlists created by others"""
    user_id = models.IntegerField()
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='followers')
    followed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_id', 'playlist')
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['playlist']),
            models.Index(fields=['followed_at']),
        ]

    def __str__(self):
        return f"User {self.user_id} follows {self.playlist.name}"


class UserPlaylistLike(models.Model):
    """Users can like/favorite playlists"""
    user_id = models.IntegerField()
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='likes')
    liked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_id', 'playlist')
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['playlist']),
            models.Index(fields=['liked_at']),
        ]

    def __str__(self):
        return f"User {self.user_id} likes {self.playlist.name}"


class PlaylistSnapshot(models.Model):
    """Snapshots/versioning of playlist states"""
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='snapshots')
    snapshot_data = models.JSONField()  # Stores complete playlist state
    created_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    change_reason = models.CharField(max_length=255, blank=True, default='')
    track_count = models.PositiveIntegerField(default=0)

    class Meta:
        indexes = [
            models.Index(fields=['playlist']),
            models.Index(fields=['created_at']),
            models.Index(fields=['-created_at']),  # For ordering recent first
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Snapshot of {self.playlist.name} at {self.created_at}"
