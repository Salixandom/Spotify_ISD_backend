from rest_framework.views import APIView
from rest_framework import permissions
import requests

from utils.responses import (
    SuccessResponse,
    NotFoundResponse,
    ForbiddenResponse,
    ValidationErrorResponse,
    ServiceUnavailableResponse,
    NoContentResponse,
)
from django.db import connection
from .models import Collaborator, InviteLink
from .serializers import CollaboratorSerializer, InviteLinkSerializer


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                cursor.fetchone()
            return SuccessResponse(
                data={'status': 'healthy', 'service': 'collaboration', 'database': 'connected'},
                message='Service is healthy'
            )
        except Exception as e:
            return ServiceUnavailableResponse(
                message=f'Database connection failed: {str(e)}'
            )


class GenerateInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        invite = InviteLink.objects.create(
            playlist_id=playlist_id,
            created_by_id=request.user.id,
        )
        return SuccessResponse(
            data=InviteLinkSerializer(invite).data,
            message='Invite link generated successfully',
            status_code=201
        )


class JoinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token):
        try:
            invite = InviteLink.objects.get(token=token)
        except InviteLink.DoesNotExist:
            return NotFoundResponse(message='Invalid link')
        if not invite.is_valid:
            return NotFoundResponse(message='Invalid link')
        return SuccessResponse(
            data={'playlist_id': invite.playlist_id, 'valid': True},
            message='Invite link is valid'
        )

    def post(self, request, token):
        try:
            invite = InviteLink.objects.get(token=token)
        except InviteLink.DoesNotExist:
            return NotFoundResponse(message='Invalid link')
        if not invite.is_valid:
            return NotFoundResponse(message='Invalid link')

        collab, created = Collaborator.objects.get_or_create(
            playlist_id=invite.playlist_id,
            user_id=request.user.id,
        )

        # If this is the first collaborator, update the playlist_type to 'collaborative'
        if created:
            self._update_playlist_type_to_collaborative(invite.playlist_id)

        # Auto-follow the playlist in core service so it appears in user's library
        auth_header = request.headers.get('Authorization', '')
        self._auto_follow_playlist(invite.playlist_id, request.user.id, auth_header)

        if not created:
            return SuccessResponse(
                data={'already_member': True},
                message='Already a member of this playlist'
            )

        return SuccessResponse(
            data=CollaboratorSerializer(collab).data,
            message='Added as collaborator successfully',
            status_code=201
        )

    def _auto_follow_playlist(self, playlist_id, user_id, auth_header):
        """Make cross-service call to core API to auto-follow the playlist."""
        import requests
        import os
        import logging
        logger = logging.getLogger(__name__)

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8000')
        try:
            logger.info(f"Attempting to auto-follow playlist {playlist_id} for user {user_id}")
            response = requests.post(
                f'{core_service_url}/api/playlists/{playlist_id}/follow/',
                headers={'Authorization': auth_header},
                timeout=5
            )
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"Successfully auto-followed playlist {playlist_id} for user {user_id}")
            else:
                logger.warning(f"Failed to auto-follow playlist {playlist_id}: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Exception during auto-follow of playlist {playlist_id}: {e}")
            # Non-critical: auto-follow failure should not block joining

    def _update_playlist_type_to_collaborative(self, playlist_id):
        """Update playlist type to collaborative in core service."""
        import requests
        import os
        import logging
        logger = logging.getLogger(__name__)

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8000')
        try:
            # Get current playlist data first to check if update is needed
            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/',
                timeout=5
            )
            if response.status_code == 200:
                response_json = response.json()
                # Core service wraps data in {"data": {...}} structure
                playlist_data = response_json.get('data', {})
                if playlist_data.get('playlist_type') != 'collaborative':
                    # Update to collaborative
                    update_response = requests.patch(
                        f'{core_service_url}/api/playlists/{playlist_id}/',
                        json={'playlist_type': 'collaborative'},
                        timeout=5
                    )
                    if update_response.status_code == 200:
                        logger.info(f"Updated playlist {playlist_id} type to collaborative")
                    else:
                        logger.warning(f"Failed to update playlist {playlist_id} type: {update_response.status_code}")
        except Exception as e:
            logger.error(f"Exception during playlist type update for {playlist_id}: {e}")
            # Non-critical: type update failure should not block joining


class CollaboratorListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        collabs = Collaborator.objects.filter(playlist_id=playlist_id)
        return SuccessResponse(
            data=CollaboratorSerializer(collabs, many=True).data,
            message=f'Retrieved {collabs.count()} collaborators'
        )

    def delete(self, request, playlist_id):
        """
        Remove a collaborator from a playlist.

        Authorization:
        - Users can always remove themselves (self-removal)
        - The playlist owner can remove any collaborator

        The caller supplies `owner_id` in the request body so the collaboration
        service can verify ownership without a cross-service HTTP call.
        `request.user.id` is JWT-verified; if it matches the supplied `owner_id`
        then the requester is the owner and may remove any collaborator.

        Body params:
            user_id  (required) — ID of the collaborator to remove
            owner_id (optional) — ID of the playlist owner; enables owner removal
        """
        user_id = request.query_params.get('user_id') or request.data.get('user_id')
        if not user_id:
            return ValidationErrorResponse(
                errors={'user_id': 'This field is required'},
                message='user_id required'
            )

        # Self-removal: always allowed
        if str(user_id) == str(request.user.id):
            Collaborator.objects.filter(playlist_id=playlist_id, user_id=user_id).delete()
            return NoContentResponse()

        # Check if requester is playlist owner via cross-service call
        import requests
        import os

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8000')
        auth_header = request.headers.get('Authorization', '')

        try:
            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/',
                headers={'Authorization': auth_header},
                timeout=5
            )

            if response.status_code == 200:
                response_json = response.json()
                # Core service wraps data in {"data": {...}} structure
                playlist_data = response_json.get('data', {})
                if playlist_data.get('owner_id') == request.user.id:
                    Collaborator.objects.filter(playlist_id=playlist_id, user_id=user_id).delete()
                    return NoContentResponse()

        except requests.RequestException as e:
            return ServiceUnavailableResponse(
                message=f'Failed to verify ownership: {str(e)}'
            )

        return ForbiddenResponse(message='Access forbidden')


class MyCollaborationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        playlist_ids = (
            Collaborator.objects.filter(user_id=request.user.id)
            .values_list('playlist_id', flat=True)
        )
        return SuccessResponse(
            data={'playlist_ids': list(playlist_ids)},
            message=f'Retrieved {len(playlist_ids)} collaborative playlists'
        )


class MyRoleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        # First check if user is the owner via cross-service call
        import os

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8000')
        auth_header = request.headers.get('Authorization', '')

        try:
            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/',
                headers={'Authorization': auth_header},
                timeout=5
            )

            if response.status_code == 200:
                response_json = response.json()
                # Core service wraps data in {"data": {...}} structure
                playlist_data = response_json.get('data', {})

                # Check if user is owner (for ALL playlist types, not just collaborative)
                if playlist_data.get('owner_id') == request.user.id:
                    return SuccessResponse(
                        data={'role': 'owner'},
                        message='User is the owner of this playlist'
                    )
        except requests.RequestException:
            pass  # Continue to collaborator check

        # Check if user is a collaborator
        try:
            Collaborator.objects.get(playlist_id=playlist_id, user_id=request.user.id)
            return SuccessResponse(
                data={'role': 'collaborator'},
                message='User is a collaborator'
            )
        except Collaborator.DoesNotExist:
            return SuccessResponse(
                data={'role': None},
                message='User is neither owner nor collaborator'
            )
