from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes, OpenApiExample
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
        description="Refresh an expired access token using a valid refresh token. Use this endpoint instead of logging in again when your access token expires (5 minute lifetime). Refresh tokens are valid for 24 hours.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'refresh': {
                        'type': 'string',
                        'description': 'Valid JWT refresh token received from login or previous refresh',
                        'example': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiZnJlc2giLCJleHAiOjE3NDQwOTYwMDB9.example'
                    }
                },
                'required': ['refresh']
            }
        },
        examples=[
            OpenApiExample(
                'Token refresh',
                description='Refresh an expired access token',
                value={
                    'refresh': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiZnJlc2giLCJleHAiOjE3NDQwOTYwMDB9.example'
                }
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
                        'example': 'Token refreshed successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'access': {
                                'type': 'string',
                                'description': 'New JWT access token (valid for 5 minutes from now)',
                                'example': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQ0MDEyMDAwfQ.example'
                            },
                            'refresh': {
                                'type': 'string',
                                'description': 'New JWT refresh token (optional - may be rotated for security)',
                                'example': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiZnJlc2giLCJleHAiOjE3NDQxMDAwMDB9.example'
                            }
                        }
                    }
                }
            },
            401: {
                'type': 'object',
                'examples': {
                    'invalid_token': {
                        'summary': 'Invalid or expired refresh token',
                        'description': 'The refresh token is invalid, expired, or malformed',
                        'value': {
                            'success': False,
                            'message': 'Invalid refresh token',
                            'errors': {
                                'detail': 'Token is invalid or expired',
                                'code': 'token_not_valid'
                            }
                        }
                    },
                    'missing_token': {
                        'summary': 'Refresh token not provided',
                        'value': {
                            'success': False,
                            'message': 'Invalid refresh token',
                            'errors': {
                                'refresh': ['This field is required.']
                            }
                        }
                    },
                    'blacklisted_token': {
                        'summary': 'Token has been blacklisted',
                        'description': 'Token was revoked (e.g., after password change or logout)',
                        'value': {
                            'success': False,
                            'message': 'Invalid refresh token',
                            'errors': {
                                'detail': 'Token is blacklisted',
                                'code': 'token_not_valid'
                            }
                        }
                    }
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
        description="Authenticate with username/password and receive JWT access and refresh tokens. The access token expires in 5 minutes. Use the refresh token to get a new access token without logging in again.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {
                        'type': 'string',
                        'description': 'Your registered username',
                        'example': 'john_doe123'
                    },
                    'password': {
                        'type': 'string',
                        'format': 'password',
                        'description': 'Your account password',
                        'example': 'SecurePass123!'
                    }
                },
                'required': ['username', 'password']
            }
        },
        examples=[
            OpenApiExample(
                'Successful login',
                description='Login with valid credentials',
                value={
                    'username': 'john_doe123',
                    'password': 'SecurePass123!'
                }
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
                        'example': 'Login successful'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'access': {
                                'type': 'string',
                                'description': 'JWT access token (valid for 5 minutes). Include in Authorization header as "Bearer <token>"',
                                'example': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzQ0MDA4MDAwfQ.example'
                            },
                            'refresh': {
                                'type': 'string',
                                'description': 'JWT refresh token (valid for 24 hours). Use to get new access token via /api/auth/token/refresh/',
                                'example': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiZnJlc2giLCJleHAiOjE3NDQwOTYwMDB9.example'
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'invalid_credentials': {
                        'summary': 'Invalid username or password',
                        'description': 'Either the username does not exist or the password is incorrect',
                        'value': {
                            'success': False,
                            'message': 'Invalid credentials',
                            'errors': {
                                'detail': 'No active account found with the given credentials'
                            }
                        }
                    },
                    'missing_fields': {
                        'summary': 'Missing required fields',
                        'value': {
                            'success': False,
                            'message': 'Invalid credentials',
                            'errors': {
                                'username': ['This field is required.'],
                                'password': ['This field is required.']
                            }
                        }
                    },
                    'inactive_account': {
                        'summary': 'Account is disabled/inactive',
                        'value': {
                            'success': False,
                            'message': 'Invalid credentials',
                            'errors': {
                                'detail': 'No active account found with the given credentials'
                            }
                        }
                    }
                }
            },
            401: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Authentication failed',
                    'errors': {
                        'detail': 'Authentication credentials were not provided.'
                    }
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
        description="Create a new user account. Username must be unique. Email must be valid and unique. Password must be at least 8 characters. A profile is automatically created upon registration.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'username': {
                        'type': 'string',
                        'description': 'Unique username for the account (3-150 characters, alphanumeric plus @.+_-)',
                        'minLength': 3,
                        'maxLength': 150,
                        'example': 'john_doe123'
                    },
                    'email': {
                        'type': 'string',
                        'format': 'email',
                        'description': 'Valid email address (must be unique)',
                        'example': 'john.doe@example.com'
                    },
                    'password': {
                        'type': 'string',
                        'format': 'password',
                        'description': 'Password (minimum 8 characters)',
                        'minLength': 8,
                        'example': 'SecurePass123!'
                    },
                    'first_name': {
                        'type': 'string',
                        'description': 'First name (optional)',
                        'maxLength': 150,
                        'example': 'John'
                    },
                    'last_name': {
                        'type': 'string',
                        'description': 'Last name (optional)',
                        'maxLength': 150,
                        'example': 'Doe'
                    }
                },
                'required': ['username', 'email', 'password']
            }
        },
        examples=[
            OpenApiExample(
                'Complete registration',
                description='Register with all optional fields',
                value={
                    'username': 'john_doe123',
                    'email': 'john.doe@example.com',
                    'password': 'SecurePass123!',
                    'first_name': 'John',
                    'last_name': 'Doe'
                }
            ),
            OpenApiExample(
                'Minimal registration',
                description='Register with only required fields',
                value={
                    'username': 'jane_smith',
                    'email': 'jane@example.com',
                    'password': 'MyPassword123'
                }
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
                        'example': 'User registered successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer', 'example': 1},
                            'username': {'type': 'string', 'example': 'john_doe123'},
                            'email': {'type': 'string', 'example': 'john.doe@example.com'},
                            'first_name': {'type': 'string', 'example': 'John'},
                            'last_name': {'type': 'string', 'example': 'Doe'}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'validation_error': {
                        'summary': 'Validation failed',
                        'value': {
                            'success': False,
                            'message': 'Registration failed',
                            'errors': {
                                'password': ['This password is too short. It must contain at least 8 characters.'],
                                'email': ['Enter a valid email address.']
                            }
                        }
                    },
                    'duplicate_username': {
                        'summary': 'Username already exists',
                        'value': {
                            'success': False,
                            'message': 'Registration failed',
                            'errors': {
                                'username': ['A user with that username already exists.']
                            }
                        }
                    },
                    'duplicate_email': {
                        'summary': 'Email already exists',
                        'value': {
                            'success': False,
                            'message': 'Registration failed',
                            'errors': {
                                'email': ['A user with that email already exists.']
                            }
                        }
                    }
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
        description="Retrieve basic information about the authenticated user including username, email, and name. This endpoint verifies your JWT token is valid and returns your user details.",
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
                        'example': 'User profile retrieved successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {
                                'type': 'integer',
                                'description': 'Your user ID',
                                'example': 1
                            },
                            'username': {
                                'type': 'string',
                                'description': 'Your username',
                                'example': 'john_doe123'
                            },
                            'email': {
                                'type': 'string',
                                'format': 'email',
                                'description': 'Your email address',
                                'example': 'john.doe@example.com'
                            },
                            'first_name': {
                                'type': 'string',
                                'description': 'Your first name',
                                'example': 'John'
                            },
                            'last_name': {
                                'type': 'string',
                                'description': 'Your last name',
                                'example': 'Doe'
                            }
                        }
                    }
                }
            },
            401: {
                'type': 'object',
                'description': 'Token is invalid or expired',
                'example': {
                    'success': False,
                    'message': 'Authentication credentials were not provided'
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
        description="Retrieve the authenticated user's full profile including bio, location, website, and privacy settings. Profile is auto-created if it doesn't exist.",
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
                        'example': 'Profile retrieved successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {'type': 'integer', 'example': 1},
                            'bio': {
                                'type': 'string',
                                'example': 'Music lover and playlist curator',
                                'description': 'User biography (max 500 characters)'
                            },
                            'location': {
                                'type': 'string',
                                'example': 'New York, NY',
                                'description': 'User location (max 100 characters)'
                            },
                            'website': {
                                'type': 'string',
                                'example': 'https://example.com',
                                'description': 'Personal website URL'
                            },
                            'avatar_url': {
                                'type': 'string',
                                'example': 'https://example.com/avatar.jpg',
                                'description': 'Profile avatar image URL'
                            },
                            'profile_visibility': {
                                'type': 'string',
                                'enum': ['public', 'followers', 'private'],
                                'example': 'public',
                                'description': 'Who can view your profile: public (everyone), followers (followers only), private (only you)'
                            },
                            'show_activity': {
                                'type': 'boolean',
                                'example': True,
                                'description': 'Whether to show your recent activity to others'
                            }
                        }
                    }
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
        description="Update the authenticated user's profile. All fields are optional - only include the fields you want to change. Partial updates are supported.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'bio': {
                        'type': 'string',
                        'description': 'User biography (max 500 characters)',
                        'maxLength': 500,
                        'example': 'Music lover and playlist curator'
                    },
                    'location': {
                        'type': 'string',
                        'description': 'User location (max 100 characters)',
                        'maxLength': 100,
                        'example': 'New York, NY'
                    },
                    'website': {
                        'type': 'string',
                        'description': 'Personal website URL (must be valid URL)',
                        'example': 'https://example.com'
                    },
                    'avatar_url': {
                        'type': 'string',
                        'description': 'Profile avatar image URL',
                        'example': 'https://example.com/avatar.jpg'
                    },
                    'profile_visibility': {
                        'type': 'string',
                        'enum': ['public', 'followers', 'private'],
                        'description': 'Who can view your profile',
                        'example': 'public'
                    },
                    'show_activity': {
                        'type': 'boolean',
                        'description': 'Whether to show your recent activity to others',
                        'example': True
                    }
                }
            }
        },
        examples=[
            OpenApiExample(
                'Update bio and location',
                description='Update only bio and location fields',
                value={
                    'bio': 'Music lover and playlist curator',
                    'location': 'New York, NY'
                }
            ),
            OpenApiExample(
                'Update privacy settings',
                description='Change profile visibility and activity settings',
                value={
                    'profile_visibility': 'followers',
                    'show_activity': False
                }
            ),
            OpenApiExample(
                'Add website and avatar',
                description='Update website and avatar URL',
                value={
                    'website': 'https://example.com',
                    'avatar_url': 'https://example.com/avatar.jpg'
                }
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
                        'example': 'Profile updated successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {'type': 'integer', 'example': 1},
                            'bio': {'type': 'string', 'example': 'Music lover and playlist curator'},
                            'location': {'type': 'string', 'example': 'New York, NY'},
                            'website': {'type': 'string', 'example': 'https://example.com'},
                            'avatar_url': {'type': 'string', 'example': 'https://example.com/avatar.jpg'},
                            'profile_visibility': {
                                'type': 'string',
                                'example': 'public',
                                'enum': ['public', 'followers', 'private']
                            },
                            'show_activity': {'type': 'boolean', 'example': True}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'invalid_url': {
                        'summary': 'Invalid website URL',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'website': ['Enter a valid URL.']
                            }
                        }
                    },
                    'invalid_visibility': {
                        'summary': 'Invalid profile visibility value',
                        'value': {
                            'success': False,
                            'message': 'Validation failed',
                            'errors': {
                                'profile_visibility': ['"invalid" is not a valid choice.']
                            }
                        }
                    }
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
        description="Get a user's profile. Respects privacy settings: public profiles show all data to everyone, followers-only profiles show only to followers, private profiles show only to the owner. Your own profile always shows full data regardless of privacy setting.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to fetch profile for',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'public_profile': {
                        'summary': 'Public profile (visible to everyone)',
                        'value': {
                            'success': True,
                            'message': 'Profile retrieved successfully',
                            'data': {
                                'user_id': 123,
                                'bio': 'Music enthusiast and playlist creator',
                                'location': 'Los Angeles, CA',
                                'website': 'https://example.com',
                                'avatar_url': 'https://example.com/avatar.jpg',
                                'profile_visibility': 'public',
                                'show_activity': True
                            }
                        }
                    },
                    'own_profile': {
                        'summary': 'Your own profile (always full data)',
                        'value': {
                            'success': True,
                            'message': 'Profile retrieved successfully',
                            'data': {
                                'user_id': 1,
                                'bio': 'My music journey',
                                'location': 'New York, NY',
                                'website': 'https://mymusic.com',
                                'avatar_url': 'https://example.com/me.jpg',
                                'profile_visibility': 'private',
                                'show_activity': False
                            }
                        }
                    }
                }
            },
            403: {
                'type': 'object',
                'examples': {
                    'private_profile': {
                        'summary': 'Private profile (not visible to non-followers)',
                        'value': {
                            'success': False,
                            'message': 'This profile is private'
                        }
                    },
                    'followers_only': {
                        'summary': 'Followers-only profile (not visible to non-followers)',
                        'value': {
                            'success': False,
                            'message': 'This profile is only visible to followers'
                        }
                    }
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
        description="Update the authenticated user's profile avatar by providing a URL to an image. The URL should be publicly accessible. Common image formats: JPG, PNG, GIF, WebP. Recommended size: 400x400px.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'avatar_url': {
                        'type': 'string',
                        'format': 'uri',
                        'description': 'Public URL of the avatar image',
                        'example': 'https://example.com/avatars/user123.jpg'
                    }
                },
                'required': ['avatar_url']
            }
        },
        examples=[
            OpenApiExample(
                'Update avatar URL',
                description='Update profile avatar with a new image URL',
                value={'avatar_url': 'https://example.com/avatars/my-new-avatar.jpg'}
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
                        'example': 'Avatar updated successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {'type': 'integer', 'example': 1},
                            'avatar_url': {
                                'type': 'string',
                                'example': 'https://example.com/avatars/my-new-avatar.jpg'
                            },
                            'bio': {'type': 'string', 'example': 'Music lover'},
                            'location': {'type': 'string', 'example': 'NYC'},
                            'profile_visibility': {
                                'type': 'string',
                                'example': 'public',
                                'enum': ['public', 'followers', 'private']
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'missing_url': {
                        'summary': 'Avatar URL not provided',
                        'value': {
                            'success': False,
                            'message': 'avatar_url required',
                            'errors': {
                                'avatar_url': ['This field is required']
                            }
                        }
                    },
                    'invalid_url': {
                        'summary': 'Invalid URL format',
                        'value': {
                            'success': False,
                            'message': 'avatar_url required',
                            'errors': {
                                'avatar_url': ['Enter a valid URL.']
                            }
                        }
                    }
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
        description="Follow a user to see their public activity and updates in your feed. You will see their public playlists and activity. Following is idempotent - following an already-followed user returns success.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to follow',
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
                        'example': 'User followed successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'integer', 'example': 456},
                            'follower_id': {
                                'type': 'integer',
                                'description': 'Your user ID',
                                'example': 1
                            },
                            'following_id': {
                                'type': 'integer',
                                'description': 'User ID you are now following',
                                'example': 123
                            },
                            'created_at': {
                                'type': 'string',
                                'format': 'date-time',
                                'example': '2026-04-07T16:30:00Z'
                            }
                        }
                    }
                }
            },
            200: {
                'type': 'object',
                'description': 'Already following (idempotent)',
                'properties': {
                    'success': {
                        'type': 'boolean',
                        'example': True
                    },
                    'message': {
                        'type': 'string',
                        'example': 'You are already following this user'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'already_following': {
                                'type': 'boolean',
                                'example': True
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'follow_self': {
                        'summary': 'Cannot follow yourself',
                        'value': {
                            'success': False,
                            'message': 'You cannot follow yourself'
                        }
                    }
                }
            },
            404: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'User not found'
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
        description="Stop following a user. Their updates will no longer appear in your feed. Idempotent - unfollowing a user you don't follow returns success.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to unfollow',
                required=True,
                example=123
            )
        ],
        responses={
            200: {
                'type': 'object',
                'examples': {
                    'success': {
                        'summary': 'Successfully unfollowed',
                        'value': {
                            'success': True,
                            'message': 'User unfollowed successfully',
                            'data': {
                                'unfollowed': True
                            }
                        }
                    },
                    'not_following': {
                        'summary': 'Not following this user (idempotent)',
                        'value': {
                            'success': False,
                            'message': 'Not following this user'
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'unfollow_self': {
                        'summary': 'Cannot unfollow yourself',
                        'value': {
                            'success': False,
                            'message': 'You cannot unfollow yourself'
                        }
                    }
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
        description="Get list of users who follow the specified user. If no user_id is provided, returns followers of the authenticated user. Results are ordered by most recent followers first.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to get followers for (optional, defaults to authenticated user)',
                required=False,
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
                        'example': 'Retrieved 42 followers'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {
                                'type': 'integer',
                                'description': 'User ID whose followers were retrieved',
                                'example': 123
                            },
                            'followers': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 1},
                                        'follower_id': {
                                            'type': 'integer',
                                            'description': 'User ID who is following',
                                            'example': 456
                                        },
                                        'following_id': {
                                            'type': 'integer',
                                            'description': 'User ID being followed',
                                            'example': 123
                                        },
                                        'created_at': {
                                            'type': 'string',
                                            'format': 'date-time',
                                            'description': 'When the follow relationship was created',
                                            'example': '2026-04-07T16:30:00Z'
                                        }
                                    }
                                },
                                'description': 'List of followers, most recent first'
                            },
                            'count': {
                                'type': 'integer',
                                'description': 'Total number of followers',
                                'example': 42
                            }
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
        description="Get list of users that the specified user follows. If no user_id provided, returns who the authenticated user follows. Results ordered by most recent follows first.",
        parameters=[
            OpenApiParameter(
                name='user_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='User ID to get following for (optional, defaults to authenticated user)',
                required=False,
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
                        'example': 'Retrieved 28 following'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'user_id': {
                                'type': 'integer',
                                'description': 'User ID whose following list was retrieved',
                                'example': 123
                            },
                            'following': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer', 'example': 1},
                                        'follower_id': {
                                            'type': 'integer',
                                            'description': 'User ID who is following',
                                            'example': 123
                                        },
                                        'following_id': {
                                            'type': 'integer',
                                            'description': 'User ID being followed',
                                            'example': 789
                                        },
                                        'created_at': {
                                            'type': 'string',
                                            'format': 'date-time',
                                            'example': '2026-04-07T16:30:00Z'
                                        }
                                    }
                                },
                                'description': 'List of users being followed, most recent first'
                            },
                            'count': {
                                'type': 'integer',
                                'description': 'Total number of following',
                                'example': 28
                            }
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
        description="Change the authenticated user's password. Requires current password for security. New password must be different from current password. Minimum 8 characters recommended.",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'current_password': {
                        'type': 'string',
                        'format': 'password',
                        'description': 'Current password for verification',
                        'example': 'OldPass123!'
                    },
                    'new_password': {
                        'type': 'string',
                        'format': 'password',
                        'description': 'New password (minimum 8 characters)',
                        'minLength': 8,
                        'example': 'NewSecurePass456!'
                    }
                },
                'required': ['current_password', 'new_password']
            }
        },
        examples=[
            OpenApiExample(
                'Change password',
                description='Change password with current password verification',
                value={
                    'current_password': 'OldPass123!',
                    'new_password': 'NewSecurePass456!'
                }
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
                        'example': 'Password changed successfully'
                    },
                    'data': {
                        'type': 'object',
                        'properties': {
                            'success': {
                                'type': 'boolean',
                                'example': True
                            }
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'examples': {
                    'validation_error': {
                        'summary': 'Validation failed',
                        'value': {
                            'success': False,
                            'message': 'Invalid password data',
                            'errors': {
                                'new_password': ['This password is too short. It must contain at least 8 characters.']
                            }
                        }
                    },
                    'same_password': {
                        'summary': 'New password same as current',
                        'value': {
                            'success': False,
                            'message': 'New password must be different from current password'
                        }
                    }
                }
            },
            401: {
                'type': 'object',
                'example': {
                    'success': False,
                    'message': 'Current password is incorrect'
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
