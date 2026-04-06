from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
from drf_spectacular.types import OpenApiTypes
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

    @extend_schema(
        tags=["Health"],
        summary="Collaboration service health check",
        description="Check if the collaboration service and database are healthy",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'status': {'type': 'string'},
                            'service': {'type': 'string'},
                            'database': {'type': 'string'}
                        }
                    }
                }
            },
            503: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
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

    @extend_schema(
        tags=["Collaboration"],
        summary="Generate invite link",
        description="Generates a unique invite link for a playlist. Only the playlist owner can generate invites. The link can be shared with others to allow them to join as collaborators. Invite links include a token and expire after 7 days.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to generate invite for',
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
                        'example': 'Invite link generated successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer', 'example': 456},
                            'token': {
                                'type': 'string',
                                'description': 'Unique invite token',
                                'example': 'abc123xyz789'
                            },
                            'playlist_id': {'type': 'integer', 'example': 123},
                            'created_by_id': {'type': 'integer', 'example': 1},
                            'role': {
                                'type': 'string',
                                'enum': ['viewer', 'contributor', 'admin'],
                                'description': 'Role assigned to users who join',
                                'example': 'contributor'
                            },
                            'expires_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'When the invite link expires (7 days from creation)',
                                'example': '2026-04-14T10:00:00Z'
                            },
                            'invite_url': {
                                'type': 'string',
                                'description': 'Full invite URL to share',
                                'example': 'http://localhost:3000/invite/abc123xyz789'
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Only the playlist owner can generate invite links'
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist not found'
                }
            }
        }
    )
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

    @extend_schema(
        tags=["Collaboration"],
        summary="Get invite link details",
        description="Returns invite link details including playlist information, owner name, and current collaborators. Use this to preview what will happen before accepting an invite.",
        parameters=[
            OpenApiParameter(
                name='token',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Invite token from invite link',
                required=True,
                example='abc123xyz789'
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Invite details retrieved successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'token': {
                                'type': 'string',
                                'description': 'Invite token',
                                'example': 'abc123xyz789'
                            },
                            'playlist_id': {
                                'type': 'integer',
                                'description': 'Playlist ID',
                                'example': 123
                            },
                            'playlist_name': {
                                'type': 'string',
                                'description': 'Playlist name',
                                'example': 'Team Workout Mix'
                            },
                            'role': {
                                'type': 'string',
                                'enum': ['viewer', 'contributor', 'admin'],
                                'description': 'Role you will receive when you join',
                                'example': 'contributor'
                            },
                            'inviter_name': {
                                'type': 'string',
                                'description': 'Name of the user who created the invite',
                                'example': 'John Doe'
                            },
                            'collaborator_count': {
                                'type': 'integer',
                                'description': 'Number of current collaborators',
                                'example': 5
                            },
                            'is_collaborative': {
                                'type': 'boolean',
                                'description': 'Whether this is a collaborative playlist',
                                'example': True
                            },
                            'owner_id': {
                                'type': 'integer',
                                'description': 'User ID of playlist owner',
                                'example': 1
                            },
                            'valid': {
                                'type': 'boolean',
                                'description': 'Whether the invite is still valid (not expired)',
                                'example': True
                            },
                            'expires_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'description': 'When the invite expires',
                                'example': '2026-04-14T10:00:00Z'
                            }
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'invalid_token': {
                        'summary': 'Invite token not found',
                        'value': {
                            'success': False,
                            'message': 'Invalid link'
                        }
                    },
                    'expired': {
                        'summary': 'Invite link has expired',
                        'value': {
                            'success': False,
                            'message': 'Invalid link'
                        }
                    }
                }
            }
        }
    )
    def get(self, request, token):
        """
        GET /api/collab/join/<token>/

        Returns invite link details including playlist name from core service.
        Passes user's auth header to core service to authorize the request.
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            invite = InviteLink.objects.get(token=token)
        except InviteLink.DoesNotExist:
            return NotFoundResponse(message='Invalid link')
        if not invite.is_valid:
            return NotFoundResponse(message='Invalid link')

        # Fetch playlist details from core service
        import os

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')

        try:
            # Get playlist details from core service
            # Pass the user's auth header to authorize with core service
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            headers = {}
            if auth_header:
                headers['Authorization'] = auth_header
                logger.info(f"Passing auth header to core service: {auth_header[:20]}...")
            else:
                logger.warning("No auth header found in request")

            logger.info(f"Fetching playlist {invite.playlist_id} from core service at {core_service_url}")

            response = requests.get(
                f'{core_service_url}/api/playlists/{invite.playlist_id}/',
                headers=headers,
                timeout=5
            )

            logger.info(f"Core service response status: {response.status_code}")
            logger.info(f"Core service response: {response.text[:500]}")

            if response.status_code == 200:
                response_json = response.json()
                logger.info(f"Response JSON keys: {response_json.keys()}")

                # Core service wraps data in {"data": {...}} structure
                playlist_data = response_json.get('data', response_json)
                logger.info(f"Playlist data keys: {playlist_data.keys()}")
                logger.info(f"Playlist name: {playlist_data.get('name')}")
                logger.info(f"Playlist type: {playlist_data.get('playlist_type')}")

                # Get owner_id from playlist data
                owner_id = playlist_data.get('owner_id')

                # Get existing collaborators to check if user is already one
                existing_collaborators = Collaborator.objects.filter(
                    playlist_id=invite.playlist_id
                ).values_list('user_id', flat=True)

                # Check if requesting user is already a collaborator
                is_already_collaborator = request.user.id in existing_collaborators

                return SuccessResponse(
                    data={
                        'playlist_id': invite.playlist_id,
                        'playlist_name': playlist_data.get('name', 'Unknown Playlist'),
                        'inviter_name': f'User {invite.created_by_id}',
                        'collaborators': list(existing_collaborators),
                        'is_collaborative': playlist_data.get('playlist_type') == 'collaborative',
                        'owner_id': owner_id,
                        'valid': True
                    },
                    message='Invite link is valid'
                )
            else:
                # If core service returns error, log it and return basic info
                logger.warning(f"Core service returned {response.status_code}: {response.text[:200]}")
                return SuccessResponse(
                    data={
                        'playlist_id': invite.playlist_id,
                        'playlist_name': 'Unknown Playlist',
                        'inviter_name': f'User {invite.created_by_id}',
                        'collaborators': [],
                        'is_collaborative': False,
                        'valid': True
                    },
                    message='Invite link is valid (playlist details unavailable)'
                )
        except requests.RequestException as e:
            # If core service is down, still return valid invite with basic info
            logger.error(f"Core service request failed: {e}")
            return SuccessResponse(
                data={
                    'playlist_id': invite.playlist_id,
                    'playlist_name': 'Unknown Playlist',
                    'inviter_name': f'User {invite.created_by_id}',
                    'collaborators': [],
                    'is_collaborative': False,
                    'valid': True
                },
                message='Invite link is valid (core service unavailable)'
            )

    @extend_schema(
        tags=["Collaboration"],
        summary="Join playlist via invite",
        description="Accept an invite and join a collaborative playlist. You will be added as a collaborator with the role specified in the invite. If the playlist is not collaborative, it will be converted automatically. Accepting is idempotent - if you're already a collaborator, returns success.",
        parameters=[
            OpenApiParameter(
                name='token',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Invite token from invite link',
                required=True,
                example='abc123xyz789'
            )
        ],
        responses={
            201: {
                'type': 'object',
                'examples': {
                    'joined_successfully': {
                        'summary': 'Successfully joined playlist',
                        'value': {
                            'success': True,
                            'message': 'Successfully joined playlist',
                            'data': {
                                'id': 789,
                                'playlist_id': 123,
                                'user_id': 456,
                                'role': 'contributor',
                                'joined_at': '2026-04-07T19:00:00Z'
                            }
                        }
                    },
                    'already_collaborator': {
                        'summary': 'Already a collaborator (idempotent)',
                        'value': {
                            'success': True,
                            'message': 'You are already a collaborator on this playlist',
                            'data': {
                                'id': 789,
                                'playlist_id': 123,
                                'user_id': 456,
                                'role': 'contributor',
                                'joined_at': '2026-04-06T10:00:00Z'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'owner_cannot_join': {
                        'summary': 'Playlist owner cannot join via invite',
                        'value': {
                            'success': False,
                            'message': 'Playlist owner cannot join their own playlist via invite'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'invalid_token': {
                        'summary': 'Invite token not found or expired',
                        'value': {
                            'success': False,
                            'message': 'Invalid link'
                        }
                    }
                }
            }
        }
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
            auth_header = request.headers.get('Authorization', '')
            self._update_playlist_type_to_collaborative(invite.playlist_id, auth_header)

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

    def _update_playlist_type_to_collaborative(self, playlist_id, auth_header=''):
        """Update playlist type to collaborative in core service."""
        import requests
        import os
        import logging
        logger = logging.getLogger(__name__)

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')
        try:
            logger.info(f"Attempting to update playlist {playlist_id} to collaborative type")
            # Get current playlist data first to check if update is needed
            headers = {}
            if auth_header:
                headers['Authorization'] = auth_header

            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/',
                headers=headers,
                timeout=5
            )
            logger.info(f"GET response status: {response.status_code}")
            if response.status_code == 200:
                response_json = response.json()
                logger.info(f"GET response: {response.text[:300]}")
                # Core service wraps data in {"data": {...}} structure
                playlist_data = response_json.get('data', {})
                current_type = playlist_data.get('playlist_type')
                logger.info(f"Current playlist type: {current_type}")

                if current_type != 'collaborative':
                    # Update to collaborative
                    logger.info(f"Updating playlist {playlist_id} from {current_type} to collaborative")
                    update_response = requests.patch(
                        f'{core_service_url}/api/playlists/{playlist_id}/',
                        json={'playlist_type': 'collaborative'},
                        headers=headers,
                        timeout=5
                    )
                    logger.info(f"PATCH response status: {update_response.status_code}")
                    logger.info(f"PATCH response: {update_response.text[:300]}")
                    if update_response.status_code == 200:
                        logger.info(f"Successfully updated playlist {playlist_id} type to collaborative")
                    else:
                        logger.warning(f"Failed to update playlist {playlist_id} type: {update_response.status_code}")
                else:
                    logger.info(f"Playlist {playlist_id} is already collaborative")
        except Exception as e:
            logger.error(f"Exception during playlist type update for {playlist_id}: {e}", exc_info=True)
            # Non-critical: type update failure should not block joining


class CollaboratorListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Collaboration"],
        summary="List playlist collaborators",
        description="Returns a list of all collaborators for a specific playlist along with their roles. Shows who has access to the playlist and what they can do based on their role (viewer, contributor, admin).",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to get collaborators for',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'Retrieved 5 collaborators'
                    },
                    'data': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer', 'example': 789},
                                'playlist_id': {'type': 'integer', 'example': 123},
                                'user_id': {'type': 'integer', 'example': 456},
                                'role': {
                                    'type': 'string',
                                    'enum': ['viewer', 'contributor', 'admin'],
                                    'description': 'Collaborator role determining permissions',
                                    'example': 'contributor'
                                },
                                'joined_at': {
                                    'type': 'string',
                                    'format': 'date-time',
                                    'description': 'When this user became a collaborator',
                                    'example': '2026-04-07T15:30:00Z'
                                },
                                'invited_by': {
                                    'type': 'integer',
                                    'description': 'User ID who invited this collaborator',
                                    'example': 1
                                }
                            }
                        },
                        'description': 'List of collaborators with their roles'
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Not authorized to view collaborators'
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist not found'
                }
            }
        }
    )
    def get(self, request, playlist_id):
        collabs = Collaborator.objects.filter(playlist_id=playlist_id)
        return SuccessResponse(
            data=CollaboratorSerializer(collabs, many=True).data,
            message=f'Retrieved {collabs.count()} collaborators'
        )

    @extend_schema(
        tags=["Collaboration"],
        summary="Remove collaborator",
        description="Removes a collaborator from a playlist. **Self-removal:** Users can always remove themselves without any additional parameters. **Owner removal:** Playlist owners can remove any collaborator by providing the owner_id in the request body.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to remove collaborator from',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_id': {
                        'type': 'integer',
                        'description': 'Required when owner is removing someone else. ID of the collaborator to remove.',
                        'example': 456
                    },
                    'owner_id': {
                        'type': 'integer',
                        'description': 'Required when owner is removing someone else. ID of the playlist owner (your user ID) to verify ownership.',
                        'example': 1
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Remove yourself (self-removal)',
                description='Remove yourself from a collaborative playlist',
                value={'user_id': 456}
            ),
            OpenApiExample(
                'Remove as owner',
                description='Owner removing a collaborator (must provide both user_id and owner_id)',
                value={
                    'user_id': 789,
                    'owner_id': 1
                }
            )
        ],
        responses={
            204: {
                'description': 'Collaborator removed successfully (no content returned)'
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_user_id': {
                        'summary': 'user_id not provided',
                        'value': {
                            'success': False,
                            'message': 'user_id required',
                            'errors': {
                                'user_id': ['This field is required.']
                            }
                        }
                    },
                    'not_owner': {
                        'summary': 'Requester is not the owner',
                        'value': {
                            'success': False,
                            'message': 'Only the playlist owner can remove other collaborators'
                        }
                    },
                    'owner_mismatch': {
                        'summary': 'owner_id does not match actual owner',
                        'value': {
                            'success': False,
                            'message': 'Owner ID does not match playlist owner'
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Not authorized to remove collaborators'
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Playlist or collaborator not found'
                }
            }
        }
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

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')
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

    @extend_schema(
        tags=["Collaboration"],
        summary="Get my collaborations",
        description="Returns a list of playlist IDs where the authenticated user is a collaborator.",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'playlist_ids': {
                                'type': 'array',
                                'items': {'type': 'integer'}
                            }
                        }
                    }
                }
            }
        }
    )
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

    @extend_schema(
        tags=["Collaboration"],
        summary="Get my role in playlist",
        description="Returns the authenticated user's role for a specific playlist (owner, collaborator, or none).",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID',
                required=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'role': {
                                'type': 'string',
                                'enum': ['owner', 'collaborator', None]
                            }
                        }
                    }
                }
            }
        }
    )
    def get(self, request, playlist_id):
        # First check if user is the owner via cross-service call
        import os

        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')
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


class LeavePlaylistView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["Collaboration"],
        summary="Leave collaborative playlist",
        description="Leave a collaborative playlist. **For collaborators:** Simply removes you from the playlist. **For owners:** Must transfer ownership to another collaborator first by providing new_owner_id. After transferring ownership, you can optionally stay as a collaborator (stay_as_collaborator=true) or leave completely (default).",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID to leave',
                required=True,
                example=123
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'new_owner_id': {
                        'type': 'integer',
                        'description': 'ID of the collaborator to transfer ownership to (required for owners, must be an existing collaborator)',
                        'example': 456
                    },
                    'stay_as_collaborator': {
                        'type': 'boolean',
                        'description': 'If true, owner stays as collaborator after transferring ownership. If false or not provided, owner leaves completely.',
                        'example': False,
                        'default': False
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Collaborator leaves',
                description='A collaborator leaving the playlist (no body required)',
                value=None
            ),
            OpenApiExample(
                'Owner transfers and leaves',
                description='Owner transfers ownership to another collaborator and leaves completely',
                value={
                    'new_owner_id': 456,
                    'stay_as_collaborator': False
                }
            ),
            OpenApiExample(
                'Owner transfers and stays',
                description='Owner transfers ownership but stays as a collaborator',
                value={
                    'new_owner_id': 456,
                    'stay_as_collaborator': True
                }
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'collaborator_left': {
                        'summary': 'Collaborator left successfully',
                        'value': {
                            'success': True,
                            'message': 'Left playlist successfully'
                        }
                    },
                    'owner_transferred_and_left': {
                        'summary': 'Owner transferred ownership and left',
                        'value': {
                            'success': True,
                            'message': 'Left playlist successfully'
                        }
                    },
                    'owner_transferred_and_stayed': {
                        'summary': 'Owner transferred ownership and stayed as collaborator',
                        'value': {
                            'success': True,
                            'message': 'Ownership transferred successfully'
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'owner_missing_new_owner_id': {
                        'summary': 'Owner must provide new_owner_id',
                        'value': {
                            'success': False,
                            'message': 'Owners must transfer ownership before leaving. Please provide new_owner_id.'
                        }
                    },
                    'new_owner_not_collaborator': {
                        'summary': 'The selected new owner is not a collaborator',
                        'value': {
                            'success': False,
                            'message': 'Selected user is not a collaborator on this playlist'
                        }
                    },
                    'ownership_transfer_failed': {
                        'summary': 'Core service rejected ownership transfer',
                        'value': {
                            'success': False,
                            'message': 'Failed to transfer ownership'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'examples': {
                    'not_a_collaborator': {
                        'summary': 'User is not a collaborator on this playlist',
                        'value': {
                            'success': False,
                            'message': 'You are not a collaborator on this playlist'
                        }
                    },
                    'playlist_not_found': {
                        'summary': 'Playlist does not exist',
                        'value': {
                            'success': False,
                            'message': 'Failed to verify playlist ownership'
                        }
                    }
                }
            },
            503: {
                'type': 'object',
                'examples': {
                    'core_service_unavailable': {
                        'summary': 'Core service is down or unreachable',
                        'value': {
                            'success': False,
                            'message': 'Failed to verify ownership: Connection refused'
                        }
                    }
                }
            }
        }
    )
    def post(self, request, playlist_id):
        """
        Leave a collaborative playlist.

        For collaborators: Simply removes them from the playlist.
        For owners: Must transfer ownership to another collaborator first.

        Body params (for owners only):
            new_owner_id (required) - ID of the collaborator to transfer ownership to
            stay_as_collaborator (optional) - If true, owner stays as collaborator after transfer
        """
        import os
        import logging

        logger = logging.getLogger(__name__)
        core_service_url = os.getenv('CORE_SERVICE_URL', 'http://core:8002')
        auth_header = request.headers.get('Authorization', '')

        # Check if user is owner
        try:
            response = requests.get(
                f'{core_service_url}/api/playlists/{playlist_id}/',
                headers={'Authorization': auth_header},
                timeout=5
            )

            if response.status_code != 200:
                return ServiceUnavailableResponse(message='Failed to verify playlist ownership')

            response_json = response.json()
            # Core service wraps data in {"data": {...}} structure
            playlist_data = response_json.get('data', {})
            is_owner = playlist_data.get('owner_id') == request.user.id
            playlist_type = playlist_data.get('playlist_type')

        except requests.RequestException as e:
            logger.error(f"Failed to verify ownership for playlist {playlist_id}: {e}")
            return ServiceUnavailableResponse(message=f'Failed to verify ownership: {str(e)}')

        # Owner must transfer ownership first
        if is_owner:
            new_owner_id = request.data.get('new_owner_id')
            stay_as_collaborator = request.data.get('stay_as_collaborator', False)

            if not new_owner_id:
                return ValidationErrorResponse(
                    message='Owners must transfer ownership before leaving. Please provide new_owner_id.'
                )

            # Verify new owner is a collaborator
            try:
                Collaborator.objects.get(playlist_id=playlist_id, user_id=new_owner_id)
            except Collaborator.DoesNotExist:
                return ValidationErrorResponse(
                    message='Selected user is not a collaborator on this playlist'
                )

            # Transfer ownership via core service
            try:
                transfer_response = requests.post(
                    f'{core_service_url}/api/playlists/{playlist_id}/transfer-ownership/',
                    json={'new_owner_id': new_owner_id},
                    headers={'Authorization': auth_header},
                    timeout=5
                )

                if transfer_response.status_code != 200:
                    logger.error(f"Ownership transfer failed: {transfer_response.text}")
                    return ServiceUnavailableResponse(message='Failed to transfer ownership')

                logger.info(f"Ownership of playlist {playlist_id} transferred from {request.user.id} to {new_owner_id}")

            except requests.RequestException as e:
                logger.error(f"Exception during ownership transfer: {e}")
                return ServiceUnavailableResponse(message=f'Failed to transfer ownership: {str(e)}')

            # If owner doesn't want to stay as collaborator, remove them
            if not stay_as_collaborator:
                Collaborator.objects.filter(playlist_id=playlist_id, user_id=request.user.id).delete()

            return SuccessResponse(
                message='Ownership transferred successfully' if stay_as_collaborator else 'Left playlist successfully'
            )

        # Collaborator: simply remove them
        try:
            collaborator = Collaborator.objects.get(playlist_id=playlist_id, user_id=request.user.id)
            collaborator.delete()
            logger.info(f"User {request.user.id} left playlist {playlist_id}")

            # Unfollow the playlist in core service
            try:
                requests.post(
                    f'{core_service_url}/api/playlists/{playlist_id}/unfollow/',
                    headers={'Authorization': auth_header},
                    timeout=5
                )
                logger.info(f"Auto-unfollowed playlist {playlist_id} for user {request.user.id}")
            except Exception as e:
                logger.warning(f"Failed to auto-unfollow playlist {playlist_id}: {e}")
                # Non-critical: unfollow failure should not block leaving

            return SuccessResponse(message='Left playlist successfully')

        except Collaborator.DoesNotExist:
            return NotFoundResponse(message='You are not a collaborator on this playlist')

