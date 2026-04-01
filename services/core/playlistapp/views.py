from rest_framework import viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from django.db import connection
from utils.responses import (
    SuccessResponse,
    ErrorResponse,
    ValidationErrorResponse,
    NotFoundResponse,
    ForbiddenResponse,
    ServiceUnavailableResponse,
)
from django.db.models import Q, Count, Sum
from django.utils import timezone
from .models import Playlist, UserPlaylistFollow, UserPlaylistLike, PlaylistSnapshot, PlaylistComment, PlaylistCommentLike
from .serializers import PlaylistSerializer, PlaylistSnapshotSerializer, PlaylistCommentSerializer, PlaylistCommentLikeSerializer
from trackapp.models import Track

PLAYLIST_SORT_MAP = {
    'name':        'name',
    'created_at':  'created_at',
    'updated_at':  'updated_at',
    'track_count': 'track_count',
}


class PlaylistViewSet(viewsets.ModelViewSet):
    serializer_class = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Enhanced filtering for playlist list:
        - visibility: public|private
        - type: solo|collaborative
        - is_system_generated: true|false (filter by system-generated vs user-created)
        - q: search in name/description
        - min_tracks, max_tracks: track count range
        - created_after, created_before: date range
        - sort: name|created_at|updated_at|track_count
        - order: asc|desc
        - include_archived: true (default: excluded)
        - include_followed: true (default: excluded)
        - filter: followed|liked (special filters)
        """
        qs = Playlist.objects.filter(owner_id=self.request.user.id)

        # Enhanced filtering
        visibility = self.request.query_params.get('visibility')
        if visibility in ['public', 'private']:
            qs = qs.filter(visibility=visibility)

        playlist_type = self.request.query_params.get('type')
        if playlist_type in ['solo', 'collaborative']:
            qs = qs.filter(playlist_type=playlist_type)

        # Filter by system-generated vs user-created
        is_system_generated = self.request.query_params.get('is_system_generated')
        if is_system_generated in ['true', 'false']:
            qs = qs.filter(is_system_generated=(is_system_generated == 'true'))

        # Search in name and description
        query = self.request.query_params.get('q')
        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )

        # Date range filters
        created_after = self.request.query_params.get('created_after')
        if created_after:
            try:
                qs = qs.filter(created_at__gte=created_after)
            except ValueError:
                pass  # Invalid date format, ignore filter

        created_before = self.request.query_params.get('created_before')
        if created_before:
            try:
                qs = qs.filter(created_at__lte=created_before)
            except ValueError:
                pass  # Invalid date format, ignore filter

        # Exclude archived by default
        if self.request.query_params.get('include_archived') != 'true':
            qs = qs.exclude(archived_by__user_id=self.request.user.id)

        # Special filters
        filter_type = self.request.query_params.get('filter')
        if filter_type == 'followed':
            # Filter to playlists followed by the user
            followed_playlist_ids = UserPlaylistFollow.objects.filter(
                user_id=self.request.user.id
            ).values_list('playlist_id', flat=True)
            qs = qs.filter(id__in=followed_playlist_ids)
        elif filter_type == 'liked':
            # Filter to playlists liked by the user
            liked_playlist_ids = UserPlaylistLike.objects.filter(
                user_id=self.request.user.id
            ).values_list('playlist_id', flat=True)
            qs = qs.filter(id__in=liked_playlist_ids)

        # Sorting
        sort = self.request.query_params.get('sort', 'updated_at')
        order = self.request.query_params.get('order', 'desc')
        order_field = PLAYLIST_SORT_MAP.get(sort, 'updated_at')

        # Handle track_count sorting with annotation
        if sort == 'track_count':
            qs = qs.annotate(track_count=Count('tracks'))

        if order == 'desc':
            order_field = '-' + order_field

        qs = qs.order_by(order_field)

        # Post-filtering by track count (after annotation)
        min_tracks = self.request.query_params.get('min_tracks')
        if min_tracks:
            try:
                min_tracks_int = int(min_tracks)
                if sort == 'track_count':
                    qs = [p for p in qs if p.track_count >= min_tracks_int]
                else:
                    # Annotate track_count if not already done
                    qs = qs.annotate(track_count=Count('tracks'))
                    qs = qs.filter(track_count__gte=min_tracks_int)
            except ValueError:
                pass  # Invalid integer, ignore filter

        max_tracks = self.request.query_params.get('max_tracks')
        if max_tracks:
            try:
                max_tracks_int = int(max_tracks)
                if sort == 'track_count' and not isinstance(qs, list):
                    qs = [p for p in qs if p.track_count <= max_tracks_int]
                elif not isinstance(qs, list):
                    # Annotate track_count if not already done
                    qs = qs.annotate(track_count=Count('tracks'))
                    qs = qs.filter(track_count__lte=max_tracks_int)
            except ValueError:
                pass  # Invalid integer, ignore filter

        return qs

    def perform_create(self, serializer):
        serializer.save(owner_id=self.request.user.id)

    def list(self, request, *args, **kwargs):
        """Override to wrap response in SuccessResponse format"""
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return SuccessResponse(data=serializer.data, message='Playlists retrieved successfully')

    def retrieve(self, request, *args, **kwargs):
        """Override to wrap response in SuccessResponse format"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return SuccessResponse(data=serializer.data, message='Playlist retrieved successfully')

    def create(self, request, *args, **kwargs):
        """Override to wrap response in SuccessResponse format"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return SuccessResponse(data=serializer.data, message='Playlist created successfully', status=201)

    def update(self, request, *args, **kwargs):
        playlist = self.get_object()
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return SuccessResponse(data=serializer.data, message='Playlist updated successfully')

    def destroy(self, request, *args, **kwargs):
        playlist = self.get_object()
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')
        self.perform_destroy(playlist)
        return SuccessResponse(data=None, message='Playlist deleted successfully')


class PlaylistStatsView(APIView):
    """
    GET /api/playlists/{id}/stats/

    Returns comprehensive statistics for a playlist:
    - Track counts and durations
    - Genre breakdown
    - Artist/album uniqueness
    - Collaborator count
    - Follow/like status
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Check authorization
        if playlist.owner_id != request.user.id and playlist.visibility != 'public':
            return ForbiddenResponse(message='Not authorized to view this playlist')

        # Track statistics
        tracks = Track.objects.filter(playlist=playlist).select_related(
            'song__artist', 'song__album'
        )

        total_tracks = tracks.count()
        total_duration = tracks.aggregate(
            total=Sum('song__duration_seconds')
        )['total'] or 0

        # Genre breakdown
        genres = list(
            tracks.exclude(song__genre='')
            .values_list('song__genre', flat=True)
            .distinct()
        )

        # Unique artists and albums
        unique_artists = tracks.values('song__artist').distinct().count()
        unique_albums = tracks.values('song__album').distinct().count()

        # Last track added
        last_track = tracks.order_by('-added_at').first()
        last_track_added = last_track.added_at if last_track else None

        # Collaborator count from collabapp via service client
        try:
            from utils.service_clients import CollaborationServiceClient
            auth_token = request.headers.get('Authorization', '')
            collaborator_count = CollaborationServiceClient.get_collaborator_count(
                playlist.id,
                auth_token
            )
        except Exception:
            # Fallback if service communication fails
            collaborator_count = 0

        # Follow/like status
        is_followed = UserPlaylistFollow.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).exists()

        is_liked = UserPlaylistLike.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).exists()

        # Follower and like counts
        follower_count = UserPlaylistFollow.objects.filter(playlist=playlist).count()
        like_count = UserPlaylistLike.objects.filter(playlist=playlist).count()

        # Format duration
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        seconds = total_duration % 60
        duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"

        return SuccessResponse(
            data={
                'id': playlist.id,
                'name': playlist.name,
                'total_tracks': total_tracks,
                'total_duration_seconds': total_duration,
                'total_duration_formatted': duration_formatted,
                'genres': genres,
                'unique_artists': unique_artists,
                'unique_albums': unique_albums,
                'last_track_added': last_track_added,
                'collaborator_count': collaborator_count,
                'follower_count': follower_count,
                'like_count': like_count,
                'is_followed': is_followed,
                'is_liked': is_liked,
                'owner_id': playlist.owner_id,
                'cover_url': playlist.cover_url
            },
            message='Playlist statistics retrieved successfully'
        )


