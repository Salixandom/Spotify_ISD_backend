from rest_framework import serializers
from .models import Playlist, PlaylistSnapshot, PlaylistComment, PlaylistCommentLike


class PlaylistSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for playlist snapshots/versioning"""

    class Meta:
        model = PlaylistSnapshot
        fields = [
            'id', 'playlist', 'snapshot_data', 'created_by',
            'created_at', 'change_reason', 'track_count'
        ]
        read_only_fields = ['id', 'created_at', 'created_by']


class PlaylistSerializer(serializers.ModelSerializer):
    """Serializer for playlists with optional snapshot inclusion"""
    snapshots = PlaylistSnapshotSerializer(many=True, read_only=True)

    class Meta:
        model = Playlist
        fields = [
            'id', 'owner_id', 'name', 'description',
            'visibility', 'playlist_type', 'cover_url',
            'max_songs', 'created_at', 'updated_at',
            'snapshots',  # Include related snapshots
        ]
        read_only_fields = ['owner_id', 'created_at', 'updated_at']

    def validate(self, data):
        playlist_type = data.get('playlist_type', getattr(self.instance, 'playlist_type', 'solo'))
        visibility = data.get('visibility', getattr(self.instance, 'visibility', 'public'))
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


class PlaylistCommentSerializer(serializers.ModelSerializer):
    """Serializer for playlist comments with threading support"""
    username = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()

    class Meta:
        model = PlaylistComment
        fields = [
            'id',
            'playlist_id',
            'user_id',
            'username',
            'parent_id',
            'content',
            'likes_count',
            'is_edited',
            'is_deleted',
            'is_liked',
            'replies_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['user_id', 'likes_count', 'is_edited', 'created_at', 'updated_at']

    def get_username(self, obj):
        """Get username from Django User model"""
        try:
            from django.contrib.auth.models import User
            user = User.objects.get(id=obj.user_id)
            return user.username
        except User.DoesNotExist:
            return None

    def get_is_liked(self, obj):
        """Check if current user liked this comment"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return PlaylistCommentLike.objects.filter(
                comment_id=obj.id,
                user_id=request.user.id
            ).exists()
        return False

    def get_replies_count(self, obj):
        """Count direct replies to this comment"""
        return PlaylistComment.objects.filter(parent_id=obj.id, is_deleted=False).count()


class PlaylistCommentLikeSerializer(serializers.ModelSerializer):
    """Serializer for comment likes"""

    class Meta:
        model = PlaylistCommentLike
        fields = ['id', 'comment_id', 'user_id', 'created_at']
        read_only_fields = ['id', 'created_at']
