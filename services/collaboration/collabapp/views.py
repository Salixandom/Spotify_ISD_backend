from rest_framework.views import APIView
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
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
        description="Generates a unique invite link for a playlist. The link can be shared to allow others to join as collaborators.",
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
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': InviteLinkSerializer
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
        description="Returns invite link details including playlist information. Used to preview what the user will join.",
        parameters=[
            OpenApiParameter(
                name='token',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Invite token',
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
                            'playlist_id': {'type': 'integer'},
                            'playlist_name': {'type': 'string'},
                            'inviter_name': {'type': 'string'},
                            'collaborators': {
                                'type': 'array',
                                'items': {'type': 'integer'}
                            },
                            'is_collaborative': {'type': 'boolean'},
                            'owner_id': {'type': 'integer'},
                            'valid': {'type': 'boolean'}
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
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
        description="Joins a collaborative playlist using an invite token. Converts the playlist to collaborative type if needed.",
        parameters=[
            OpenApiParameter(
                name='token',
                type=OpenApiTypes.STR,
                location=OpenApiParameter.PATH,
                description='Invite token',
                required=True
            )
        ],
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': CollaboratorSerializer
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
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
        description="Returns a list of all collaborators for a specific playlist.",
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
                        'type': 'array',
                        'items': CollaboratorSerializer
                    }
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
        description="Removes a collaborator from a playlist. Users can always remove themselves. Playlist owners can remove any collaborator.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID',
                required=True
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'user_id': {
                        'type': 'integer',
                        'description': 'ID of the collaborator to remove'
                    },
                    'owner_id': {
                        'type': 'integer',
                        'description': 'ID of the playlist owner (for owner verification)'
                    }
                }
            }
        },
        responses={
            204: {
                'description': 'Collaborator removed successfully'
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
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
        description="Leave a collaborative playlist. For collaborators: simply removes them. For owners: must transfer ownership to another collaborator first.",
        parameters=[
            OpenApiParameter(
                name='playlist_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Playlist ID',
                required=True
            )
        ],
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'new_owner_id': {
                        'type': 'integer',
                        'description': 'ID of the collaborator to transfer ownership to (required for owners)'
                    },
                    'stay_as_collaborator': {
                        'type': 'boolean',
                        'description': 'If true, owner stays as collaborator after transfer (optional)',
                        'default': False
                    }
                }
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
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

