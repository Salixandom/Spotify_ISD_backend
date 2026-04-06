from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
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
        description='Creates a shareable link for a public playlist. Only the playlist owner or collaborators can create share links. Share links allow anyone with the link to view the playlist without authentication. **Note:** Share links can only be created for public playlists. For private playlists, use invite links instead.',
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the playlist to create a share link for',
                required=True,
                example=123
            )
        ],
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Share link created successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {
                                'type': 'integer',
                                'description': 'Share link ID',
                                'example': 456
                            },
                            'token': {
                                'type': 'string',
                                'description': 'Unique share token',
                                'example': 'xyz789abc123'
                            },
                            'playlist_id': {
                                'type': 'integer',
                                'example': 123
                            },
                            'created_by_id': {
                                'type': 'integer',
                                'description': 'User ID who created the share link',
                                'example': 1
                            },
                            'created_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'When the share link was created',
                                'example': '2026-04-07T10:00:00Z'
                            },
                            'expires_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'When the share link expires (30 days from creation)',
                                'example': '2026-05-07T10:00:00Z'
                            },
                            'usage_count': {
                                'type': 'integer',
                                'description': 'Number of times the link has been viewed',
                                'example': 0
                            },
                            'share_url': {
                                'type': 'string',
                                'description': 'Full share URL to share with others',
                                'example': 'http://localhost:3000/share/xyz789abc123'
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'not_public': {
                        'summary': 'Playlist is not public',
                        'value': {
                            'success': False,
                            'message': 'Share links can only be created for public playlists. Use invite links for private playlists.'
                        }
                    },
                    'not_owner_or_collaborator': {
                        'summary': 'User is not authorized',
                        'value': {
                            'success': False,
                            'message': 'Only playlist owners and collaborators can create share links'
                        }
                    },
                    'playlist_archived': {
                        'summary': 'Playlist is archived by creator',
                        'value': {
                            'success': False,
                            'message': 'Cannot create share link for a hidden playlist'
                        }
                    }
                }
            },
            503: {
                'type': 'object',
                'examples': {
                    'core_service_unavailable': {
                        'summary': 'Core service is down',
                        'value': {
                            'success': False,
                            'message': 'Failed to verify playlist details'
                        }
                    }
                }
            }
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
        description='Retrieves playlist details from a share link token. This endpoint is publicly accessible (no authentication required) and increments the usage count each time the link is viewed. Returns playlist information including name, owner, visibility, and type. If the playlist has been archived by the creator, the link will be inactive.',
        parameters=[
            OpenApiParameter(
                name='token',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Share link token from URL',
                required=True,
                example='xyz789abc123'
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'valid_link': {
                        'summary': 'Valid share link with full details',
                        'value': {
                            'success': True,
                            'message': 'Share link is valid',
                            'data': {
                                'valid': True,
                                'playlist_id': 123,
                                'playlist_name': 'Summer Vibes 2026',
                                'owner_name': 'User 1',
                                'owner_id': 1,
                                'is_public': True,
                                'visibility': 'public',
                                'playlist_type': 'normal',
                                'share': {
                                    'id': 456,
                                    'token': 'xyz789abc123',
                                    'playlist_id': 123,
                                    'created_by_id': 1,
                                    'created_at': '2026-04-07T10:00:00Z',
                                    'expires_at': '2026-05-07T10:00:00Z',
                                    'usage_count': 42
                                }
                            }
                        }
                    },
                    'core_service_down': {
                        'summary': 'Valid link but core service unavailable',
                        'value': {
                            'success': True,
                            'message': 'Share link is valid (core service unavailable)',
                            'data': {
                                'valid': True,
                                'playlist_id': 123,
                                'playlist_name': 'Unknown Playlist',
                                'share': {
                                    'id': 456,
                                    'token': 'xyz789abc123',
                                    'playlist_id': 123,
                                    'created_by_id': 1,
                                    'created_at': '2026-04-07T10:00:00Z',
                                    'expires_at': '2026-05-07T10:00:00Z',
                                    'usage_count': 42
                                }
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'invalid_token': {
                        'summary': 'Share link token not found',
                        'value': {
                            'success': False,
                            'message': 'Invalid share link'
                        }
                    },
                    'expired': {
                        'summary': 'Share link has expired (30-day limit)',
                        'value': {
                            'success': False,
                            'message': 'Share link has expired'
                        }
                    },
                    'playlist_archived': {
                        'summary': 'Playlist archived by creator',
                        'value': {
                            'success': False,
                            'message': 'Share link is inactive for hidden playlist'
                        }
                    }
                }
            }
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
        description='Retrieves the number of users following the specified playlist. This count reflects all users who have followed the playlist, not just collaborators. The data is fetched from the core service which maintains the follower relationships.',
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the playlist to get followers count for',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'successful': {
                        'summary': 'Successfully retrieved followers count',
                        'value': {
                            'success': True,
                            'message': 'Followers count retrieved successfully',
                            'data': {
                                'followers_count': 42,
                                'playlist_id': 123
                            }
                        }
                    },
                    'no_followers': {
                        'summary': 'Playlist has no followers',
                        'value': {
                            'success': True,
                            'message': 'Followers count retrieved successfully',
                            'data': {
                                'followers_count': 0,
                                'playlist_id': 123
                            }
                        }
                    },
                    'service_unavailable': {
                        'summary': 'Core service unavailable (returns 0)',
                        'value': {
                            'success': True,
                            'message': 'Unable to fetch followers count',
                            'data': {
                                'followers_count': 0,
                                'playlist_id': 123
                            }
                        }
                    }
                }
            },
            503: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Failed to fetch followers information'
                }
            }
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
        description='Checks if the current authenticated user is following the specified playlist. This is different from being a collaborator - following is a one-way relationship where users receive updates about the playlist. The data is fetched from the core service which maintains follow relationships.',
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='ID of the playlist to check follow status for',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'following': {
                        'summary': 'User is following the playlist',
                        'value': {
                            'success': True,
                            'message': 'Follow status retrieved successfully',
                            'data': {
                                'is_following': True,
                                'playlist_id': 123
                            }
                        }
                    },
                    'not_following': {
                        'summary': 'User is not following the playlist',
                        'value': {
                            'success': True,
                            'message': 'Follow status retrieved successfully',
                            'data': {
                                'is_following': False,
                                'playlist_id': 123
                            }
                        }
                    },
                    'service_unavailable': {
                        'summary': 'Core service unavailable (returns false)',
                        'value': {
                            'success': True,
                            'message': 'Unable to check follow status',
                            'data': {
                                'is_following': False,
                                'playlist_id': 123
                            }
                        }
                    }
                }
            },
            503: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Failed to check follow status'
                }
            }
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
