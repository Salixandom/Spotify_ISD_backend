from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from django.db import connection
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from datetime import timedelta
from .models import Playlist
from .serializers import PlaylistSerializer, PlaylistStatsSerializer
from trackapp.models import Track

PLAYLIST_SORT_MAP = {
    'name':        'name',
    'created_at':  'created_at',
    'updated_at':  'updated_at',
    'track_count': 'track_count',
}


class PlaylistViewSet(viewsets.ModelViewSet):
    serializer_class   = PlaylistSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Enhanced filtering for playlist list:
        - visibility: public|private
        - type: solo|collaborative
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
            # Will be implemented in Phase 3
            pass
        elif filter_type == 'liked':
            # Will be implemented in Phase 3
            pass

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

    def update(self, request, *args, **kwargs):
        playlist = self.get_object()
        if playlist.owner_id != request.user.id:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        playlist = self.get_object()
        if playlist.owner_id != request.user.id:
            return Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


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
            return Response({
                'error': 'playlist_not_found',
                'message': 'Playlist not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check authorization
        if playlist.owner_id != request.user.id and playlist.visibility != 'public':
            return Response({
                'error': 'forbidden',
                'message': 'Not authorized to view this playlist'
            }, status=status.HTTP_403_FORBIDDEN)

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

        # Collaborator count (will be implemented in Phase 3)
        collaborator_count = 0  # TODO: Integrate with collaboration service

        # Follow/like status (will be implemented in Phase 3)
        is_followed = False  # TODO: Check UserPlaylistFollow
        is_liked = False     # TODO: Check UserPlaylistLike

        # Format duration
        hours = total_duration // 3600
        minutes = (total_duration % 3600) // 60
        seconds = total_duration % 60
        duration_formatted = f"{hours}:{minutes:02d}:{seconds:02d}"

        return Response({
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
            'is_followed': is_followed,
            'is_liked': is_liked,
            'owner_id': playlist.owner_id,
            'cover_url': playlist.cover_url
        })


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

        return Response(PlaylistSerializer(qs, many=True).data)


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
            return Response({
                'error': 'playlist_not_found',
                'message': 'Playlist not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Authorization check - can only duplicate own playlists or public playlists
        if source.owner_id != request.user.id and source.visibility != 'public':
            return Response({
                'error': 'forbidden',
                'message': 'Not authorized to duplicate this playlist'
            }, status=status.HTTP_403_FORBIDDEN)

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

        return Response(
            PlaylistSerializer(new_playlist).data,
            status=status.HTTP_201_CREATED
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
            return Response({
                'error': 'invalid_input',
                'message': 'playlist_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(playlist_ids, list):
            return Response({
                'error': 'invalid_input',
                'message': 'playlist_ids must be a list'
            }, status=status.HTTP_400_BAD_REQUEST)

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

        return Response({
            'deleted': deleted,
            'not_found': not_found,
            'not_authorized': not_authorized
        }, status=status.HTTP_200_OK if deleted > 0 else status.HTTP_202_ACCEPTED)


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
            return Response({
                'error': 'invalid_input',
                'message': 'playlist_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not updates:
            return Response({
                'error': 'invalid_input',
                'message': 'updates field is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(playlist_ids, list):
            return Response({
                'error': 'invalid_input',
                'message': 'playlist_ids must be a list'
            }, status=status.HTTP_400_BAD_REQUEST)

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

        return Response({
            'updated': updated,
            'not_found': not_found,
            'not_authorized': not_authorized
        }, status=status.HTTP_200_OK if updated > 0 else status.HTTP_202_ACCEPTED)


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
            return Response({
                'error': 'playlist_not_found',
                'message': 'Playlist not found'
            }, status=status.HTTP_404_NOT_FOUND)

        if playlist.owner_id != request.user.id:
            return Response({
                'error': 'forbidden',
                'message': 'Not authorized to modify this playlist'
            }, status=status.HTTP_403_FORBIDDEN)

        # For now, we accept cover_url in the request body
        # Future enhancement: Handle multipart file upload
        cover_url = request.data.get('cover_url')

        if not cover_url:
            return Response({
                'error': 'invalid_input',
                'message': 'cover_url is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Validate URL format
        if not cover_url.startswith(('http://', 'https://')):
            return Response({
                'error': 'invalid_input',
                'message': 'cover_url must be a valid HTTP(S) URL'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Update cover URL
        playlist.cover_url = cover_url
        playlist.save()

        return Response(PlaylistSerializer(playlist).data, status=status.HTTP_200_OK)


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
            return Response({
                'error': 'playlist_not_found',
                'message': 'Playlist not found'
            }, status=status.HTTP_404_NOT_FOUND)

        if playlist.owner_id != request.user.id:
            return Response({
                'error': 'forbidden',
                'message': 'Not authorized to modify this playlist'
            }, status=status.HTTP_403_FORBIDDEN)

        # Clear cover URL
        playlist.cover_url = ''
        playlist.save()

        return Response(PlaylistSerializer(playlist).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return Response(
            {'status': 'healthy', 'service': 'playlist', 'database': 'connected'},
            status=200,
        )
    except Exception as e:
        return Response(
            {
                'status': 'unhealthy',
                'service': 'playlist',
                'database': 'disconnected',
                'error': str(e),
            },
            status=503,
        )
