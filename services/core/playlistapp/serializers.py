from rest_framework import serializers
from .models import Playlist


class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Playlist
        fields = [
            'id', 'owner_id', 'name', 'description',
            'visibility', 'playlist_type', 'cover_url',
            'max_songs', 'created_at', 'updated_at',
        ]
        read_only_fields = ['owner_id', 'created_at', 'updated_at']

    def validate(self, data):
        playlist_type = data.get('playlist_type', getattr(self.instance, 'playlist_type', 'solo'))
        visibility    = data.get('visibility',    getattr(self.instance, 'visibility', 'public'))
        if playlist_type == 'collaborative' and visibility != 'private':
            raise serializers.ValidationError(
                {'visibility': 'Collaborative playlists must be private.'}
            )
        return data


class PlaylistStatsSerializer(serializers.Serializer):
    """Serializer for playlist statistics endpoint"""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    total_tracks = serializers.IntegerField(read_only=True)
    total_duration_seconds = serializers.IntegerField(read_only=True)
    total_duration_formatted = serializers.CharField(read_only=True)
    genres = serializers.ListField(child=serializers.CharField(), read_only=True)
    unique_artists = serializers.IntegerField(read_only=True)
    unique_albums = serializers.IntegerField(read_only=True)
    last_track_added = serializers.DateTimeField(read_only=True)
    collaborator_count = serializers.IntegerField(read_only=True)
    follower_count = serializers.IntegerField(read_only=True)
    like_count = serializers.IntegerField(read_only=True)
    is_followed = serializers.BooleanField(read_only=True)
    is_liked = serializers.BooleanField(read_only=True)
    owner_id = serializers.IntegerField(read_only=True)
    cover_url = serializers.URLField(read_only=True)
