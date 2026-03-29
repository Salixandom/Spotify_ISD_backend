from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes

from utils.responses import (
    SuccessResponse,
    ErrorResponse,
    NotFoundResponse,
    ForbiddenResponse,
    ValidationErrorResponse,
    ServiceUnavailableResponse,
)
from django.db.models import Q
from django.db import connection

from .models import Artist, Album, Song
from .serializers import ArtistSerializer, AlbumSerializer, SongSerializer
from playlistapp.models import Playlist
from playlistapp.serializers import PlaylistSerializer

SONG_SORT_MAP = {
    'title':    'title',
    'artist':   'artist__name',
    'album':    'album__name',
    'genre':    'genre',
    'duration': 'duration_seconds',
    'year':     'release_year',
}


class SearchView(APIView):
    """Unified search across songs, playlists, artists, and albums."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '')

        songs = Song.objects.select_related('artist', 'album')
        playlists = Playlist.objects.filter(visibility='public')
        artists = Artist.objects.all()
        albums = Album.objects.select_related('artist')

        if query:
            songs = songs.filter(
                Q(title__icontains=query)
                | Q(artist__name__icontains=query)
                | Q(album__name__icontains=query)
            )
            playlists = playlists.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
            )
            artists = artists.filter(name__icontains=query)
            albums = albums.filter(
                Q(name__icontains=query)
                | Q(artist__name__icontains=query)
            )

        return SuccessResponse(
            data={
                'songs': SongSerializer(songs[:20], many=True).data,
                'playlists': PlaylistSerializer(playlists[:20], many=True).data,
                'artists': ArtistSerializer(artists[:20], many=True).data,
                'albums': AlbumSerializer(albums[:20], many=True).data,
            },
            message='Search completed successfully'
        )


class BrowseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        genres = (
            Song.objects.exclude(genre='')
            .values_list('genre', flat=True)
            .distinct()
            .order_by('genre')
        )
        return SuccessResponse(
            data=list(genres),
            message=f'Found {len(list(genres))} genres'
        )


class ArtistListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '')
        qs = Artist.objects.all()
        if query:
            qs = qs.filter(name__icontains=query)
        return SuccessResponse(
            data=ArtistSerializer(qs.order_by('name'), many=True).data,
            message=f'Found {qs.count()} artists'
        )


class ArtistDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, artist_id):
        try:
            artist = Artist.objects.get(id=artist_id)
        except Artist.DoesNotExist:
            return NotFoundResponse(message='Artist not found')
        return SuccessResponse(
            data=ArtistSerializer(artist).data,
            message='Artist retrieved successfully'
        )


class AlbumListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '')
        qs = Album.objects.select_related('artist')
        if query:
            qs = qs.filter(
                Q(name__icontains=query) | Q(artist__name__icontains=query)
            )
        return SuccessResponse(
            data=AlbumSerializer(qs.order_by('name'), many=True).data,
            message=f'Found {qs.count()} albums'
        )


class AlbumDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, album_id):
        try:
            album = Album.objects.select_related('artist').get(id=album_id)
        except Album.DoesNotExist:
            return NotFoundResponse(message='Album not found')
        return SuccessResponse(
            data=AlbumSerializer(album).data,
            message='Album retrieved successfully'
        )


class SongSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query = request.query_params.get('q', '')
        genre = request.query_params.get('genre', '')
        sort  = request.query_params.get('sort', '')
        order = request.query_params.get('order', 'asc')

        qs = Song.objects.select_related('artist', 'album')

        if query:
            qs = qs.filter(
                Q(title__icontains=query)
                | Q(artist__name__icontains=query)
                | Q(album__name__icontains=query)
            )

        if genre:
            qs = qs.filter(genre__iexact=genre)

        if sort in SONG_SORT_MAP:
            order_field = SONG_SORT_MAP[sort]
            if order == 'desc':
                order_field = '-' + order_field
            qs = qs.order_by(order_field)

        return SuccessResponse(
            data=SongSerializer(qs[:20], many=True).data,
            message=f'Found {min(qs.count(), 20)} songs'
        )


class PlaylistSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        query        = request.query_params.get('q', '')
        playlist_type = request.query_params.get('type', '')

        qs = Playlist.objects.filter(visibility='public')

        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
            )

        if playlist_type in ('solo', 'collaborative'):
            qs = qs.filter(playlist_type=playlist_type)

        return SuccessResponse(
            data=PlaylistSerializer(qs.order_by('name')[:20], many=True).data,
            message=f'Found {min(qs.count(), 20)} playlists'
        )



@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return SuccessResponse(
            data={'status': 'healthy', 'service': 'search', 'database': 'connected'},
            message='Service is healthy'
        )
    except Exception as e:
        return ServiceUnavailableResponse(
            message=f'Database connection failed: {str(e)}'
        )
