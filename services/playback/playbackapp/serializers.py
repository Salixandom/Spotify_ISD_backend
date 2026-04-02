from rest_framework import serializers
from .models import AudioFile


class AudioFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = AudioFile
        fields = ["id", "title", "artist", "file", "duration_seconds", "uploaded_by_id", "created_at"]
        read_only_fields = ["uploaded_by_id", "created_at"]


class AudioFileUploadSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    artist = serializers.CharField(max_length=255, required=False, default="")
    file = serializers.FileField()
    duration_seconds = serializers.IntegerField(required=False, default=0)
