from rest_framework import serializers
from .models import Artist, Album, Song, Genre


class GenreSerializer(serializers.ModelSerializer):
    """Serializer for Genre model"""
    class Meta:
        model = Genre
        fields = [
            'id', 'name', 'description', 'image_url',
            'song_count', 'follower_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['song_count', 'follower_count', 'created_at', 'updated_at']


class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = ['id', 'name', 'image_url', 'bio', 'monthly_listeners', 'created_at']


class AlbumSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer(read_only=True)

    class Meta:
        model = Album
        fields = ['id', 'name', 'cover_url', 'release_year', 'artist']


class SongSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer(read_only=True)
    album = AlbumSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Song
        fields = [
            'id', 'title', 'artist', 'album', 'genre',
            'release_year', 'release_date', 'is_explicit', 'popularity_score',
            'duration_seconds',
            'cover_url', 'audio_url', 'storage_path',
        ]
        read_only_fields = ['created_at']


class SongMinimalSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views"""
    class Meta:
        model = Song
        fields = [
            'id', 'title', 'genre', 'artist', 'album',
            'duration_seconds', 'cover_url', 'popularity_score'
        ]

    artist = serializers.SerializerMethodField()
    album = serializers.SerializerMethodField()

    def get_artist(self, obj):
        return {'id': obj.artist.id, 'name': obj.artist.name}

    def get_album(self, obj):
        if obj.album:
            return {'id': obj.album.id, 'name': obj.album.name}
        return None