class FeaturedPlaylistsView(APIView):
    """
    GET /api/playlists/featured/

    Returns featured/curated playlists:
    - Public playlists only
    - Ordered by track count or creation date
    - Optional genre filter
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # For now, return public playlists ordered by track count
        # In future, can add is_featured flag to Playlist model
        qs = Playlist.objects.filter(visibility='public').annotate(
            track_count=Count('tracks')
        ).order_by('-track_count', '-created_at')

        # Optional genre filter
        genre = self.request.query_params.get('genre')
        if genre:
            # Filter playlists that have songs in this genre
            from trackapp.models import Track
            playlist_ids_with_genre = Track.objects.filter(
                song__genre=genre
            ).values_list('playlist_id', flat=True).distinct()
            qs = qs.filter(id__in=playlist_ids_with_genre)

        # Limit results
        limit = int(self.request.query_params.get('limit', 20))
        qs = qs[:limit]

        return SuccessResponse(
            data=PlaylistSerializer(qs, many=True).data,
            message='Playlists retrieved successfully'
        )


class DuplicatePlaylistView(APIView):
    """
    POST /api/playlists/{id}/duplicate/

    Duplicate a playlist with all its tracks.
    Creates a new playlist with name "{original_name} (Copy)"
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        try:
            source = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization check - can only duplicate own playlists or public playlists
        if source.owner_id != request.user.id and source.visibility != 'public':
            return ForbiddenResponse(message='Not authorized to duplicate this playlist')

        # Get request body for optional parameters
        data = request.data
        name = data.get('name', f"{source.name} (Copy)")
        include_tracks = data.get('include_tracks', True)
        reset_position = data.get('reset_position', False)

        # Create duplicate playlist
        new_playlist = Playlist.objects.create(
            owner_id=request.user.id,
            name=name,
            description=source.description,
            visibility='private',  # Duplicates are always private
            playlist_type='solo',  # Duplicates are always solo
            max_songs=source.max_songs,
            cover_url=source.cover_url
        )

        # Copy tracks if requested
        if include_tracks:
            tracks = Track.objects.filter(playlist=source).select_related('song')
            new_tracks = []
            for index, track in enumerate(tracks):
                new_tracks.append(Track(
                    playlist=new_playlist,
                    song=track.song,
                    added_by_id=request.user.id,
                    position=index if not reset_position else track.position
                ))

            if new_tracks:
                Track.objects.bulk_create(new_tracks)

        return SuccessResponse(
            data=PlaylistSerializer(new_playlist).data,
            message='Playlist duplicated successfully',
            status_code=201
        )


class BatchDeleteView(APIView):
    """
    DELETE /api/playlists/batch-delete/

    Delete multiple playlists at once.
    Body: {"playlist_ids": [1, 2, 3]}
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        playlist_ids = request.data.get('playlist_ids', [])

        if not playlist_ids:
            return ValidationErrorResponse(
                errors={'playlist_ids': 'This field is required'},
                message='playlist_ids is required'
            )

        if not isinstance(playlist_ids, list):
            return ValidationErrorResponse(
                errors={'playlist_ids': 'Must be a list'},
                message='playlist_ids must be a list'
            )

        # Delete only user's own playlists
        deleted, not_found, not_authorized = 0, 0, 0

        for playlist_id in playlist_ids:
            try:
                playlist = Playlist.objects.get(id=playlist_id)
                if playlist.owner_id == request.user.id:
                    playlist.delete()
                    deleted += 1
                else:
                    not_authorized += 1
            except Playlist.DoesNotExist:
                not_found += 1

        status_code = status.HTTP_200_OK if deleted > 0 else status.HTTP_202_ACCEPTED
        return SuccessResponse(
            data={
                'deleted': deleted,
                'not_found': not_found,
                'not_authorized': not_authorized
            },
            message=f'Batch delete completed: {deleted} deleted',
            status_code=status_code
        )


class BatchUpdateView(APIView):
    """
    PATCH /api/playlists/batch-update/

    Update multiple playlists at once.
    Body: {"playlist_ids": [1, 2], "updates": {"visibility": "private"}}
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        playlist_ids = request.data.get('playlist_ids', [])
        updates = request.data.get('updates', {})

        if not playlist_ids:
            return ValidationErrorResponse(
                errors={'playlist_ids': 'This field is required'},
                message='playlist_ids is required'
            )

        if not updates:
            return ValidationErrorResponse(
                errors={'updates': 'This field is required'},
                message='updates field is required'
            )

        if not isinstance(playlist_ids, list):
            return ValidationErrorResponse(
                errors={'playlist_ids': 'Must be a list'},
                message='playlist_ids must be a list'
            )

        # Update only user's own playlists
        updated, not_found, not_authorized = 0, 0, 0

        for playlist_id in playlist_ids:
            try:
                playlist = Playlist.objects.get(id=playlist_id)
                if playlist.owner_id == request.user.id:
                    # Apply updates
                    for field, value in updates.items():
                        if hasattr(playlist, field):
                            setattr(playlist, field, value)
                    playlist.save()
                    updated += 1
                else:
                    not_authorized += 1
            except Playlist.DoesNotExist:
                not_found += 1

        status_code = status.HTTP_200_OK if updated > 0 else status.HTTP_202_ACCEPTED
        return SuccessResponse(
            data={
                'updated': updated,
                'not_found': not_found,
                'not_authorized': not_authorized
            },
            message=f'Batch update completed: {updated} updated',
            status_code=status_code
        )


