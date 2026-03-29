from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from django.db import connection, transaction, IntegrityError
from django.db.models import Q
from playlistapp.models import Playlist, UserPlaylistArchive
from searchapp.models import Song
from .models import Track, UserTrackHide
from .serializers import TrackSerializer

def _require_playlist_owner(playlist_id, user_id):
    """Returns (playlist, None) if user owns the playlist, or (None, Response) otherwise."""
    try:
        playlist = Playlist.objects.get(id=playlist_id)
    except Playlist.DoesNotExist:
        return None, Response({'error': 'Playlist not found'}, status=status.HTTP_404_NOT_FOUND)
    if playlist.owner_id != user_id:
        return None, Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)
    return playlist, None


def _can_edit_playlist(playlist_id, user_id):
    """
    Check if user can edit playlist (owner or collaborator).
    Returns (playlist, None) if authorized, or (None, Response) otherwise.
    """
    try:
        playlist = Playlist.objects.get(id=playlist_id)
    except Playlist.DoesNotExist:
        return None, Response({'error': 'Playlist not found'}, status=status.HTTP_404_NOT_FOUND)

    # Owner can always edit
    if playlist.owner_id == user_id:
        return playlist, None

    # Check if user is a collaborator
    try:
        # Import here to avoid circular imports
        from collaboration.collabapp.models import Collaborator
        Collaborator.objects.get(playlist_id=playlist_id, user_id=user_id)
        return playlist, None
    except Collaborator.DoesNotExist:
        return None, Response({'error': 'Not authorized'}, status=status.HTTP_403_FORBIDDEN)


TRACK_SORT_MAP = {
    'custom':   'position',
    'title':    'song__title',
    'artist':   'song__artist__name',
    'album':    'song__album__name',
    'genre':    'song__genre',
    'duration': 'song__duration_seconds',
    'year':     'song__release_year',
    'added_at': 'added_at',
}


class TrackListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, playlist_id):
        sort  = request.query_params.get('sort', 'custom')
        order = request.query_params.get('order', 'asc')
        order_field = TRACK_SORT_MAP.get(sort, 'position')
        if order == 'desc':
            order_field = '-' + order_field

        tracks = (
            Track.objects.filter(playlist_id=playlist_id)
            .exclude(hidden_by__user_id=request.user.id)
            .select_related('song', 'song__artist', 'song__album')
            .order_by(order_field)
        )
        return Response(TrackSerializer(tracks, many=True).data)

    def post(self, request, playlist_id):
        song_id = request.data.get('song_id')
        if not song_id:
            return Response({'error': 'song_id required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            song = Song.objects.get(id=song_id)
        except Song.DoesNotExist:
            return Response({'error': 'Song not found'}, status=status.HTTP_404_NOT_FOUND)

        # Wrap add-track in a transaction with row locking to prevent race conditions.
        # select_for_update() locks the playlist row so two concurrent requests cannot
        # both pass the exists()/count() pre-checks and then collide on the DB constraint.
        # The outer IntegrityError catch handles any remaining race that slips through.
        try:
            with transaction.atomic():
                playlist = Playlist.objects.select_for_update().get(id=playlist_id)

                if playlist.owner_id != request.user.id:
                    return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

                if Track.objects.filter(playlist=playlist, song=song).exists():
                    return Response(
                        {'error': 'Song already in playlist'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                if playlist.max_songs > 0:
                    count = Track.objects.filter(playlist=playlist).count()
                    if count >= playlist.max_songs:
                        return Response(
                            {'error': 'playlist_song_limit_reached', 'max_songs': playlist.max_songs},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                last = Track.objects.filter(playlist=playlist).order_by('-position').first()
                position = (last.position + 1) if last else 0

                track = Track.objects.create(
                    playlist=playlist,
                    song=song,
                    added_by_id=request.user.id,
                    position=position,
                )
        except Playlist.DoesNotExist:
            return Response({'error': 'Playlist not found'}, status=status.HTTP_404_NOT_FOUND)
        except IntegrityError:
            # Race condition: two concurrent requests both passed the exists() check
            return Response({'error': 'Song already in playlist'}, status=status.HTTP_400_BAD_REQUEST)

        return Response(TrackSerializer(track).data, status=status.HTTP_201_CREATED)


class TrackDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, playlist_id, track_id):
        _, err = _require_playlist_owner(playlist_id, request.user.id)
        if err:
            return err
        try:
            track = Track.objects.get(id=track_id, playlist_id=playlist_id)
            track.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Track.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


class TrackReorderRemoveView(APIView):
    """
    PUT /<playlist_id>/reorder/  body: {"track_ids": [id, id, ...]}

    Reorder-remove: the client sends the final desired ordered list of track IDs.
    Any tracks currently in the playlist that are absent from track_ids are deleted.
    Remaining tracks are assigned positions 0, 1, 2, ... matching the sent order.
    This handles the case where the user removes tracks while reordering and clicks save.
    Both operations happen atomically.

    Available to: Owner and collaborators
    """
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, playlist_id):
        if 'track_ids' not in request.data:
            return Response({'error': 'track_ids required'}, status=status.HTTP_400_BAD_REQUEST)
        ordered_ids = request.data.get('track_ids')
        if not isinstance(ordered_ids, list):
            return Response({'error': 'track_ids must be a list'}, status=status.HTTP_400_BAD_REQUEST)
        if len(ordered_ids) != len(set(ordered_ids)):
            return Response({'error': 'track_ids must not contain duplicates'}, status=status.HTTP_400_BAD_REQUEST)

        # Check authorization (owner or collaborator)
        playlist, err = _can_edit_playlist(playlist_id, request.user.id)
        if err:
            return err

        try:
            with transaction.atomic():
                playlist = Playlist.objects.select_for_update().get(id=playlist_id)

                existing_ids = set(
                    Track.objects.filter(playlist=playlist).values_list('id', flat=True)
                )
                for track_id in ordered_ids:
                    if track_id not in existing_ids:
                        return Response(
                            {'error': f'Track {track_id} does not belong to this playlist'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                # Delete tracks not present in the new ordered list (reorder-remove)
                Track.objects.filter(playlist=playlist).exclude(id__in=ordered_ids).delete()
                # Reassign positions to match the submitted order
                for index, track_id in enumerate(ordered_ids):
                    Track.objects.filter(id=track_id, playlist=playlist).update(position=index)
        except Playlist.DoesNotExist:
            return Response({'error': 'Playlist not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({'status': 'reordered'})


class TrackRemoveView(APIView):
    """DELETE /<playlist_id>/remove/  body: {"track_ids": [1, 2, 3]}
    Removes specific tracks from a playlist without reordering remaining tracks."""
    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, playlist_id):
        _, err = _require_playlist_owner(playlist_id, request.user.id)
        if err:
            return err
        track_ids = request.data.get('track_ids', [])
        Track.objects.filter(playlist_id=playlist_id, id__in=track_ids).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlaylistArchiveView(APIView):
    """POST   /<playlist_id>/archive/  → archive playlist for requesting user
    DELETE /<playlist_id>/archive/  → unarchive playlist for requesting user"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        try:
            playlist = Playlist.objects.get(id=playlist_id)
        except Playlist.DoesNotExist:
            return Response({'error': 'Playlist not found'}, status=status.HTTP_404_NOT_FOUND)
        UserPlaylistArchive.objects.get_or_create(user_id=request.user.id, playlist=playlist)
        return Response({'status': 'archived'})

    def delete(self, request, playlist_id):
        UserPlaylistArchive.objects.filter(user_id=request.user.id, playlist_id=playlist_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TrackHideView(APIView):
    """POST   /<playlist_id>/<track_id>/hide/  → hide track for requesting user
    DELETE /<playlist_id>/<track_id>/hide/  → unhide track for requesting user"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id, track_id):
        try:
            track = Track.objects.get(id=track_id, playlist_id=playlist_id)
        except Track.DoesNotExist:
            return Response({'error': 'Track not found'}, status=status.HTTP_404_NOT_FOUND)
        UserTrackHide.objects.get_or_create(user_id=request.user.id, track=track)
        return Response({'status': 'hidden'})

    def delete(self, request, playlist_id, track_id):
        UserTrackHide.objects.filter(
            user_id=request.user.id,
            track_id=track_id,
            track__playlist_id=playlist_id,
        ).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return Response(
            {'status': 'healthy', 'service': 'track', 'database': 'connected'},
            status=200,
        )
    except Exception as e:
        return Response(
            {
                'status': 'unhealthy',
                'service': 'track',
                'database': 'disconnected',
                'error': str(e),
            },
            status=503,
        )


class TrackSortView(APIView):
    """
    PUT /<playlist_id>/sort/

    Sorts all tracks in a playlist by a specified field and persists the order.
    This updates the position field for all tracks based on the sort criteria.

    Available to: Owner and collaborators

    Request body:
    {
        "sort_by": "title|artist|album|genre|duration|year|added_at",
        "order": "asc|desc"
    }

    Response: List of tracks with updated positions
    """
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, playlist_id):
        sort_by = request.data.get('sort_by', 'custom')
        order = request.data.get('order', 'asc')

        if sort_by not in TRACK_SORT_MAP:
            return Response({
                'error': 'invalid_sort_field',
                'message': f'Sort field must be one of: {", ".join(TRACK_SORT_MAP.keys())}'
            }, status=status.HTTP_400_BAD_REQUEST)

        if order not in ['asc', 'desc']:
            return Response({
                'error': 'invalid_order',
                'message': 'Order must be asc or desc'
            }, status=status.HTTP_400_BAD_REQUEST)

        # Check authorization (owner or collaborator)
        playlist, err = _can_edit_playlist(playlist_id, request.user.id)
        if err:
            return err

        try:
            with transaction.atomic():
                # Get all tracks with related data
                tracks = Track.objects.filter(playlist=playlist).select_related(
                    'song', 'song__artist', 'song__album'
                )

                # Determine sort field
                order_field = TRACK_SORT_MAP[sort_by]
                if order == 'desc':
                    order_field = '-' + order_field

                # Sort tracks in Python (since we need to update positions)
                # For custom/position sort, we just use current order
                if sort_by == 'custom':
                    sorted_tracks = list(tracks.order_by('position'))
                else:
                    # Sort using Django's ordering, then convert to list
                    sorted_tracks = list(tracks.order_by(order_field))

                # Update positions to match new order
                track_updates = []
                for index, track in enumerate(sorted_tracks):
                    track.position = index
                    track_updates.append(track)

                # Bulk update positions
                Track.objects.bulk_update(track_updates, ['position'])

                return Response({
                    'message': f'Playlist sorted by {sort_by} ({order})',
                    'sort_by': sort_by,
                    'order': order,
                    'tracks_updated': len(sorted_tracks),
                    'tracks': TrackSerializer(sorted_tracks, many=True).data
                })

        except Exception as e:
            return Response({
                'error': 'sort_failed',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
