from django.db import models
import uuid

class Collaborator(models.Model):
    ROLE_CHOICES = [('owner', 'Owner'), ('collaborator', 'Collaborator')]
    playlist_id = models.IntegerField()
    user_id = models.IntegerField()
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='collaborator')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('playlist_id', 'user_id')

class InviteLink(models.Model):
    playlist_id = models.IntegerField()
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_by_id = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
