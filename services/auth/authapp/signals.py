from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User


@receiver(post_save, sender=User)
def create_liked_songs_playlist(sender, instance, created, **kwargs):
    """
    Automatically create a Liked Songs playlist when a new user registers.
    """
    if created:
        # Import here to avoid circular imports
        from core.playlistapp.models import Playlist

        # Check if user already has a Liked Songs playlist
        existing = Playlist.objects.filter(
            owner_id=instance.id,
            is_liked_songs=True
        ).first()

        if not existing:
            # Create the Liked Songs playlist
            Playlist.objects.create(
                owner_id=instance.id,
                name="Liked Songs",
                description="All your liked songs in one place",
                visibility="private",
                playlist_type="solo",
                is_system_generated=True,
                is_liked_songs=True,
                cover_url="",
                max_songs=0
            )
