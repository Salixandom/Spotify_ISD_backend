from rest_framework import serializers
from .models import Collaborator, InviteLink


class CollaboratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collaborator
        fields = ['id', 'playlist_id', 'user_id', 'joined_at']


class InviteLinkSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model = InviteLink
        fields = ['id', 'playlist_id', 'token', 'created_by_id', 'is_active', 'created_at', 'expires_at', 'is_valid']
        read_only_fields = ['token', 'created_by_id', 'created_at', 'is_valid']

    def get_is_valid(self, obj):
        return obj.is_valid
