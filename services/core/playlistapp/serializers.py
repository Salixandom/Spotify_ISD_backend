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
