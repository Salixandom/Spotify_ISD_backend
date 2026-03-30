from django.db import models


class UserProfile(models.Model):
    """
    Extended user profile information.
    Stores additional user data beyond Django's built-in User model.
    """
    user_id = models.IntegerField(unique=True, db_index=True)

    # Basic profile info
    display_name = models.CharField(max_length=100, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    avatar_url = models.URLField(blank=True, max_length=500)

    # Privacy settings
    PROFILE_VISIBILITY_CHOICES = [
        ('public', 'Public'),
        ('followers', 'Followers Only'),
        ('private', 'Private'),
    ]
    profile_visibility = models.CharField(
        max_length=20,
        choices=PROFILE_VISIBILITY_CHOICES,
        default='public'
    )

    # Activity settings
    show_activity = models.BooleanField(default=True)
    allow_messages = models.BooleanField(default=True)

    # User preferences (JSON field for flexible settings)
    preferences = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['profile_visibility']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile for User {self.user_id}"

    @property
    def is_public(self):
        """Check if profile is publicly visible"""
        return self.profile_visibility == 'public'


class UserFollow(models.Model):
    """
    Track user-to-user following relationships.
    """
    follower_id = models.IntegerField(db_index=True)  # User who follows
    following_id = models.IntegerField(db_index=True)  # User being followed
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        unique_together = ('follower_id', 'following_id')
        indexes = [
            models.Index(fields=['follower_id']),
            models.Index(fields=['following_id']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = 'User Follow'
        verbose_name_plural = 'User Follows'

    def __str__(self):
        return f"User {self.follower_id} follows {self.following_id}"
