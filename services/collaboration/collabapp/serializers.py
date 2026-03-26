from rest_framework import serializers
from .models import Collaborator, InviteLink


class CollaboratorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Collaborator
        fields = "__all__"


class InviteLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = InviteLink
        fields = "__all__"
        read_only_fields = ["token", "created_by_id", "created_at"]
