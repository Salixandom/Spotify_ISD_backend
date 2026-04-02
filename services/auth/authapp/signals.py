import os
import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
import httpx

logger = logging.getLogger(__name__)
CORE_SERVICE_URL = os.environ.get("CORE_SERVICE_URL", "http://core:8002")


@receiver(post_save, sender=User)
def create_liked_songs_playlist(sender, instance, created, **kwargs):
    """
    Automatically create a Liked Songs playlist when a new user registers.
    Makes an HTTP request to the core service's playlist API.
    """
    if created:
        try:
            # Create the Liked Songs playlist via HTTP API call
            playlist_data = {
                "owner_id": instance.id,
                "name": "Liked Songs",
                "description": "All your liked songs in one place",
                "visibility": "private",
                "playlist_type": "solo",
                "is_system_generated": True,
                "is_liked_songs": True,
                "cover_url": "",
                "max_songs": 0
            }

            response = httpx.post(
                f"{CORE_SERVICE_URL}/api/playlists/",
                json=playlist_data,
                timeout=5.0
            )

            if response.status_code == 201:
                logger.info(f"Created Liked Songs playlist for user {instance.id}")
            else:
                logger.warning(
                    f"Failed to create Liked Songs playlist for user {instance.id}: "
                    f"Status {response.status_code}, Response: {response.text}"
                )

        except httpx.TimeoutException:
            logger.error(f"Timeout creating Liked Songs playlist for user {instance.id}")
        except httpx.RequestError as e:
            logger.error(f"HTTP error creating Liked Songs playlist for user {instance.id}: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error creating Liked Songs playlist for user {instance.id}: {str(e)}")
