import uuid
from django.db import models
from django.utils import timezone
from searchapp.models import Song


class Play(models.Model):
    user_id = models.IntegerField()
    song = models.ForeignKey(
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


class UserAction(models.Model):
    """
    Track all user mutations for undo/redo functionality.
    This is the foundation of the undo/redo system.
    """
    # Action identification
    id = models.BigAutoField(primary_key=True)
    action_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    # User & context
    user_id = models.IntegerField(db_index=True)
    session_id = models.CharField(max_length=100, db_index=True, null=True, blank=True)

    # Action classification
    ACTION_TYPES = [
        ('playlist_create', 'Create Playlist'),
        ('playlist_delete', 'Delete Playlist'),
        ('playlist_update', 'Update Playlist'),
        ('playlist_duplicate', 'Duplicate Playlist'),
        ('track_add', 'Add Track'),
        ('track_remove', 'Remove Track'),
        ('track_reorder', 'Reorder Tracks'),
        ('track_sort', 'Sort Tracks'),
        ('playlist_follow', 'Follow Playlist'),
        ('playlist_unfollow', 'Unfollow Playlist'),
        ('playlist_like', 'Like Playlist'),
        ('playlist_unlike', 'Unlike Playlist'),
        ('comment_add', 'Add Comment'),
        ('comment_delete', 'Delete Comment'),
        ('invite_generate', 'Generate Invite'),
        ('collaborator_add', 'Add Collaborator'),
        ('collaborator_remove', 'Remove Collaborator'),
    ]

    action_type = models.CharField(max_length=50, choices=ACTION_TYPES, db_index=True)
    entity_type = models.CharField(max_length=50)  # 'playlist', 'track', 'comment', etc.
    entity_id = models.IntegerField()

    # State snapshots (JSON serialized)
    before_state = models.JSONField(default=dict)  # State before action
    after_state = models.JSONField(default=dict)   # State after action
    delta = models.JSONField(default=dict)          # Changes made (for efficient undo)

    # Metadata
    description = models.TextField()  # Human-readable description
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Undo/redo state
    is_undone = models.BooleanField(default=False, db_index=True)
    undone_at = models.DateTimeField(null=True, blank=True)
    undone_action_id = models.UUIDField(null=True, blank=True)  # The undo action

    is_redone = models.BooleanField(default=False)
    redone_at = models.DateTimeField(null=True, blank=True)
    redone_action_id = models.UUIDField(null=True, blank=True)  # The redo action

    # Undoability
    is_undoable = models.BooleanField(default=True)  # Some actions can't be undone
    undo_deadline = models.DateTimeField(null=True, blank=True)  # Time limit for undo

    # Relationships for cascading actions
    parent_action_id = models.UUIDField(null=True, blank=True)  # Original action
    related_actions = models.JSONField(default=list)  # IDs of related actions

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id', '-created_at']),
            models.Index(fields=['action_id']),
            models.Index(fields=['is_undone']),
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_action_type_display()} by User {self.user_id} at {self.created_at}"

    def can_undo(self):
        """Check if action can still be undone"""
        if not self.is_undoable:
            return False
        if self.is_undone:
            return False
        if self.undo_deadline and timezone.now() > self.undo_deadline:
            return False
        return True

    def can_redo(self):
        """Check if undone action can be redone"""
        return self.is_undone and not self.is_redone


class UndoRedoConfiguration(models.Model):
    """
    User preferences for undo/redo system.
    """
    user_id = models.IntegerField(unique=True)

    # Time window for undo (in hours, 0 = unlimited)
    undo_window_hours = models.IntegerField(default=24)

    # Maximum actions to keep per user
    max_actions = models.IntegerField(default=1000)

    # Auto-delete old actions
    auto_cleanup = models.BooleanField(default=True)

    # Enable/disable undo for specific action types
    disabled_action_types = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Undo/Redo Configuration'
        verbose_name_plural = 'Undo/Redo Configurations'

    def __str__(self):
        return f"Undo/Redo Config for User {self.user_id}"
