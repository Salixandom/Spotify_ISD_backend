from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from drf_spectacular.types import OpenApiTypes
from .serializers import RegisterSerializer, UserSerializer, UserProfileSerializer, PublicUserProfileSerializer, UserFollowSerializer, ChangePasswordSerializer
from django.contrib.auth.models import User
from django.db import connection

from utils.responses import (
    SuccessResponse,
    ValidationErrorResponse,
    ServiceUnavailableResponse,
    NotFoundResponse,
    ForbiddenResponse,
    UnauthorizedResponse,
)


class CustomTokenRefreshView(APIView):
    """
    Custom token refresh view that returns JWT tokens in our standardized response format.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Refresh access token",
        description="Refresh an expired access token using a valid refresh token",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'refresh': {'type': 'string', 'description': 'JWT refresh token'}
                },
                'required': ['refresh']
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'access': {'type': 'string', 'description': 'New JWT access token'}
                        }
                    }
                }
            },
            401: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def post(self, request, *args, **kwargs):
        from rest_framework_simplejwt.serializers import TokenRefreshSerializer

        serializer = TokenRefreshSerializer(data=request.data)

        if not serializer.is_valid():
            return UnauthorizedResponse(
                message='Invalid refresh token'
            )

        # Return refreshed access token in our standardized format
        return SuccessResponse(
            data=serializer.validated_data,
            message='Token refreshed successfully'
        )


class CustomTokenObtainPairView(APIView):
    """
    Custom login view that returns JWT tokens in our standardized response format.
    """
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="User login",
        description="Authenticate with username/password and receive JWT tokens",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {'type': 'string', 'description': 'Username'},
                    'password': {'type': 'string', 'description': 'Password', 'format': 'password'}
                },
                'required': ['username', 'password']
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'access': {'type': 'string', 'description': 'JWT access token'},
                            'refresh': {'type': 'string', 'description': 'JWT refresh token'}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            }
        }
    )
    def post(self, request, *args, **kwargs):
        from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

        serializer = TokenObtainPairSerializer(data=request.data)

        if not serializer.is_valid():
            return ValidationErrorResponse(
                errors=serializer.errors,
                message='Invalid credentials'
            )

        # Return tokens in our standardized format
        return SuccessResponse(
            data=serializer.validated_data,
            message='Login successful'
        )


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="Register new user",
        description="Create a new user account. A profile is automatically created.",
        request=RegisterSerializer,
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': RegisterSerializer
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            }
        }
    )
    def post(self, request):
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Registration request data: {request.data}")
        logger.info(f"Request headers: {dict(request.headers)}")

        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(
                data=serializer.data,
                message='User registered successfully',
                status_code=201
            )
        logger.warning(f"Registration validation failed: {serializer.errors}")
        return ValidationErrorResponse(
            errors=serializer.errors,
            message='Registration failed'
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Get current user info",
        description="Retrieve basic information about the authenticated user",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': UserSerializer
                }
            }
        }
    )
    def get(self, request):
        serializer = UserSerializer(request.user)
        return SuccessResponse(
            data=serializer.data,
            message='User profile retrieved successfully'
        )


@api_view(["GET"])
@permission_classes([AllowAny])
@extend_schema(
    tags=["Health"],
    summary="Health check",
    description="Check if the auth service and database are healthy",
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
def health_check(request):
    """
    Health check endpoint for monitoring and orchestration
    Returns 200 if service and database are healthy
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return SuccessResponse(
            data={'status': 'healthy', 'service': 'auth', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )


class MyProfileView(APIView):
    """
    Get or update the authenticated user's profile.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Profile"],
        summary="Get my profile",
        description="Retrieve the authenticated user's full profile",
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': UserProfileSerializer
                }
            }
        }
    )
    def get(self, request):
        """Get my profile"""
        from .models import UserProfile

        profile, created = UserProfile.objects.get_or_create(
            user_id=request.user.id
        )

        serializer = UserProfileSerializer(profile)
        return SuccessResponse(
            data=serializer.data,
            message='Profile retrieved successfully'
        )

    @extend_schema(
        tags=["Profile"],
        summary="Update my profile",
        description="Update the authenticated user's profile. All fields are optional.",
        request=UserProfileSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': UserProfileSerializer
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            }
        }
    )
    def put(self, request):
        """Update my profile"""
        from .models import UserProfile

        profile, created = UserProfile.objects.get_or_create(
            user_id=request.user.id
        )

        serializer = UserProfileSerializer(profile, data=request.data, partial=True)
        if not serializer.is_valid():
            return ValidationErrorResponse(
                errors=serializer.errors,
                message='Validation failed'
            )

        serializer.save()
        return SuccessResponse(
            data=serializer.data,
            message='Profile updated successfully'
        )


class PublicProfileView(APIView):
    """
    Get a user's public profile.
    Respects privacy settings - only shows public info for non-owners.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Profile"],
        summary="Get user profile",
        description="Get a user's profile. Respects privacy settings (public, followers, private). Your own profile always shows full data.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID',
                required=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': PublicUserProfileSerializer
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def get(self, request, user_id):
        """Get user's public profile"""
        from .models import UserProfile

        try:
            profile = UserProfile.objects.get(user_id=user_id)
        except UserProfile.DoesNotExist:
            # Create default profile if it doesn't exist
            profile = UserProfile.objects.create(user_id=user_id)

        # Check privacy settings
        is_own_profile = (user_id == request.user.id)

        if profile.profile_visibility == 'private' and not is_own_profile:
            return ForbiddenResponse(
                message='This profile is private'
            )

        if profile.profile_visibility == 'followers' and not is_own_profile:
            from .models import UserFollow
            is_following = UserFollow.objects.filter(
                follower_id=request.user.id,
                following_id=user_id
            ).exists()
            if not is_following:
                return ForbiddenResponse(
                    message='This profile is only visible to followers'
                )

        # For public profiles or own profile, show full data
        if is_own_profile:
            serializer = UserProfileSerializer(profile)
        else:
            serializer = PublicUserProfileSerializer(profile)

        return SuccessResponse(
            data=serializer.data,
            message='Profile retrieved successfully'
        )


class UpdateAvatarView(APIView):
    """
    Upload or update profile avatar.
    Accepts avatar URL (actual file upload would require additional setup).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Profile"],
        summary="Update avatar",
        description="Update the authenticated user's profile avatar URL",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'avatar_url': {'type': 'string', 'description': 'URL of the avatar image'}
                },
                'required': ['avatar_url']
            }
        },
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': UserProfileSerializer
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def post(self, request):
        """Update avatar URL"""
        from .models import UserProfile

        avatar_url = request.data.get('avatar_url')
        if not avatar_url:
            return ValidationErrorResponse(
                errors={'avatar_url': 'This field is required'},
                message='avatar_url required'
            )

        profile, created = UserProfile.objects.get_or_create(
            user_id=request.user.id
        )

        profile.avatar_url = avatar_url
        profile.save()

        serializer = UserProfileSerializer(profile)
        return SuccessResponse(
            data=serializer.data,
            message='Avatar updated successfully',
            status_code=201
        )


class FollowUserView(APIView):
    """
    Follow or unfollow a user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Social"],
        summary="Follow a user",
        description="Follow a user. Returns success if already following.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to follow',
                required=True
            )
        ],
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': UserFollowSerializer
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
            }
        }
    )
    def post(self, request, user_id):
        """Follow a user"""
        from .models import UserFollow

        # Can't follow yourself
        if user_id == request.user.id:
            return ValidationErrorResponse(
                message='You cannot follow yourself'
            )

        # Check if user exists
        try:
            User.objects.get(id=user_id)
        except User.DoesNotExist:
            return NotFoundResponse(message='User not found')

        # Check if already following
        existing = UserFollow.objects.filter(
            follower_id=request.user.id,
            following_id=user_id
        ).first()

        if existing:
            return SuccessResponse(
                data={'already_following': True},
                message='You are already following this user'
            )

        # Create follow relationship
        follow = UserFollow.objects.create(
            follower_id=request.user.id,
            following_id=user_id
        )

        serializer = UserFollowSerializer(follow)
        return SuccessResponse(
            data=serializer.data,
            message='User followed successfully',
            status_code=201
        )

    @extend_schema(
        tags=["Social"],
        summary="Unfollow a user",
        description="Unfollow a user you are currently following",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to unfollow',
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
                            'unfollowed': {'type': 'boolean'}
                        }
                    }
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
            }
        }
    )
    def delete(self, request, user_id):
        """Unfollow a user"""
        from .models import UserFollow

        # Can't unfollow yourself
        if user_id == request.user.id:
            return ValidationErrorResponse(
                message='You cannot unfollow yourself'
            )

        # Check if following
        try:
            follow = UserFollow.objects.get(
                follower_id=request.user.id,
                following_id=user_id
            )
            follow.delete()
            return SuccessResponse(
                data={'unfollowed': True},
                message='User unfollowed successfully'
            )
        except UserFollow.DoesNotExist:
            return NotFoundResponse(message='Not following this user')


