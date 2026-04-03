from django.db import models


class Playlist(models.Model):
    VISIBILITY_CHOICES = [('public', 'Public'), ('private', 'Private')]
    TYPE_CHOICES = [('solo', 'Solo'), ('collaborative', 'Collaborative')]

    owner_id = models.IntegerField()
    name = models.CharField(max_length=255, blank=True, default='')
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
    is_system_generated = models.BooleanField(default=False)  # For Spotify-made playlists like Discover Weekly, Liked Songs
    is_liked_songs = models.BooleanField(default=False)  # Special flag for the Liked Songs playlist
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
            # Composite indexes for common query patterns
            models.Index(fields=['owner_id', '-updated_at']),  # User's playlists ordered by recent
            models.Index(fields=['visibility', '-created_at']),  # Public playlists ordered by recent
            models.Index(fields=['visibility', 'playlist_type']),  # Public playlists by type
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


class PlaylistComment(models.Model):
    """
    Comments on playlists with threading support.
    """
    playlist_id = models.IntegerField(db_index=True)
    user_id = models.IntegerField(db_index=True)
    parent_id = models.IntegerField(null=True, blank=True, db_index=True)  # For threaded replies
    content = models.TextField()

    # Engagement
    likes_count = models.IntegerField(default=0)

    # Moderation
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['playlist_id', '-created_at']),
            models.Index(fields=['user_id']),
            models.Index(fields=['parent_id']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Playlist Comment'
        verbose_name_plural = 'Playlist Comments'

    def __str__(self):
        return f"Comment by {self.user_id} on playlist {self.playlist_id}"


class PlaylistCommentLike(models.Model):
    """
    Likes on playlist comments.
    """
    comment_id = models.IntegerField(db_index=True)
    user_id = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ('comment_id', 'user_id')
        indexes = [
            models.Index(fields=['comment_id']),
            models.Index(fields=['user_id']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'Playlist Comment Like'
        verbose_name_plural = 'Playlist Comment Likes'

    def __str__(self):
        return f"Like by User {self.user_id} on Comment {self.comment_id}"
