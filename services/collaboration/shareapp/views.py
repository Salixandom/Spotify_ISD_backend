from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from drf_spectacular.types import OpenApiTypes

from utils.responses import (
    SuccessResponse,
    NotFoundResponse,
    ServiceUnavailableResponse,
    ForbiddenResponse,
)
from django.db import connection
from .models import ShareLink
from .serializers import ShareLinkSerializer


class CreateShareLinkView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Sharing'],
        summary='Create share link',
        description='Creates a shareable link for a public playlist. Only the owner or collaborators can create share links.',
        parameters=[OpenApiParameter(
            name='playlist_id',
            type=int,
            location=OpenApiParameter.PATH,
            description='ID of the playlist to create a share link for'
        )],
        responses={
            201: ShareLinkSerializer,
            403: OpenApiTypes.OBJECT,
            503: OpenApiTypes.OBJECT,
        }
    )
    def post(self, request, playlist_id):
        import requests
        import os
        import logging
        logger = logging.getLogger(__name__)

        # Check playlist visibility and owner info via core service
        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')
        try:
            # Get auth header to pass to core service
            auth_header = request.headers.get('Authorization', '')
            headers = {}
            if auth_header:
                headers['Authorization'] = auth_header

            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/',
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                response_json = response.json()
                playlist_data = response_json.get('data', response_json)
                visibility = playlist_data.get('visibility')
                owner_id = playlist_data.get('owner_id')
                playlist_type = playlist_data.get('playlist_type')

                # Only allow share links for public playlists
                if visibility != 'public':
                    return ForbiddenResponse(
                        message='Share links can only be created for public playlists. Use invite links for private playlists.'
                    )

                # Check if user is owner or collaborator
                is_owner = (owner_id == request.user.id)

                # If not owner, check if collaborator
                is_collaborator = False
                if not is_owner:
                    try:
                        from utils.service_clients import CollaborationServiceClient
                        is_collaborator = CollaborationServiceClient.is_collaborator(
                            playlist_id=playlist_id,
                            user_id=request.user.id,
                            auth_token=auth_header
                        )
                    except Exception as e:
                        logger.warning(f"Failed to check collaborator status: {e}")

                # Only owners and collaborators can create share links
                if not is_owner and not is_collaborator:
                    return ForbiddenResponse(
                        message='Only playlist owners and collaborators can create share links'
                    )

        except requests.RequestException as e:
            logger.error(f"Failed to verify playlist details: {e}")
            return ServiceUnavailableResponse(message='Failed to verify playlist details')

        # Check if playlist is archived by the user
        is_archived = False
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM playlistapp_userplaylistarchive WHERE playlist_id = %s AND user_id = %s",
                [playlist_id, request.user.id]
            )
            if cursor.fetchone():
                is_archived = True

        if is_archived:
            return ForbiddenResponse(message='Cannot create share link for a hidden playlist')

        share = ShareLink.objects.create(
            playlist_id=playlist_id,
            created_by_id=request.user.id,
        )

        # Generate share URL
        share_url = f'{os.getenv("FRONTEND_URL", "http://localhost:3000")}/share/{share.token}'

        return SuccessResponse(
            data={
                **ShareLinkSerializer(share).data,
                'share_url': share_url
            },
            message='Share link created successfully',
            status_code=201
        )


