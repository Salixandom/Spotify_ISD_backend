from rest_framework import serializers
from .models import Artist, Album, Song


class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Artist
        fields = ['id', 'name', 'image_url', 'bio', 'monthly_listeners', 'created_at']


class AlbumSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer(read_only=True)

    class Meta:
        model  = Album
        fields = ['id', 'name', 'cover_url', 'release_year', 'artist']


class SongSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer(read_only=True)
    album  = AlbumSerializer(read_only=True, allow_null=True)

    class Meta:
        model  = Song
        fields = [
            'id', 'title', 'artist', 'album', 'genre',
            'release_year', 'duration_seconds',
            'cover_url', 'audio_url', 'storage_path',
        ]
