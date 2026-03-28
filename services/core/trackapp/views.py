from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from django.db import connection, transaction, IntegrityError
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
    """
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, playlist_id):
        _, err = _require_playlist_owner(playlist_id, request.user.id)
        if err:
            return err
        ordered_ids = request.data.get('track_ids', [])
        with transaction.atomic():
            # Delete tracks not present in the new ordered list (reorder-remove)
            Track.objects.filter(playlist_id=playlist_id).exclude(id__in=ordered_ids).delete()
            # Reassign positions to match the submitted order
            for index, track_id in enumerate(ordered_ids):
                Track.objects.filter(id=track_id, playlist_id=playlist_id).update(position=index)
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
