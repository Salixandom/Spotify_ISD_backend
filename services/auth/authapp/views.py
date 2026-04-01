from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
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

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return SuccessResponse(
                data=serializer.data,
                message='User registered successfully',
                status_code=201
            )
        return ValidationErrorResponse(
            errors=serializer.errors,
            message='Registration failed'
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return SuccessResponse(
            data=serializer.data,
            message='User profile retrieved successfully'
        )


@api_view(["GET"])
@permission_classes([AllowAny])
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
