from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile, UserFollow


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"], password=validated_data["password"]
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username"]


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""

    class Meta:
        model = UserProfile
        fields = [
            'user_id',
            'display_name',
            'bio',
            'avatar_url',
            'profile_visibility',
            'show_activity',
            'allow_messages',
            'preferences',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['user_id', 'created_at', 'updated_at']


class PublicUserProfileSerializer(serializers.ModelSerializer):
    """Serializer for public profile viewing (respecting privacy)"""

    username = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = [
            'user_id',
            'username',
            'display_name',
            'bio',
            'avatar_url',
            'profile_visibility',
            'show_activity',
        ]

    def get_username(self, obj):
        """Get username from Django User model"""
        try:
            user = User.objects.get(id=obj.user_id)
            return user.username
        except User.DoesNotExist:
            return None


class UserFollowSerializer(serializers.ModelSerializer):
    """Serializer for UserFollow model"""

    follower_username = serializers.SerializerMethodField()
    following_username = serializers.SerializerMethodField()

    class Meta:
        model = UserFollow
        fields = [
            'id',
            'follower_id',
            'following_id',
            'follower_username',
            'following_username',
            'created_at',
        ]
        read_only_fields = ['created_at']

    def get_follower_username(self, obj):
        """Get username of follower"""
        try:
            user = User.objects.get(id=obj.follower_id)
            return user.username
        except User.DoesNotExist:
            return None

    def get_following_username(self, obj):
        """Get username of followed user"""
        try:
            user = User.objects.get(id=obj.following_id)
            return user.username
        except User.DoesNotExist:
            return None