class FollowersView(APIView):
    """
    Get followers (people who follow a user).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Social"],
        summary="Get followers",
        description="Get list of users who follow the specified user (or authenticated user if not specified)",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to get followers for (optional, defaults to authenticated user)',
                required=False
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
                            'user_id': {'type': 'integer'},
                            'followers': {
                                'type': 'array',
                                'items': UserFollowSerializer
                            },
                            'count': {'type': 'integer'}
                        }
                    }
                }
            }
        }
    )
    def get(self, request, user_id=None):
        """Get followers for a user (defaults to authenticated user)"""
        from .models import UserFollow

        target_user_id = user_id if user_id else request.user.id

        followers = UserFollow.objects.filter(
            following_id=target_user_id
        ).order_by('-created_at')

        serializer = UserFollowSerializer(followers, many=True)
        return SuccessResponse(
            data={
                'user_id': target_user_id,
                'followers': serializer.data,
                'count': followers.count()
            },
            message=f'Retrieved {followers.count()} followers'
        )


class FollowingView(APIView):
    """
    Get following (people a user follows).
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Social"],
        summary="Get following",
        description="Get list of users that the specified user follows (or authenticated user if not specified)",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to get following for (optional, defaults to authenticated user)',
                required=False
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
                            'user_id': {'type': 'integer'},
                            'following': {
                                'type': 'array',
                                'items': UserFollowSerializer
                            },
                            'count': {'type': 'integer'}
                        }
                    }
                }
            }
        }
    )
    def get(self, request, user_id=None):
        """Get following for a user (defaults to authenticated user)"""
        from .models import UserFollow

        target_user_id = user_id if user_id else request.user.id

        following = UserFollow.objects.filter(
            follower_id=target_user_id
        ).order_by('-created_at')

        serializer = UserFollowSerializer(following, many=True)
        return SuccessResponse(
            data={
                'user_id': target_user_id,
                'following': serializer.data,
                'count': following.count()
            },
            message=f'Retrieved {following.count()} following'
        )


class ChangePasswordView(APIView):
    """
    Change password for authenticated user.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentication"],
        summary="Change password",
        description="Change the authenticated user's password. Requires current password for verification.",
        request=ChangePasswordSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'success': {'type': 'boolean'}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            },
            401: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def post(self, request):
        from django.contrib.auth import authenticate

        serializer = ChangePasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return ValidationErrorResponse(
                errors=serializer.errors,
                message='Invalid password data'
            )

        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        # Verify current password
        user = authenticate(
            username=request.user.username,
            password=current_password
        )

        if not user:
            return UnauthorizedResponse(
                message='Current password is incorrect'
            )

        # Check if new password is same as current
        if current_password == new_password:
            return ValidationErrorResponse(
                message='New password must be different from current password'
            )

        # Change password
        request.user.set_password(new_password)
        request.user.save()

        return SuccessResponse(
            data={'success': True},
            message='Password changed successfully'
        )
