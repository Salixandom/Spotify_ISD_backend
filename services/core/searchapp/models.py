from django.db import models


class Genre(models.Model):
    """Music genre for categorization and discovery"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True, default='')

    # Statistics
    song_count = models.IntegerField(default=0)
    follower_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['song_count']),
        ]

    def __str__(self):
        return self.name


class Artist(models.Model):
    name              = models.CharField(max_length=255, unique=True)
    image_url         = models.URLField(max_length=500, blank=True, default='')
    bio               = models.TextField(default='')
    monthly_listeners = models.IntegerField(default=0)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['name'])]

    def __str__(self):
        return self.name


class Album(models.Model):
    artist       = models.ForeignKey(
                       Artist,
                       on_delete=models.CASCADE,
                       related_name='albums'
                   )
    name         = models.CharField(max_length=255)
    cover_url    = models.URLField(max_length=500, blank=True, default='')
    release_year = models.IntegerField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('artist', 'name')
        indexes = [
            models.Index(fields=['artist']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} — {self.artist.name}"


class Song(models.Model):
    artist           = models.ForeignKey(
                           Artist,
                           on_delete=models.CASCADE,
                           related_name='songs'
                       )
    album            = models.ForeignKey(
                           Album,
                           on_delete=models.SET_NULL,
                           null=True,
                           blank=True,
                           related_name='songs'
                       )
    title            = models.CharField(max_length=255)
    genre            = models.CharField(max_length=100, default='')
    release_year     = models.IntegerField(null=True, blank=True)

    # New fields for music discovery
    release_date     = models.DateField(null=True, blank=True, db_index=True)
    is_explicit      = models.BooleanField(default=False)
    popularity_score = models.IntegerField(default=0, db_index=True)  # 0-100

    duration_seconds = models.IntegerField(default=0)
    cover_url        = models.URLField(max_length=500, blank=True, default='')
    audio_url        = models.URLField(max_length=500, blank=True, default='')
    storage_path     = models.CharField(max_length=500, blank=True, default='')
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['artist']),
            models.Index(fields=['album']),
            models.Index(fields=['title']),
            models.Index(fields=['genre']),
            models.Index(fields=['release_year']),
            models.Index(fields=['-popularity_score']),  # For trending
            models.Index(fields=['-release_date']),  # For new releases
            models.Index(fields=['genre', '-popularity_score']),  # Composite for genre browsing
        ]

    def __str__(self):
        return f"{self.title} — {self.artist.name}"