class CoverUploadView(APIView):
    """
    POST /api/playlists/{id}/cover/

    Upload a cover image for a playlist.
    Currently accepts cover_url as a string (for Supabase URLs or external URLs).
    Future enhancement: Accept multipart file upload.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized to modify this playlist')

        # For now, we accept cover_url in the request body
        # Future enhancement: Handle multipart file upload
        cover_url = request.data.get('cover_url')

        if not cover_url:
            return ValidationErrorResponse(
                errors={'cover_url': 'This field is required'},
                message='cover_url is required'
            )

        # Validate URL format
        if not cover_url.startswith(('http://', 'https://')):
            return ValidationErrorResponse(
                errors={'cover_url': 'Must be a valid HTTP(S) URL'},
                message='Invalid cover URL format'
            )

        # Update cover URL
        playlist.cover_url = cover_url
        playlist.save()

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Cover image updated successfully'
        )


class CoverDeleteView(APIView):
    """
    DELETE /api/playlists/{id}/cover/

    Remove the cover image from a playlist.
    Sets cover_url back to empty string (will show gradient placeholder).
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized to modify this playlist')

        # Clear cover URL
        playlist.cover_url = ''
        playlist.save()

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Cover image updated successfully'
        )


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return SuccessResponse(
            data={'status': 'healthy', 'service': 'playlist', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )


class UserPlaylistsView(APIView):
    """
    GET /api/users/{id}/playlists/

    Returns playlists for a specific user:
    - If requesting own playlists: shows all (public + private)
    - If requesting others' playlists: shows only public
    - Supports all filtering parameters from PlaylistViewSet
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, user_id):
        # Start with all playlists for this user
        qs = Playlist.objects.filter(owner_id=user_id)

        # Privacy check: if not requesting own playlists, only show public
        if request.user.id != user_id:
            qs = qs.filter(visibility='public')

        # Apply the same filtering logic as PlaylistViewSet
        # Visibility filter
        visibility = request.query_params.get('visibility')
        if visibility in ['public', 'private']:
            qs = qs.filter(visibility=visibility)

        # Type filter
        playlist_type = request.query_params.get('type')
        if playlist_type in ['solo', 'collaborative']:
            qs = qs.filter(playlist_type=playlist_type)

        # Filter by system-generated vs user-created
        is_system_generated = request.query_params.get('is_system_generated')
        if is_system_generated in ['true', 'false']:
            qs = qs.filter(is_system_generated=(is_system_generated == 'true'))

        # Search
        query = request.query_params.get('q')
        if query:
            qs = qs.filter(
                Q(name__icontains=query) |
                Q(description__icontains=query)
            )

        # Date range filters
        created_after = request.query_params.get('created_after')
        if created_after:
            try:
                qs = qs.filter(created_at__gte=created_after)
            except ValueError:
                pass

        created_before = request.query_params.get('created_before')
        if created_before:
            try:
                qs = qs.filter(created_at__lte=created_before)
            except ValueError:
                pass

        # Exclude archived by default
        if request.query_params.get('include_archived') != 'true':
            qs = qs.exclude(archived_by__user_id=request.user.id)

        # Sorting
        sort = request.query_params.get('sort', 'updated_at')
        order = request.query_params.get('order', 'desc')
        order_field = PLAYLIST_SORT_MAP.get(sort, 'updated_at')

        if sort == 'track_count':
            qs = qs.annotate(track_count=Count('tracks'))

        if order == 'desc':
            order_field = '-' + order_field

        qs = qs.order_by(order_field)

        # Pagination limit
        limit = int(request.query_params.get('limit', 50))
        offset = int(request.query_params.get('offset', 0))

        total = qs.count()
        playlists = qs[offset:offset + limit]

        return SuccessResponse(
            data={
                'user_id': user_id,
                'total': total,
                'limit': limit,
                'offset': offset,
                'playlists': PlaylistSerializer(playlists, many=True).data
            },
            message=f'Retrieved {len(playlists)} playlists'
        )


class PlaylistFollowView(APIView):
    """
    POST /api/playlists/{id}/follow/ - Follow a playlist
    DELETE /api/playlists/{id}/follow/ - Unfollow a playlist
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Cannot follow own playlists
        if playlist.owner_id == request.user.id:
            return ValidationErrorResponse(
                errors={'operation': 'Cannot follow your own playlist'},
                message='Cannot follow your own playlist'
            )

        # Can only follow public playlists
        if playlist.visibility != 'public':
            return ValidationErrorResponse(
                errors={'operation': 'Can only follow public playlists'},
                message='Can only follow public playlists'
            )

        # Create follow relationship (idempotent)
        follow, created = UserPlaylistFollow.objects.get_or_create(
            user_id=request.user.id,
            playlist=playlist
        )

        if not created:
            return SuccessResponse(
                data={'followed_at': follow.followed_at},
                message='Already following this playlist'
            )

        return SuccessResponse(
            data={'followed_at': follow.followed_at},
            message='Playlist followed successfully',
            status_code=201
        )

    def delete(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Delete follow relationship
        deleted_count, _ = UserPlaylistFollow.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).delete()

        if deleted_count == 0:
            return SuccessResponse(
                message='Not following this playlist'
            )

        return SuccessResponse(
            message='Playlist unfollowed successfully'
        )


class PlaylistLikeView(APIView):
    """
    POST /api/playlists/{id}/like/ - Like a playlist
    DELETE /api/playlists/{id}/like/ - Unlike a playlist
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Cannot like own playlists
        if playlist.owner_id == request.user.id:
            return ValidationErrorResponse(
                errors={'operation': 'Cannot like your own playlist'},
                message='Cannot like your own playlist'
            )

        # Can only like public playlists
        if playlist.visibility != 'public':
            return ValidationErrorResponse(
                errors={'operation': 'Can only like public playlists'},
                message='Can only like public playlists'
            )

        # Create like relationship (idempotent)
        like, created = UserPlaylistLike.objects.get_or_create(
            user_id=request.user.id,
            playlist=playlist
        )

        if not created:
            return SuccessResponse(
                data={'liked_at': like.liked_at},
                message='Already liked this playlist'
            )

        return SuccessResponse(
            data={'liked_at': like.liked_at},
            message='Playlist liked successfully',
            status_code=201
        )

    def delete(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Delete like relationship
        deleted_count, _ = UserPlaylistLike.objects.filter(
            user_id=request.user.id,
            playlist=playlist
        ).delete()

        if deleted_count == 0:
            return SuccessResponse(
                message='Not liking this playlist'
            )

        return SuccessResponse(
            message='Playlist unliked successfully'
        )


class RecommendedPlaylistsView(APIView):
    """
    GET /api/playlists/recommended/

    Returns personalized playlist recommendations:
    - Based on user's liked playlists' genres
    - Based on user's followed playlists' genres
    - Excludes already liked/followed playlists
    - Ranked by genre overlap score
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        limit = int(request.query_params.get('limit', 20))

        # Get genres from user's liked playlists
        liked_playlist_ids = UserPlaylistLike.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Get genres from user's followed playlists
        followed_playlist_ids = UserPlaylistFollow.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Combine to get user's preferred genres
        preferred_playlist_ids = set(liked_playlist_ids) | set(followed_playlist_ids)

        if not preferred_playlist_ids:
            # No preferences, return featured playlists
            return SuccessResponse(
                data={
                    'recommendation_type': 'featured',
                    'playlists': FeaturedPlaylistsView.as_view()(request._request).data
                },
                message='Featured playlists returned'
            )

        # Get genres from user's preferred playlists
        from trackapp.models import Track

        preferred_genres = list(
            Track.objects.filter(
                playlist_id__in=preferred_playlist_ids
            ).exclude(
                song__genre=''
            ).values_list('song__genre', flat=True).distinct()
        )

        if not preferred_genres:
            # No genres found, return featured playlists
            return SuccessResponse(
                data={
                    'recommendation_type': 'featured',
                    'playlists': FeaturedPlaylistsView.as_view()(request._request).data
                },
                message='Featured playlists returned'
            )

        # Find playlists with similar genres (excluding user's own)

        # Find playlists with matching genres
        playlist_genre_scores = {}
        playlists_with_genres = Track.objects.filter(
            song__genre__in=preferred_genres
        ).exclude(
            playlist_id__in=Playlist.objects.filter(owner_id=request.user.id)
        ).values('playlist_id', 'song__genre')

        # Calculate genre overlap scores
        for item in playlists_with_genres:
            pid = item['playlist_id']
            genre_name = item['song__genre']

            if pid not in playlist_genre_scores:
                playlist_genre_scores[pid] = {'matches': 0, 'genres': set()}
            if genre_name in preferred_genres:
                playlist_genre_scores[pid]['matches'] += 1
                playlist_genre_scores[pid]['genres'].add(genre_name)

        # Sort by match count
        sorted_playlists = sorted(
            playlist_genre_scores.items(),
            key=lambda x: x[1]['matches'],
            reverse=True
        )

        # Get top N playlists
        top_playlist_ids = [pid for pid, _ in sorted_playlists[:limit]]

        playlists = Playlist.objects.filter(
            id__in=top_playlist_ids,
            visibility='public'
        ).annotate(
            track_count=Count('tracks')
        )

        # Maintain order by score
        playlist_dict = {p.id: p for p in playlists}
        ordered_playlists = []
        for pid in top_playlist_ids:
            if pid in playlist_dict:
                ordered_playlists.append(playlist_dict[pid])

        return SuccessResponse(
            data={
                'recommendation_type': 'genre_based',
                'preferred_genres': preferred_genres,
                'total': len(ordered_playlists),
                'playlists': PlaylistSerializer(ordered_playlists, many=True).data
            },
            message=f'Genre-based recommendations: {len(ordered_playlists)} playlists'
        )


class SimilarPlaylistsView(APIView):
    """
    GET /api/playlists/{id}/similar/

    Returns playlists similar to the given playlist:
    - Based on genre overlap
    - Based on track count similarity
    - Excludes the playlist itself
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        limit = int(request.query_params.get('limit', 10))

        # Get genres from this playlist
        from trackapp.models import Track

        playlist_genres = list(
            Track.objects.filter(
                playlist=playlist
            ).exclude(
                song__genre=''
            ).values_list('song__genre', flat=True).distinct()
        )

        if not playlist_genres:
            return SuccessResponse(
                data={'similar_playlists': []},
                message='No genres found in this playlist'
            )

        # Find playlists with similar genres
        similar_candidates = Track.objects.filter(
            song__genre__in=playlist_genres
        ).exclude(
            playlist_id=playlist_id
        ).values('playlist_id', 'song__genre')

        # Calculate Jaccard similarity (intersection / union)
        # OPTIMIZATION: Fetch all candidate genres in one query to avoid N+1
        playlist_a_genres = set(playlist_genres)

        # Get all playlist-genre pairs in a single query
        candidate_playlist_ids = [c['playlist_id'] for c in similar_candidates]
        all_candidate_genres = Track.objects.filter(
            playlist_id__in=candidate_playlist_ids
        ).exclude(
            song__genre=''
        ).values_list('playlist_id', 'song__genre')

        # Build playlist->genres mapping
        playlist_genres_map = {}
        for pid, genre in all_candidate_genres:
            if pid not in playlist_genres_map:
                playlist_genres_map[pid] = set()
            playlist_genres_map[pid].add(genre)

        # Calculate Jaccard similarity using pre-fetched genres
        playlist_similarities = {}
        for pid in candidate_playlist_ids:
            if pid in playlist_genres_map:
                candidate_genres = playlist_genres_map[pid]
                intersection = len(playlist_a_genres & candidate_genres)
                union = len(playlist_a_genres | candidate_genres)

                if union > 0:
                    jaccard_score = intersection / union
                    playlist_similarities[pid] = jaccard_score

        # Sort by similarity score
        sorted_similar = sorted(
            playlist_similarities.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        # Get playlist objects
        similar_ids = [pid for pid, _ in sorted_similar]

        similar_playlists = Playlist.objects.filter(
            id__in=similar_ids,
            visibility='public'
        ).annotate(
            track_count=Count('tracks')
        )

        # Order by similarity score
        playlist_dict = {p.id: p for p in similar_playlists}
        ordered_playlists = []
        for pid in similar_ids:
            if pid in playlist_dict:
                ordered_playlists.append(playlist_dict[pid])

        return SuccessResponse(
            data={
                'playlist_id': playlist_id,
                'playlist_name': playlist.name,
                'playlist_genres': playlist_genres,
                'total': len(ordered_playlists),
                'similar_playlists': PlaylistSerializer(ordered_playlists, many=True).data
            },
            message=f'Found {len(ordered_playlists)} similar playlists'
        )


class AutoGeneratedPlaylistsView(APIView):
    """
    GET /api/playlists/auto-generated/

    Returns auto-generated playlist suggestions based on:
    - User's most listened genres
    - Trending genres across platform
    - Mood-based mixes

    POST /api/playlists/auto-generated/

    Creates an auto-generated playlist:
    - Based on specified genre or mood
    - Picks top tracks from that category
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get auto-generated playlist suggestions"""
        # OPTIMIZATION: Fetch liked playlist IDs once and reuse
        liked_playlist_ids = UserPlaylistLike.objects.filter(
            user_id=request.user.id
        ).values_list('playlist_id', flat=True)

        # Get user's favorite genres from their liked playlists in a single query
        liked_genres = list(
            Track.objects.filter(
                playlist_id__in=liked_playlist_ids
            ).exclude(
                song__genre=''
            ).values_list('song__genre', flat=True)
        )

        # Count genre occurrences
        from collections import Counter
        genre_counts = Counter(liked_genres)

        # Get top genres
        top_genres = [genre for genre, _ in genre_counts.most_common(5)]

        if not top_genres:
            # Fallback to popular genres across platform
            top_genres = ['Pop', 'Rock', 'Hip-Hop', 'Electronic', 'Jazz']

        suggestions = []
        for genre in top_genres:
            # Count tracks available in this genre
            track_count = Track.objects.filter(
                song__genre=genre
            ).count()

            if track_count > 0:
                suggestions.append({
                    'type': 'genre_based',
                    'name': f'{genre} Mix',
                    'description': f'Auto-generated playlist based on {genre} genre',
                    'estimated_track_count': track_count,
                    'genre': genre
                })

        # Add mood-based suggestions
        mood_suggestions = [
            {'type': 'mood_based', 'name': 'Chill Vibes', 'description': 'Relaxing tracks for unwinding', 'mood': 'chill'},
            {
                'type': 'mood_based',
                'name': 'Workout Mix',
                'description': 'High-energy tracks for workouts',
                'mood': 'energetic'
            },
            {'type': 'mood_based', 'name': 'Focus Flow', 'description': 'Concentration-boosting tracks', 'mood': 'focus'},
        ]

        return SuccessResponse(
            data={'suggestions': suggestions + mood_suggestions},
            message='Auto-generated playlist suggestions retrieved'
        )

    def post(self, request):
        """Create an auto-generated playlist"""
        generation_type = request.data.get('generation_type', 'genre')  # genre, taste, trending, new_releases, similar_song
        name = request.data.get('name')
        track_limit = int(request.data.get('track_limit', 20))

        # Parameters for different generation types
        genre = request.data.get('genre')
        mood = request.data.get('mood')
        song_id = request.data.get('song_id')  # For similar_song type

        # Validate required parameters
        if generation_type == 'genre' and not genre:
            return ValidationErrorResponse(
                errors={'genre': 'Genre is required for genre-based generation'},
                message='Genre is required for genre-based generation'
            )
        if generation_type == 'similar_song' and not song_id:
            return ValidationErrorResponse(
                errors={'song_id': 'Song ID is required for similar song generation'},
                message='Song ID is required for similar song generation'
            )

        # Determine playlist name if not provided
        if not name:
            if generation_type == 'taste':
                name = 'For You Mix'
            elif generation_type == 'trending':
                name = 'Trending Now'
            elif generation_type == 'new_releases':
                name = 'New Releases'
            elif generation_type == 'similar_song':
                name = 'Similar Tracks'
            elif genre:
                name = f'{genre} Mix'
            elif mood:
                name = f'{mood.capitalize()} Mix'
            else:
                name = 'Auto-Generated Playlist'

        # Import searchapp models for recommendation integration
        from searchapp.models import Song

        # Find tracks based on generation type
        tracks_to_add = []

        if generation_type == 'taste':
            # Use personalized recommendations
            import requests
            from django.conf import settings

            # Call internal recommendations endpoint
            try:
                # Get recommended songs from searchapp
                from searchapp.views import RecommendationsView
                from django.test import RequestFactory

                factory = RequestFactory()
                rec_request = factory.get(f'/api/discover/recommendations/?limit={track_limit}')
                rec_request.user = request.user

                view = RecommendationsView.as_view()
                response = view(rec_request)
                response_data = response.data

                if response_data.get('recommendation_type') == 'personalized':
                    song_ids = [song['id'] for song in response_data['songs']]
                    tracks_to_add = Track.objects.filter(
                        song_id__in=song_ids
                    ).select_related('song', 'song__artist', 'song__album')[:track_limit]
                else:
                    # Fallback to trending
                    tracks_to_add = Track.objects.filter(
                        song__popularity_score__gt=0
                    ).select_related('song', 'song__artist', 'song__album').order_by(
                        '-song__popularity_score'
                    )[:track_limit]
            except Exception as e:
                # Fallback to trending on error
                tracks_to_add = Track.objects.filter(
                    song__popularity_score__gt=0
                ).select_related('song', 'song__artist', 'song__album').order_by(
                    '-song__popularity_score'
                )[:track_limit]

        elif generation_type == 'trending':
            # Get trending songs
            trending_songs = Song.objects.filter(
                popularity_score__gt=0
            ).order_by('-popularity_score', '-release_date')[:track_limit]

            tracks_to_add = []
            for song in trending_songs:
                tracks_to_add.append(Track(
                    song=song,
                    added_by_id=request.user.id,
                    position=len(tracks_to_add)
                ))

        elif generation_type == 'new_releases':
            # Get new releases (last 90 days)
            from datetime import datetime, timedelta
            since_date = datetime.now().date() - timedelta(days=90)

            new_songs = Song.objects.filter(
                release_date__gte=since_date
            ).order_by('-release_date', '-popularity_score')[:track_limit]

            tracks_to_add = []
            for song in new_songs:
                tracks_to_add.append(Track(
                    song=song,
                    added_by_id=request.user.id,
                    position=len(tracks_to_add)
                ))

        elif generation_type == 'similar_song':
            # Get songs similar to the given song
            try:
                reference_song = Song.objects.get(id=song_id)
            except Song.DoesNotExist:
                return NotFoundResponse(message='Reference song not found')

            # Find similar songs (same genre or artist)
            similar_songs = Song.objects.filter(
                Q(genre__iexact=reference_song.genre) |
                Q(artist_id=reference_song.artist_id)
            ).exclude(
                id=reference_song.id
            ).select_related('artist', 'album').order_by(
                '-popularity_score'
            )[:track_limit]

            tracks_to_add = []
            for song in similar_songs:
                tracks_to_add.append(Track(
                    song=song,
                    added_by_id=request.user.id,
                    position=len(tracks_to_add)
                ))

        else:  # genre or mood-based (original logic)
            tracks_queryset = Track.objects.select_related('song', 'song__artist', 'song__album')

            if genre:
                tracks_to_add = tracks_queryset.filter(
                    song__genre=genre
                ).order_by('-added_at')[:track_limit]
            else:
                # For mood, we'll use genre as a proxy
                mood_genre_map = {
                    'chill': ['Jazz', 'Ambient', 'Lo-Fi', 'Classical'],
                    'energetic': ['Rock', 'Electronic', 'Hip-Hop', 'Pop'],
                    'focus': ['Classical', 'Ambient', 'Electronic'],
                }

                genres = mood_genre_map.get(mood, ['Pop'])
                tracks_to_add = tracks_queryset.filter(
                    song__genre__in=genres
                ).order_by('-added_at')[:track_limit]

        if not tracks_to_add:
            return NotFoundResponse(message='No tracks found for the specified criteria')

        # Create the playlist
        description = f'Auto-generated playlist based on {generation_type}'
        if genre:
            description = f'Auto-generated {genre} playlist'
        elif song_id:
            description = 'Songs similar to your selection'
        elif generation_type == 'taste':
            description = 'Personalized recommendations based on your taste'

        playlist = Playlist.objects.create(
            owner_id=request.user.id,
            name=name,
            description=description,
            visibility='private',
            playlist_type='solo',
            is_system_generated=True,
            max_songs=len(tracks_to_add)
        )

        # Add tracks to playlist
        new_tracks = []
        for index, track in enumerate(tracks_to_add):
            if isinstance(track, Track):
                # Track already exists (from queryset), need to duplicate it
                new_tracks.append(Track(
                    playlist=playlist,
                    song=track.song,
                    added_by_id=request.user.id,
                    position=index
                ))
            else:
                # Track created new (with song reference)
                new_tracks.append(track)

        Track.objects.bulk_create(new_tracks)

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Auto-generated playlist created successfully',
            status_code=201
        )


class EnhancedBatchDeleteView(APIView):
    """
    DELETE /api/playlists/batch-delete-advanced/

    Enhanced batch delete with detailed error tracking:
    - Returns per-playlist deletion results
    - Includes reasons for failures
    - Supports partial success
    - Creates snapshots before deletion
    """
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        playlist_ids = request.data.get('playlist_ids', [])

        if not playlist_ids:
            return ValidationErrorResponse(
                errors={'playlist_ids': 'This field is required'},
                message='playlist_ids is required'
            )

        if not isinstance(playlist_ids, list):
            return ValidationErrorResponse(
                errors={'playlist_ids': 'Must be a list'},
                message='playlist_ids must be a list'
            )

        create_snapshots = request.data.get('create_snapshots', False)

        results = []
        deleted_count = 0
        failed_count = 0

        for playlist_id in playlist_ids:
            try:
                playlist = Playlist.objects.get(id=playlist_id)

                if playlist.owner_id != request.user.id:
                    results.append({
                        'playlist_id': playlist_id,
                        'status': 'failed',
                        'reason': 'not_authorized'
                    })
                    failed_count += 1
                    continue

                # Create snapshot before deletion if requested
                if create_snapshots:
                    snapshot_data = PlaylistSerializer(playlist).data
                    PlaylistSnapshot.objects.create(
                        playlist=playlist,
                        snapshot_data=snapshot_data,
                        created_by=request.user.id,
                        change_reason='Snapshot before deletion',
                        track_count=playlist.tracks.count()
                    )

                # Delete playlist
                playlist_name = playlist.name
                playlist.delete()

                results.append({
                    'playlist_id': playlist_id,
                    'status': 'deleted',
                    'name': playlist_name
                })
                deleted_count += 1

            except Playlist.DoesNotExist:
                results.append({
                    'playlist_id': playlist_id,
                    'status': 'failed',
                    'reason': 'not_found'
                })
                failed_count += 1

        return SuccessResponse(
            data={
                'total': len(playlist_ids),
                'deleted': deleted_count,
                'failed': failed_count,
                'results': results
            },
            message=f'Snapshot batch delete completed: {deleted_count} deleted'
        )


class PlaylistExportView(APIView):
    """
    GET /api/playlists/{id}/export/

    Export playlist to JSON format:
    - Includes metadata and all tracks
    - Includes song details (artist, album, genre)
    - Can be used for backup or import
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization check
        if playlist.owner_id != request.user.id and playlist.visibility != 'public':
            return ForbiddenResponse(message='Not authorized to export this playlist')

        # Get all tracks with song details
        tracks = Track.objects.filter(
            playlist=playlist
        ).select_related(
            'song__artist', 'song__album'
        ).order_by('position')

        # Build export data
        export_data = {
            'playlist': {
                'id': playlist.id,
                'name': playlist.name,
                'description': playlist.description,
                'visibility': playlist.visibility,
                'playlist_type': playlist.playlist_type,
                'max_songs': playlist.max_songs,
                'created_at': playlist.created_at.isoformat(),
                'updated_at': playlist.updated_at.isoformat(),
                'cover_url': playlist.cover_url,
            },
            'tracks': [],
            'export_metadata': {
                'exported_at': timezone.now().isoformat(),
                'exported_by': request.user.id,
                'track_count': tracks.count(),
                'version': '1.0'
            }
        }

        # Add track details
        for track in tracks:
            track_data = {
                'position': track.position,
                'added_at': track.added_at.isoformat() if track.added_at else None,
                'song': {
                    'id': track.song.id,
                    'title': track.song.title,
                    'duration_seconds': track.song.duration_seconds,
                    'genre': track.song.genre,
                    'release_date': track.song.release_date.isoformat() if track.song.release_date else None,
                    'artist': {
                        'id': track.song.artist.id,
                        'name': track.song.artist.name
                    } if track.song.artist else None,
                    'album': {
                        'id': track.song.album.id,
                        'name': track.song.album.name,
                        'cover_url': track.song.album.cover_url
                    } if track.song.album else None
                }
            }
            export_data['tracks'].append(track_data)

        return SuccessResponse(
            data=export_data,
            message='Playlist exported successfully'
        )


class PlaylistImportView(APIView):
    """
    POST /api/playlists/import/

    Import playlist from JSON export:
    - Creates new playlist from export data
    - Validates data integrity
    - Creates all tracks with relationships
    - Supports custom name (for duplicates)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        import_data = request.data.get('playlist')

        if not import_data:
            return ValidationErrorResponse(
                errors={'playlist': 'This field is required'},
                message='playlist data is required'
            )

        try:
            # Extract playlist data
            name = request.data.get('name', import_data.get('name', 'Imported Playlist'))
            description = import_data.get('description', '')
            visibility = import_data.get('visibility', 'private')
            playlist_type = import_data.get('playlist_type', 'solo')
            max_songs = import_data.get('max_songs', 0)
            cover_url = import_data.get('cover_url', '')

            tracks_data = import_data.get('tracks', [])

            # Validate data
            if visibility not in ['public', 'private']:
                visibility = 'private'

            if playlist_type not in ['solo', 'collaborative']:
                playlist_type = 'solo'

            # Create playlist
            from django.db import transaction
            with transaction.atomic():
                playlist = Playlist.objects.create(
                    owner_id=request.user.id,
                    name=name,
                    description=description,
                    visibility=visibility,
                    playlist_type=playlist_type,
                    max_songs=max_songs,
                    cover_url=cover_url
                )

                # Import tracks
                from trackapp.models import Song
                imported_tracks = []

                for track_data in tracks_data:
                    song_data = track_data.get('song')
                    if not song_data:
                        continue

                    try:
                        # Find or create song
                        song_id = song_data.get('id')
                        song = None

                        if song_id:
                            song = Song.objects.filter(id=song_id).first()

                        if not song:
                            # Try to find by title and artist
                            from artistapp.models import Artist

                            artist_name = song_data.get('artist', {}).get('name') if song_data.get('artist') else None
                            title = song_data.get('title')

                            if artist_name and title:
                                artist = Artist.objects.filter(name=artist_name).first()
                                if artist:
                                    song = Song.objects.filter(
                                        title=title,
                                        artist=artist
                                    ).first()

                        if song:
                            imported_tracks.append(Track(
                                playlist=playlist,
                                song=song,
                                added_by_id=request.user.id,
                                position=track_data.get('position', len(imported_tracks))
                            ))

                    except Exception:
                        # Skip tracks that can't be imported
                        continue

                # Bulk create tracks
                if imported_tracks:
                    Track.objects.bulk_create(imported_tracks)
                    playlist.max_songs = len(imported_tracks)
                    playlist.save()

            return SuccessResponse(
                data=PlaylistSerializer(playlist).data,
                message='Playlist imported successfully',
                status_code=201
            )

        except Exception as e:
            return ErrorResponse(
                error='import_failed',
                message=str(e)
            )


class PlaylistSnapshotView(APIView):
    """
    GET /api/playlists/{id}/snapshots/

    List all snapshots for a playlist

    POST /api/playlists/{id}/snapshots/

    Create a manual snapshot

    DELETE /api/playlists/{id}/snapshots/

    Delete old snapshots (cleanup)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        limit = int(request.query_params.get('limit', 20))

        snapshots = playlist.snapshots.all()[:limit]

        return SuccessResponse(
            data={
                'playlist_id': playlist_id,
                'total': snapshots.count(),
                'snapshots': PlaylistSnapshotSerializer(snapshots, many=True).data
            },
            message=f'Retrieved {snapshots.count()} snapshots'
        )

    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        change_reason = request.data.get('change_reason', 'Manual snapshot')

        # Create snapshot
        from .serializers import PlaylistSerializer
        playlist_data = PlaylistSerializer(playlist).data

        snapshot = PlaylistSnapshot.objects.create(
            playlist=playlist,
            snapshot_data=playlist_data,
            created_by=request.user.id,
            change_reason=change_reason,
            track_count=playlist.tracks.count()
        )

        return SuccessResponse(
            data=PlaylistSnapshotSerializer(snapshot).data,
            message='Snapshot created successfully',
            status_code=201
        )

    def delete(self, request, playlist_id):
        """Delete old snapshots, keep only N most recent"""
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        keep = int(request.data.get('keep', 10))

        # Get all snapshots ordered by date
        all_snapshots = list(playlist.snapshots.all())

        if len(all_snapshots) <= keep:
            return SuccessResponse(
                data={'total_snapshots': len(all_snapshots)},
                message='No snapshots to delete'
            )

        # Delete older snapshots
        to_delete = all_snapshots[keep:]
        deleted_count = 0

        for snapshot in to_delete:
            snapshot.delete()
            deleted_count += 1

        return SuccessResponse(
            data={'kept': keep, 'deleted': deleted_count},
            message=f'Deleted {deleted_count} old snapshots'
        )


class PlaylistRestoreView(APIView):
    """
    POST /api/playlists/{id}/restore/{snapshot_id}/

    Restore playlist from a snapshot
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id, snapshot_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization
        if playlist.owner_id != request.user.id:
            return ForbiddenResponse(message='Not authorized')

        try:
            snapshot = PlaylistSnapshot.objects.get(id=snapshot_id, playlist=playlist)
        except PlaylistSnapshot.DoesNotExist:
            return NotFoundResponse(message='Snapshot not found for this playlist')

        # Create snapshot of current state before restoring
        current_snapshot_data = PlaylistSerializer(playlist).data
        PlaylistSnapshot.objects.create(
            playlist=playlist,
            snapshot_data=current_snapshot_data,
            created_by=request.user.id,
            change_reason='Auto-snapshot before restore',
            track_count=playlist.tracks.count()
        )

        # Restore from snapshot
        from django.db import transaction
        with transaction.atomic():
            snapshot_data = snapshot.snapshot_data

            # Restore playlist fields
            playlist.name = snapshot_data.get('name', playlist.name)
            playlist.description = snapshot_data.get('description', playlist.description)
            playlist.visibility = snapshot_data.get('visibility', playlist.visibility)
            playlist.playlist_type = snapshot_data.get('playlist_type', playlist.playlist_type)
            playlist.max_songs = snapshot_data.get('max_songs', playlist.max_songs)
            playlist.cover_url = snapshot_data.get('cover_url', playlist.cover_url)
            playlist.save()

            # Delete all current tracks
            Track.objects.filter(playlist=playlist).delete()

            # Restore tracks from snapshot
            # Note: This assumes songs still exist in database
            restored_tracks = []
            for track_data in snapshot_data.get('tracks', []):
                song_id = track_data.get('song', {}).get('id')
                if song_id:
                    try:
                        from trackapp.models import Song
                        song = Song.objects.get(id=song_id)
                        restored_tracks.append(Track(
                            playlist=playlist,
                            song=song,
                            added_by_id=request.user.id,
                            position=track_data.get('position')
                        ))
                    except Song.DoesNotExist:
                        # Skip tracks where song no longer exists
                        continue

            if restored_tracks:
                Track.objects.bulk_create(restored_tracks)

        return SuccessResponse(
            data=PlaylistSerializer(playlist).data,
            message='Playlist restored successfully from snapshot'
        )


class PlaylistCommentsView(APIView):
    """
    GET /api/playlists/{id}/comments/

    List all comments for a playlist (threaded):
    - Top-level comments only (parent_id is null)
    - Includes replies_count
    - Supports pagination
    - Sorted by most recent first

    POST /api/playlists/{id}/comments/

    Create a new comment on a playlist:
    - Optional parent_id for replies
    - Auto-sets user_id from authenticated user
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization: can view comments on public playlists or own playlists
        if playlist.owner_id != request.user.id and playlist.visibility != 'public':
            return ForbiddenResponse(message='Not authorized to view comments on this playlist')

        # Get top-level comments only (no parent)
        comments = PlaylistComment.objects.filter(
            playlist_id=playlist_id,
            parent_id__isnull=True,
            is_deleted=False
        ).select_related('user').order_by('-created_at')

        # Pagination
        limit = int(request.query_params.get('limit', 20))
        offset = int(request.query_params.get('offset', 0))

        total = comments.count()
        comments_page = comments[offset:offset + limit]

        # Set current user for is_liked check
        serializer = PlaylistCommentSerializer(
            comments_page,
            many=True,
            context={'request': request}
        )

        return SuccessResponse(
            data={
                'playlist_id': playlist_id,
                'total': total,
                'limit': limit,
                'offset': offset,
                'comments': serializer.data
            },
            message=f'Retrieved {len(serializer.data)} comments'
        )

    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Authorization: can comment on public playlists or own playlists
        if playlist.owner_id != request.user.id and playlist.visibility != 'public':
            return ForbiddenResponse(message='Not authorized to comment on this playlist')

        content = request.data.get('content')
        if not content or not content.strip():
            return ValidationErrorResponse(
                errors={'content': 'This field is required and cannot be empty'},
                message='Comment content is required'
            )

        parent_id = request.data.get('parent_id')

        # Validate parent_id if provided
        if parent_id:
            try:
                parent_comment = PlaylistComment.objects.get(
                    id=parent_id,
                    playlist_id=playlist_id,
                    is_deleted=False
                )
                # Don't allow replying to replies (max 2 levels)
                if parent_comment.parent_id is not None:
                    return ValidationErrorResponse(
                        errors={'parent_id': 'Cannot reply to a reply (max 2 levels)'},
                        message='Cannot reply to a reply'
                    )
            except PlaylistComment.DoesNotExist:
                return NotFoundResponse(message='Parent comment not found')

        # Create comment
        comment = PlaylistComment.objects.create(
            playlist_id=playlist_id,
            user_id=request.user.id,
            parent_id=parent_id,
            content=content.strip()
        )

        serializer = PlaylistCommentSerializer(
            comment,
            context={'request': request}
        )

        return SuccessResponse(
            data=serializer.data,
            message='Comment created successfully',
            status_code=201
        )


class CommentDetailView(APIView):
    """
    GET /api/comments/{id}/

    Get a single comment with its replies

    PATCH /api/comments/{id}/

    Update a comment (content only):
    - Only by comment author
    - Sets is_edited flag

    DELETE /api/comments/{id}/

    Soft delete a comment:
    - Only by comment author
    - Sets is_deleted flag (content remains but marked as deleted)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.select_related('user').get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check playlist access
        try:
            playlist = Playlist.objects.get(id=comment.playlist_id)
            if playlist.owner_id != request.user.id and playlist.visibility != 'public':
                return ForbiddenResponse(message='Not authorized to view this comment')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        serializer = PlaylistCommentSerializer(
            comment,
            context={'request': request}
        )

        return SuccessResponse(
            data=serializer.data,
            message='Comment retrieved successfully'
        )

    def patch(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Only author can edit
        if comment.user_id != request.user.id:
            return ForbiddenResponse(message='Not authorized to edit this comment')

        content = request.data.get('content')
        if not content or not content.strip():
            return ValidationErrorResponse(
                errors={'content': 'This field is required and cannot be empty'},
                message='Comment content is required'
            )

        # Update comment
        comment.content = content.strip()
        comment.is_edited = True
        comment.save()

        serializer = PlaylistCommentSerializer(
            comment,
            context={'request': request}
        )

        return SuccessResponse(
            data=serializer.data,
            message='Comment updated successfully'
        )

    def delete(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Only author can delete
        if comment.user_id != request.user.id:
            return ForbiddenResponse(message='Not authorized to delete this comment')

        # Soft delete
        comment.is_deleted = True
        comment.save()

        return SuccessResponse(
            message='Comment deleted successfully'
        )


class CommentRepliesView(APIView):
    """
    GET /api/comments/{id}/replies/

    Get all replies to a comment:
    - Direct replies only (one level deep)
    - Sorted by most recent first
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, comment_id):
        try:
            parent_comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check playlist access
        try:
            playlist = Playlist.objects.get(id=parent_comment.playlist_id)
            if playlist.owner_id != request.user.id and playlist.visibility != 'public':
                return ForbiddenResponse(message='Not authorized to view replies')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Get replies
        replies = PlaylistComment.objects.filter(
            parent_id=comment_id,
            is_deleted=False
        ).select_related('user').order_by('-created_at')

        serializer = PlaylistCommentSerializer(
            replies,
            many=True,
            context={'request': request}
        )

        return SuccessResponse(
            data={
                'comment_id': comment_id,
                'total': replies.count(),
                'replies': serializer.data
            },
            message=f'Retrieved {replies.count()} replies'
        )


