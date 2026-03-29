from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
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
            return Response(
                {'status': 'healthy', 'service': 'collaboration', 'database': 'connected'},
                status=200,
            )
        except Exception as e:
            return Response(
                {
                    'status': 'unhealthy',
                    'service': 'collaboration',
                    'database': 'disconnected',
                    'error': str(e),
                },
                status=503,
            )


class GenerateInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        invite = InviteLink.objects.create(
            playlist_id=playlist_id,
            created_by_id=request.user.id,
        )
        return Response(InviteLinkSerializer(invite).data, status=status.HTTP_201_CREATED)


class JoinView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, token):
        try:
            invite = InviteLink.objects.get(token=token)
        except InviteLink.DoesNotExist:
            return Response({'valid': False}, status=status.HTTP_404_NOT_FOUND)
        if not invite.is_valid:
            return Response({'valid': False}, status=status.HTTP_404_NOT_FOUND)
        return Response({'playlist_id': invite.playlist_id, 'valid': True})

    def post(self, request, token):
        try:
            invite = InviteLink.objects.get(token=token)
        except InviteLink.DoesNotExist:
            return Response({'error': 'Invalid link'}, status=status.HTTP_404_NOT_FOUND)
        if not invite.is_valid:
            return Response({'error': 'Invalid link'}, status=status.HTTP_404_NOT_FOUND)

        collab, created = Collaborator.objects.get_or_create(
            playlist_id=invite.playlist_id,
            user_id=request.user.id,
        )
        if not created:
            return Response({'error': 'already_member'}, status=status.HTTP_200_OK)
        return Response(CollaboratorSerializer(collab).data, status=status.HTTP_201_CREATED)


class CollaboratorListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        collabs = Collaborator.objects.filter(playlist_id=playlist_id)
        return Response(CollaboratorSerializer(collabs, many=True).data)

    def delete(self, request, playlist_id):
        """
        Remove a collaborator from a playlist.

        Authorization:
        - Users can always remove themselves
        - Playlist owners can remove any collaborator
        """
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=status.HTTP_400_BAD_REQUEST)

        # Allow self-removal
        if str(user_id) == str(request.user.id):
            Collaborator.objects.filter(playlist_id=playlist_id, user_id=user_id).delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

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
                    return Response(status=status.HTTP_204_NO_CONTENT)

        except requests.RequestException as e:
            return Response(
                {'error': f'Failed to verify ownership: {str(e)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)


class MyCollaborationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        playlist_ids = (
            Collaborator.objects.filter(user_id=request.user.id)
            .values_list('playlist_id', flat=True)
        )
        return Response({'playlist_ids': list(playlist_ids)})


class MyRoleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        try:
            Collaborator.objects.get(playlist_id=playlist_id, user_id=request.user.id)
        except Collaborator.DoesNotExist:
            return Response({'error': 'Not a collaborator'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'role': 'collaborator'})


