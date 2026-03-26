from rest_framework import serializers
from .models import Track


class TrackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Track
        fields = "__all__"
        read_only_fields = ["added_by_id", "added_at"]
