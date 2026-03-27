from rest_framework import serializers
from searchapp.serializers import SongSerializer
from .models import Track


class TrackSerializer(serializers.ModelSerializer):
    song        = SongSerializer(read_only=True)
    playlist_id = serializers.IntegerField(source='playlist.id', read_only=True)

    class Meta:
        model        = Track
        fields       = ['id', 'playlist_id', 'song', 'added_by_id', 'position', 'added_at']
        read_only_fields = ['added_by_id', 'added_at', 'playlist_id']