class CommentLikeView(APIView):
    """
    POST /api/comments/{id}/like/

    Like a comment:
    - Idempotent (can like again without error)
    - Increments likes_count

    DELETE /api/comments/{id}/like/

    Unlike a comment:
    - Decrements likes_count
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Check playlist access
        try:
            playlist = Playlist.objects.get(id=comment.playlist_id)
            if playlist.owner_id != request.user.id and playlist.visibility != 'public':
                return ForbiddenResponse(message='Not authorized to like comments on this playlist')
        except Playlist.DoesNotExist:
            return NotFoundResponse(message='Playlist not found')

        # Cannot like own comments
        if comment.user_id == request.user.id:
            return ValidationErrorResponse(
                message='Cannot like your own comment'
            )

        # Create like (idempotent)
        like, created = PlaylistCommentLike.objects.get_or_create(
            comment_id=comment_id,
            user_id=request.user.id
        )

        if created:
            # Increment likes count
            comment.likes_count += 1
            comment.save()

        serializer = PlaylistCommentLikeSerializer(like)

        return SuccessResponse(
            data=serializer.data,
            message='Comment liked successfully' if created else 'Already liked this comment',
            status_code=201 if created else 200
        )

    def delete(self, request, comment_id):
        try:
            comment = PlaylistComment.objects.get(
                id=comment_id,
                is_deleted=False
            )
        except PlaylistComment.DoesNotExist:
            return NotFoundResponse(message='Comment not found')

        # Delete like
        deleted_count, _ = PlaylistCommentLike.objects.filter(
            comment_id=comment_id,
            user_id=request.user.id
        ).delete()

        if deleted_count > 0:
            # Decrement likes count
            comment.likes_count = max(0, comment.likes_count - 1)
            comment.save()

        return SuccessResponse(
            message='Comment unliked successfully' if deleted_count > 0 else 'Not liking this comment'
        )