class ViewShareLinkView(APIView):
    permission_classes = [permissions.AllowAny]  # Allow anyone to access shared playlists

    @extend_schema(
        tags=['Sharing'],
        summary='View share link',
        description='Retrieves playlist details from a share link token. Increments the usage count.',
        parameters=[OpenApiParameter(
            name='token',
            type=str,
            location=OpenApiParameter.PATH,
            description='Share link token'
        )],
        responses={
            200: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
        }
    )
    def get(self, request, token):
        import requests
        import os
        import logging
        logger = logging.getLogger(__name__)

        try:
            share = ShareLink.objects.get(token=token)
        except ShareLink.DoesNotExist:
            return NotFoundResponse(message='Invalid share link')

        if not share.is_valid:
            return NotFoundResponse(message='Share link has expired')

        # Check if playlist is currently archived by the link creator
        is_archived = False
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM playlistapp_userplaylistarchive WHERE playlist_id = %s AND user_id = %s",
                [share.playlist_id, share.created_by_id]
            )
            if cursor.fetchone():
                is_archived = True

        if is_archived:
            return NotFoundResponse(message='Share link is inactive for hidden playlist')

        # Increment usage count
        share.usage_count += 1
        share.save(update_fields=['usage_count'])

        # Fetch playlist details from core service
        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')
        try:
            # Get auth header if user is authenticated
            auth_header = request.headers.get('Authorization', '')
            headers = {}
            if auth_header:
                headers['Authorization'] = auth_header

            response = requests.get(
                f'{core_service_url}/api/playlists/{share.playlist_id}/',
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                response_json = response.json()
                playlist_data = response_json.get('data', response_json)

                return SuccessResponse(
                    data={
                        'valid': True,
                        'playlist_id': share.playlist_id,
                        'playlist_name': playlist_data.get('name', 'Unknown Playlist'),
                        'owner_name': f'User {playlist_data.get("owner_id")}',  # Can be enhanced with user service
                        'owner_id': playlist_data.get('owner_id'),
                        'is_public': playlist_data.get('visibility') == 'public',
                        'visibility': playlist_data.get('visibility'),
                        'playlist_type': playlist_data.get('playlist_type'),
                        'share': ShareLinkSerializer(share).data,
                    },
                    message='Share link is valid'
                )
            else:
                # If core service fails, return basic info
                return SuccessResponse(
                    data={
                        'valid': True,
                        'playlist_id': share.playlist_id,
                        'playlist_name': 'Unknown Playlist',
                        'share': ShareLinkSerializer(share).data,
                    },
                    message='Share link is valid (playlist details unavailable)'
                )
        except requests.RequestException as e:
            logger.error(f"Failed to fetch playlist details: {e}")
            # If core service is down, still return valid with basic info
            return SuccessResponse(
                data={
                    'valid': True,
                    'playlist_id': share.playlist_id,
                    'playlist_name': 'Unknown Playlist',
                    'share': ShareLinkSerializer(share).data,
                },
                message='Share link is valid (core service unavailable)'
            )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=['Health'],
    summary='Health check',
    description='Checks if the share service and database are running properly',
    responses={
        200: OpenApiTypes.OBJECT,
        503: OpenApiTypes.OBJECT,
    }
)
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return SuccessResponse(
            data={'status': 'healthy', 'service': 'share', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )


class FollowersListView(APIView):
    """
    GET /api/share/<int:playlist_id>/followers/ - Get list of followers
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Sharing'],
        summary='Get followers count',
        description='Retrieves the number of followers for a playlist',
        parameters=[OpenApiParameter(
            name='playlist_id',
            type=int,
            location=OpenApiParameter.PATH,
            description='ID of the playlist'
        )],
        responses={
            200: OpenApiTypes.OBJECT,
            503: OpenApiTypes.OBJECT,
        }
    )
    def get(self, request, playlist_id):
        """Get list of followers for a playlist from core service"""
        import requests
        import os
        import logging
        logger = logging.getLogger(__name__)

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')

        try:
            # Get auth header
            auth_header = request.headers.get('Authorization', '')
            headers = {}
            if auth_header:
                headers['Authorization'] = auth_header

            # Query core service for followers count
            # Note: Core service uses UserPlaylistFollow model
            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/',
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                response_json = response.json()
                playlist_data = response_json.get('data', response_json)

                # Get followers count from playlist data
                followers_count = playlist_data.get('followers_count', 0)

                return SuccessResponse(
                    data={
                        'followers_count': followers_count,
                        'playlist_id': playlist_id
                    },
                    message='Followers count retrieved successfully'
                )
            else:
                return SuccessResponse(
                    data={
                        'followers_count': 0,
                        'playlist_id': playlist_id
                    },
                    message='Unable to fetch followers count'
                )

        except requests.RequestException as e:
            logger.error(f"Failed to fetch followers: {e}")
            return ServiceUnavailableResponse(
                message='Failed to fetch followers information'
            )


class IsFollowingView(APIView):
    """
    GET /api/share/<int:playlist_id>/is-following/ - Check if current user is following
    """
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=['Sharing'],
        summary='Check follow status',
        description='Checks if the current authenticated user is following the playlist',
        parameters=[OpenApiParameter(
            name='playlist_id',
            type=int,
            location=OpenApiParameter.PATH,
            description='ID of the playlist'
        )],
        responses={
            200: OpenApiTypes.OBJECT,
            503: OpenApiTypes.OBJECT,
        }
    )
    def get(self, request, playlist_id):
        """Check if current user is following the playlist"""
        import requests
        import os
        import logging
        logger = logging.getLogger(__name__)

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')

        try:
            # Get auth header
            auth_header = request.headers.get('Authorization', '')
            headers = {}
            if auth_header:
                headers['Authorization'] = auth_header

            # Check with core service if user is following
            # We use the /stats/ endpoint which includes is_followed field
            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/stats/',
                headers=headers,
                timeout=5
            )

            if response.status_code == 200:
                response_json = response.json()
                playlist_data = response_json.get('data', response_json)

                # Check if current user is following (note: core service returns 'is_followed')
                is_following = playlist_data.get('is_followed', False)

                return SuccessResponse(
                    data={
                        'is_following': is_following,
                        'playlist_id': playlist_id
                    },
                    message='Follow status retrieved successfully'
                )
            else:
                return SuccessResponse(
                    data={
                        'is_following': False,
                        'playlist_id': playlist_id
                    },
                    message='Unable to check follow status'
                )

        except requests.RequestException as e:
            logger.error(f"Failed to check follow status: {e}")
            return ServiceUnavailableResponse(
                message='Failed to check follow status'
            )
