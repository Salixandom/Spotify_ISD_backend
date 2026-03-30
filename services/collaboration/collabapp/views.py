from rest_framework.views import APIView
from rest_framework import permissions

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
        - Users can always remove themselves
        - Playlist owners can remove any collaborator
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return ValidationErrorResponse(
                errors={'user_id': 'This field is required'},
                message='user_id required'
            )

        # Allow self-removal
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
                playlist_data = response.json()
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
        try:
            Collaborator.objects.get(playlist_id=playlist_id, user_id=request.user.id)
        except Collaborator.DoesNotExist:
            return NotFoundResponse(message='Not a collaborator')
        return SuccessResponse(
            data={'role': 'collaborator'},
            message='User is a collaborator'
        )
