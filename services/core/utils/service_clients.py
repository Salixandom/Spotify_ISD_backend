"""
Service clients for communicating between microservices.

This module provides HTTP-based clients for inter-service communication,
replacing direct model imports and maintaining service independence.
"""

import requests
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class CollaborationServiceClient:
    """Client for communicating with collaboration service"""

    BASE_URL = os.getenv('COLLAB_SERVICE_URL', 'http://collaboration:8003')

    @classmethod
    def get_collaborators(cls, playlist_id: int, auth_token: str = None) -> List[Dict]:
        """
        Get collaborators for a playlist.

        Args:
            playlist_id: Playlist ID
            auth_token: Optional authorization token for authenticated requests

        Returns:
            List of collaborator dictionaries
        """
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = auth_token

            url = f'{cls.BASE_URL}/api/collab/{playlist_id}/members/'
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to fetch collaborators for playlist {playlist_id}: {e}")
            return []

    @classmethod
    def get_collaborator_count(cls, playlist_id: int, auth_token: str = None) -> int:
        """
        Get count of collaborators for a playlist.

        Args:
            playlist_id: Playlist ID
            auth_token: Optional authorization token

        Returns:
            Number of collaborators
        """
        collaborators = cls.get_collaborators(playlist_id, auth_token)
        return len(collaborators)

    @classmethod
    def is_collaborator(cls, playlist_id: int, user_id: int, auth_token: str = None) -> bool:
        """
        Check if user is a collaborator on a playlist.

        Args:
            playlist_id: Playlist ID
            user_id: User ID
            auth_token: Optional authorization token

        Returns:
            True if user is a collaborator, False otherwise
        """
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = auth_token

            url = f'{cls.BASE_URL}/api/collab/{playlist_id}/my-role/'
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                return response.json().get('role') == 'collaborator'
            return False
        except requests.RequestException as e:
            logger.error(f"Failed to check collaborator status: {e}")
            return False

    @classmethod
    def get_user_collaborations(cls, user_id: int, auth_token: str) -> List[int]:
        """
        Get all playlist IDs where user is a collaborator.

        Args:
            user_id: User ID
            auth_token: Authorization token

        Returns:
            List of playlist IDs
        """
        try:
            headers = {'Authorization': auth_token}
            url = f'{cls.BASE_URL}/api/collab/my-collaborations/'
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            data = response.json()
            # Response is wrapped in SuccessResponse: {success, message, data: {playlist_ids: [...]}}
            return data.get('data', {}).get('playlist_ids', [])
        except requests.RequestException as e:
            logger.error(f"Failed to fetch user collaborations: {e}")
            return []

    @classmethod
    def add_collaborator_via_token(cls, playlist_id: int, token: str, auth_token: str) -> Optional[Dict]:
        """
        Add user as collaborator via invite token.

        Args:
            playlist_id: Playlist ID
            token: Invite token
            auth_token: Authorization token

        Returns:
            Collaborator data if successful, None otherwise
        """
        try:
            headers = {'Authorization': auth_token}
            url = f'{cls.BASE_URL}/api/collab/join/{token}/'
            response = requests.post(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to add collaborator via token: {e}")
            return None

    @classmethod
    def remove_collaborator(cls, playlist_id: int, user_id: int, auth_token: str) -> bool:
        """
        Remove collaborator from playlist.

        Args:
            playlist_id: Playlist ID
            user_id: User ID to remove
            auth_token: Authorization token

        Returns:
            True if successful, False otherwise
        """
        try:
            headers = {'Authorization': auth_token}
            url = f'{cls.BASE_URL}/api/collab/{playlist_id}/members/?user_id={user_id}'
            response = requests.delete(url, headers=headers, timeout=5)

            if response.status_code == 204:
                return True
            return False
        except requests.RequestException as e:
            logger.error(f"Failed to remove collaborator: {e}")
            return False


class ShareServiceClient:
    """Client for communicating with share service"""

    BASE_URL = os.getenv('COLLAB_SERVICE_URL', 'http://collaboration:8003')

    @classmethod
    def create_share_link(cls, playlist_id: int, user_id: int, auth_token: str) -> Optional[Dict]:
        """
        Create a share link for a playlist.

        Args:
            playlist_id: Playlist ID
            user_id: User ID creating the link
            auth_token: Authorization token

        Returns:
            Share link data if successful, None otherwise
        """
        try:
            headers = {'Authorization': auth_token}
            url = f'{cls.BASE_URL}/api/share/{playlist_id}/create/'
            response = requests.post(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Failed to create share link: {e}")
            return None

    @classmethod
    def validate_share_link(cls, token: str, auth_token: str = None) -> Optional[Dict]:
        """
        Validate a share link and get playlist details.

        Args:
            token: Share link token
            auth_token: Optional authorization token

        Returns:
            Share link validation data if valid, None otherwise
        """
        try:
            headers = {}
            if auth_token:
                headers['Authorization'] = auth_token

            url = f'{cls.BASE_URL}/api/share/view/{token}/'
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to validate share link: {e}")
            return None


class CoreServiceClient:
    """Client for communicating with core service (used by other services)"""

    BASE_URL = os.getenv('CORE_SERVICE_URL', 'http://core:8000')

    @classmethod
    def get_playlist(cls, playlist_id: int, auth_token: str) -> Optional[Dict]:
        """
        Get playlist details from core service.

        Args:
            playlist_id: Playlist ID
            auth_token: Authorization token

        Returns:
            Playlist data if found, None otherwise
        """
        try:
            headers = {'Authorization': auth_token}
            url = f'{cls.BASE_URL}/api/playlists/{playlist_id}/'
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                return response.json()
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch playlist {playlist_id}: {e}")
            return None

    @classmethod
    def check_playlist_ownership(cls, playlist_id: int, user_id: int, auth_token: str) -> bool:
        """
        Check if user owns a playlist.

        Args:
            playlist_id: Playlist ID
            user_id: User ID
            auth_token: Authorization token

        Returns:
            True if user owns the playlist, False otherwise
        """
        playlist = cls.get_playlist(playlist_id, auth_token)
        if playlist and playlist.get('owner_id') == user_id:
            return True
        return False


class AuthServiceClient:
    """Client for communicating with auth service"""

    BASE_URL = os.getenv('AUTH_SERVICE_URL', 'http://auth:8001')

    @classmethod
    def get_user_profile(cls, user_id: int, auth_token: str) -> Optional[Dict]:
        """
        Get user profile data from auth service.

        Args:
            user_id: User ID
            auth_token: Authorization token

        Returns:
            User profile data if found, None otherwise
        """
        try:
            headers = {'Authorization': auth_token}
            url = f'{cls.BASE_URL}/api/auth/profile/{user_id}/'
            response = requests.get(url, headers=headers, timeout=5)

            if response.status_code == 200:
                data = response.json()
                # Response is wrapped in SuccessResponse: {success, message, data: {...}}
                return data.get('data')
            return None
        except requests.RequestException as e:
            logger.error(f"Failed to fetch user profile {user_id}: {e}")
            return None
