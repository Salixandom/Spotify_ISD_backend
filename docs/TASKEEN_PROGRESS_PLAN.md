# Taskeen's Progress Plan
# Spotify ISD Backend — Playlist App Comprehensive Enhancement
# Member: Taskeen Towfique (2105122)
# Scope: Playlist management (playlistapp) — All operations for playlists and tracks
# Last Updated: 2026-03-30

---

## 1. Purpose of This Document

This is the authoritative planning reference for all playlistapp enhancements,
including playlist CRUD operations, track management within playlists, social features,
and smart playlist generation. No code is written until this plan is reviewed and
agreed upon. Every future session will begin by reading this file.

---

## 2. Current State Analysis

### ✅ What Already Exists

**Playlist Models** (`playlistapp/models.py`):
- `Playlist` model: owner_id, name, description, visibility, playlist_type, cover_url, max_songs, timestamps
- `UserPlaylistArchive` model: Per-user archive feature (already implemented)

**Playlist Views** (`playlistapp/views.py`):
- `PlaylistViewSet`: Basic CRUD operations
- GET/POST `/api/playlists/` — List owner's playlists, create new
- GET/PATCH/DELETE `/api/playlists/{id}/` — Retrieve, update, delete
- Basic sorting: name, created_at, updated_at
- Archive filtering via `?include_archived=true`
- Owner authorization on update/delete

**Playlist Serializer** (`playlistapp/serializers.py`):
- `PlaylistSerializer`: All fields except owner_id (auto-set)
- Validation: Collaborative playlists must be private

**Track Operations** (Currently in `trackapp/views.py`):
- Add track to playlist
- Remove single track
- Bulk remove tracks
- Reorder tracks
- Hide/unhide tracks (per-user)
- Archive/unarchive playlist (per-user)

### ❌ What's Missing

**Enhanced Filtering:**
- No filtering by visibility (public/private)
- No filtering by playlist type (solo/collaborative)
- No search by name/description
- No filtering by song count or date ranges

**Statistics & Metadata:**
- No endpoint for playlist stats (track count, duration, genres)
- No cover image upload/management
- No playlist cover URL validation

**Social Features:**
- No follow/unfollow functionality
- No like/heart functionality
- No collaborator list endpoint (integration with collab service)

**Smart Features:**
- No duplicate playlist functionality
- No auto-generated playlists (based on history)
- No playlist suggestions/recommendations
- No smart shuffle

**Track Operations in Playlist Context:**
- Track operations exist in trackapp but not in playlistapp
- Need unified playlist + track management interface
- Need playlist-level track statistics

---

## 3. Architectural Decisions

### 3.1 Track Operations: Where Do They Live?

**Current State:**
- `trackapp` handles all track operations (add, remove, reorder, hide)
- `playlistapp` handles playlist CRUD only

**Decision: Keep track operations in `trackapp`**

Rationale:
1. **Separation of Concerns**: Tracks are junction entities linking playlists × songs
2. **Existing Investment**: trackapp already has comprehensive track operations with locking, validation
3. **Microservices Pattern**: Different app = different responsibility
4. **Avoid Duplication**: Don't reimplement track logic in playlistapp

**However**: playlistapp will have **proxy/helper endpoints** that call trackapp:
- `POST /api/playlists/{id}/add-track/` → Proxy to trackapp with playlist context
- `DELETE /api/playlists/{id}/tracks/{track_id}/` → Proxy to trackapp
- `PUT /api/playlists/{id}/reorder/` → Proxy to trackapp

This provides a cleaner API surface for frontend: "playlist-centric" URLs even though logic lives in trackapp.

### 3.2 Cross-App Communication

**Valid Cross-App Imports** (within core service):
```python
# In playlistapp/views.py - VALID
from trackapp.models import Track
from trackapp.serializers import TrackSerializer
from searchapp.models import Song
```

These are valid because all three apps (playlistapp, trackapp, searchapp) live in the same Django project (core service).

**Invalid Cross-Service Imports**:
```python
# WRONG - collaboration service is separate
from collabapp.models import Collaborator

# WRONG - auth service is separate
from django.contrib.auth.models import User
```

Use HTTP calls for cross-service communication.

---

## 4. Complete Enhancement List

### Phase 1: Enhanced Filtering & Discovery

#### 1.1 Advanced Filtering for Playlist List

**File**: `playlistapp/views.py` — Update `PlaylistViewSet.get_queryset()`

**New Query Parameters**:
- `?visibility=public|private` — Filter by visibility
- `?type=solo|collaborative` — Filter by playlist type
- `?q=search_term` — Search in name and description
- `?min_tracks=N` — Minimum track count
- `?max_tracks=N` — Maximum track count
- `?created_after=YYYY-MM-DD` — Filter by creation date
- `?created_before=YYYY-MM-DD` — Filter by creation date
- `?sort=name|created_at|updated_at|track_count` — Sort field (add track_count)
- `?order=asc|desc` — Sort order

**Implementation Notes**:
- Use `annotate()` to add track_count for filtering/sorting
- Chainable filters — only apply provided params
- Default: sort by `-updated_at`, exclude archived

#### 1.2 Playlist Statistics Endpoint

**File**: `playlistapp/views.py` — Add `PlaylistStatsView`

**Endpoint**: `GET /api/playlists/{id}/stats/`

**Response**:
```json
{
    "id": 1,
    "total_tracks": 25,
    "total_duration_seconds": 5432,
    "total_duration_formatted": "1:30:32",
    "genres": ["Pop", "Rock", "Jazz"],
    "unique_artists": 12,
    "unique_albums": 8,
    "last_track_added": "2026-03-29T12:00:00Z",
    "collaborator_count": 3,
    "is_followed": false,
    "is_liked": false,
    "owner_name": "taskeen",
    "cover_url": "..."
}
```

**Implementation**:
- Use `Track.objects.filter(playlist_id=playlist_id)` with aggregates
- Join with `searchapp_song` for genre/artists/albums
- Collab count: HTTP call to collaboration service OR proxy endpoint
- Follow/like status: Check `UserPlaylistFollow`, `UserPlaylistLike` models

#### 1.3 Featured Playlists

**File**: `playlistapp/views.py` — Add `FeaturedPlaylistsView`

**Endpoint**: `GET /api/playlists/featured/`

**Logic**:
- Return public playlists created by "system" or "admin" users
- Filter by high track count or specific tags
- Limit to 20 results
- Optional: `?genre=Pop` filter

**Implementation**:
- Add `is_featured` BooleanField to Playlist model (default False)
- Only visible in featured endpoint, not in main list
- Or: Use owner_id filtering for admin users

---

### Phase 2: Playlist Operations

#### 2.1 Duplicate Playlist

**File**: `playlistapp/views.py` — Add `DuplicatePlaylistView`

**Endpoint**: `POST /api/playlists/{id}/duplicate/`

**Request Body** (optional):
```json
{
    "name": "My Playlist (Copy)",
    "include_tracks": true,
    "reset_position": false
}
```

**Logic**:
1. Get source playlist
2. Create new playlist with copied metadata (name append "(Copy)")
3. If `include_tracks=true`: Copy all tracks to new playlist
4. Reset positions if `reset_position=true`
5. Return new playlist ID

**Implementation**:
```python
with transaction.atomic():
    source = Playlist.objects.get(id=playlist_id)
    new_playlist = Playlist.objects.create(
        owner_id=request.user.id,
        name=name or f"{source.name} (Copy)",
        description=source.description,
        visibility='private',  # Duplicates are always private
        playlist_type='solo',
        max_songs=source.max_songs,
        cover_url=source.cover_url
    )

    if include_tracks:
        tracks = Track.objects.filter(playlist=source).select_related('song')
        new_tracks = [
            Track(
                playlist=new_playlist,
                song=track.song,
                added_by_id=request.user.id,
                position=track.position if not reset_position else index
            )
            for index, track in enumerate(tracks)
        ]
        Track.objects.bulk_create(new_tracks)
```

#### 2.2 Batch Operations

**File**: `playlistapp/views.py` — Add `BatchDeleteView`, `BatchUpdateView`

**Endpoints**:
- `DELETE /api/playlists/batch-delete/`
- `PATCH /api/playlists/batch-update/`

**Batch Delete Request**:
```json
{
    "playlist_ids": [1, 2, 3]
}
```

**Batch Update Request**:
```json
{
    "playlist_ids": [1, 2],
    "updates": {
        "visibility": "private",
        "playlist_type": "collaborative"
    }
}
```

**Implementation**:
- Authorization check for each playlist
- Use `filter(id__in=playlist_ids, owner_id=request.user.id)`
- Return list of succeeded/failed IDs

#### 2.3 Cover Image Upload

**File**: `playlistapp/views.py` — Add `CoverUploadView`, `CoverDeleteView`

**Endpoints**:
- `POST /api/playlists/{id}/cover/`
- `DELETE /api/playlists/{id}/cover/`

**Implementation Options**:

**Option A: Direct File Upload to Django**
```python
# Store uploaded file in MEDIA_ROOT
# Serve via Django static files
# Simple but not production-scalable
```

**Option B: Upload to Supabase Storage (Recommended)**
```python
import os
from supabase import create_client, Client

def upload_cover_to_supabase(file, playlist_id):
    supabase: Client = create_client(
        os.environ.get('SUPABASE_URL'),
        os.environ.get('SUPABASE_KEY')
    )

    filename = f"playlist-covers/{playlist_id}/{file.name}"
    supabase.storage.from_('playlist-covers').upload(
        filename,
        file
    )

    public_url = supabase.storage.from_('playlist-covers').get_public_url(filename)
    return public_url
```

**Validation**:
- File type: image/jpeg, image/png, image/webp
- Max size: 5MB
- Optional: Image dimensions (recommendation: 300x300px)

---

### Phase 3: Social Features

#### 3.1 Follow/Unfollow Playlists

**File**: `playlistapp/models.py` — Add `UserPlaylistFollow` model

**Model**:
```python
class UserPlaylistFollow(models.Model):
    user_id      = models.IntegerField()
    playlist     = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='followed_by')
    followed_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_id', 'playlist')
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['playlist']),
        ]
```

**File**: `playlistapp/views.py` — Add `FollowView`, `FollowedPlaylistsView`

**Endpoints**:
- `POST /api/playlists/{id}/follow/` — Follow a playlist
- `DELETE /api/playlists/{id}/follow/` — Unfollow
- `GET /api/playlists/followed/` — List followed playlists

**Logic**:
- Use `get_or_create()` for follow (idempotent)
- Only public playlists can be followed
- Can't follow your own playlist
- Followed playlists appear in `GET /api/playlists/?include_followed=true`

**Integration with Main List**:
Update `PlaylistViewSet.get_queryset()`:
```python
# Default: exclude followed
if self.request.query_params.get('include_followed') != 'true':
    qs = qs.exclude(followed_by__user_id=self.request.user.id)

# New filter: only followed
if self.request.query_params.get('filter') == 'followed':
    qs = qs.filter(followed_by__user_id=self.request.user.id)
```

#### 3.2 Like/Heart Playlists

**File**: `playlistapp/models.py` — Add `UserPlaylistLike` model

**Model**:
```python
class UserPlaylistLike(models.Model):
    user_id    = models.IntegerField()
    playlist   = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name='liked_by')
    liked_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user_id', 'playlist')
        indexes = [
            models.Index(fields=['user_id']),
            models.Index(fields=['playlist']),
        ]
```

**File**: `playlistapp/views.py` — Add `LikeView`, `LikedPlaylistsView`

**Endpoints**:
- `POST /api/playlists/{id}/like/` — Like a playlist
- `DELETE /api/playlists/{id}/like/` — Unlike
- `GET /api/playlists/liked/` — List liked playlists

**Logic**:
- Similar to follow pattern
- Like count visible in playlist detail
- Public playlists only
- Can't like your own playlist

**Serializer Update**:
Add `likes_count` field to `PlaylistSerializer`:
```python
class PlaylistSerializer(serializers.ModelSerializer):
    likes_count = serializers.SerializerMethodField()

    class Meta:
        model = Playlist
        fields = [..., 'likes_count']

    def get_likes_count(self, obj):
        return obj.liked_by.count()
```

#### 3.3 Collaborator Integration (Proxy Endpoint)

**File**: `playlistapp/views.py` — Add `CollaboratorsView`

**Endpoint**: `GET /api/playlists/{id}/collaborators/`

**Logic**: Proxy to collaboration service
```python
import requests

COLLAB_SERVICE_URL = os.environ.get('COLLAB_SERVICE_URL', 'http://collaboration:8003')

def get_collaborators(request, playlist_id):
    response = requests.get(
        f'{COLLAB_SERVICE_URL}/api/collab/{playlist_id}/members/',
        headers={'Authorization': request.headers.get('Authorization')}
    )
    return Response(response.json(), status=response.status_code)
```

**Response**:
```json
[
    {
        "id": 1,
        "user_id": 5,
        "username": "mesbah",
        "joined_at": "2026-03-29T10:00:00Z"
    }
]
```

---

### Phase 4: Smart Features

#### 4.1 Auto-Generate Playlists

**File**: `playlistapp/views.py` — Add `GeneratePlaylistView`

**Endpoint**: `POST /api/playlists/generate/`

**Request Body**:
```json
{
    "type": "top_songs",
    "name": "My Top Songs",
    "params": {
        "days": 30,
        "limit": 50
    }
}
```

**Supported Types**:
- `top_songs`: Most played songs in last N days
- `recent`: Recently played songs (distinct)
- `genre_mix`: Songs from specific genre
- `artist_mix`: Songs from specific artist
- `decade`: Songs from specific decade (by release_year)

**Implementation**:
```python
# For top_songs
from historyapp.models import Play
from django.db.models import Count

def generate_top_songs(user_id, days=30, limit=50):
    cutoff = timezone.now() - timedelta(days=days)

    # Count plays per song
    song_counts = (
        Play.objects.filter(
            user_id=user_id,
            played_at__gte=cutoff
        )
        .values('song_id')
        .annotate(play_count=Count('id'))
        .order_by('-play_count')[:limit]
    )

    # Get song objects
    song_ids = [s['song_id'] for s in song_counts]
    songs = Song.objects.filter(id__in=song_ids)

    # Create playlist
    playlist = Playlist.objects.create(
        owner_id=user_id,
        name=name,
        description=f"Top {limit} songs from last {days} days",
        playlist_type='solo',
        visibility='private'
    )

    # Add tracks
    tracks = [
        Track(
            playlist=playlist,
            song=song,
            added_by_id=user_id,
            position=index
        )
        for index, song in enumerate(songs)
    ]
    Track.objects.bulk_create(tracks)

    return playlist
```

#### 4.2 Playlist Suggestions

**File**: `playlistapp/views.py` — Add `SuggestedPlaylistsView`

**Endpoint**: `GET /api/playlists/suggested/`

**Logic**:
- Based on user's listening history (from historyapp)
- Based on user's liked playlists
- Based on followed playlists' genres
- Return public playlists matching criteria

**Implementation**:
```python
# Get user's top genres from history
user_genres = (
    Play.objects.filter(user_id=request.user.id)
    .values('song__genre')
    .annotate(count=Count('id'))
    .order_by('-count')[:5]
    .values_list('song__genre', flat=True)
)

# Suggest playlists with matching songs
suggested = (
    Playlist.objects.filter(visibility='public')
    .filter(
        tracks__song__genre__in=user_genres
    )
    .distinct()
    .annotate(match_count=Count('tracks__song__genre'))
    .order_by('-match_count')[:20]
)
```

#### 4.3 Smart Shuffle

**File**: `playlistapp/views.py` — Add `ShuffleView`

**Endpoint**: `POST /api/playlists/{id}/shuffle/`

**Request Body** (optional):
```json
{
    "type": "random",  // or "genre_based", "tempo_based"
    "group_by": "genre"  // for genre_based
}
```

**Logic**:
- **Random**: Pure random reorder
- **Genre-Based**: Group songs by genre, shuffle within groups
- **Artist-Based**: Avoid same artist consecutively

**Implementation**:
```python
import random

def random_shuffle(playlist_id):
    tracks = list(Track.objects.filter(playlist_id=playlist_id))
    random.shuffle(tracks)

    for index, track in enumerate(tracks):
        track.position = index
        track.save()

    return Response({'status': 'shuffled', 'type': 'random'})

def genre_based_shuffle(playlist_id):
    tracks = list(
        Track.objects.filter(playlist_id=playlist_id)
        .select_related('song__artist', 'song__album')
    )

    # Group by genre
    genre_groups = {}
    for track in tracks:
        genre = track.song.genre or 'Unknown'
        if genre not in genre_groups:
            genre_groups[genre] = []
        genre_groups[genre].append(track)

    # Shuffle within each group
    for genre in genre_groups:
        random.shuffle(genre_groups[genre])

    # Flatten and assign positions
    shuffled = []
    for group in genre_groups.values():
        shuffled.extend(group)

    for index, track in enumerate(shuffled):
        track.position = index
        track.save()
```

---

### Phase 5: Validation & Quality

#### 5.1 Enhanced Playlist Validation

**File**: `playlistapp/serializers.py` — Update `PlaylistSerializer.validate()`

**New Validations**:
```python
def validate(self, data):
    # Existing: collaborative must be private
    playlist_type = data.get('playlist_type', getattr(self.instance, 'playlist_type', 'solo'))
    visibility = data.get('visibility', getattr(self.instance, 'visibility', 'public'))

    if playlist_type == 'collaborative' and visibility != 'private':
        raise serializers.ValidationError({
            'visibility': 'Collaborative playlists must be private.'
        })

    # New: Name length
    name = data.get('name', getattr(self.instance, 'name', ''))
    if len(name) < 3:
        raise serializers.ValidationError({
            'name': 'Playlist name must be at least 3 characters.'
        })
    if len(name) > 100:
        raise serializers.ValidationError({
            'name': 'Playlist name must not exceed 100 characters.'
        })

    # New: Description length
    description = data.get('description', getattr(self.instance, 'description', ''))
    if len(description) > 1000:
        raise serializers.ValidationError({
            'description': 'Description must not exceed 1000 characters.'
        })

    # New: Cover URL format (if provided)
    cover_url = data.get('cover_url', getattr(self.instance, 'cover_url', ''))
    if cover_url and not cover_url.startswith(('http://', 'https://')):
        raise serializers.ValidationError({
            'cover_url': 'Cover URL must be a valid HTTP(S) URL.'
        })

    # New: max_songs validation
    max_songs = data.get('max_songs', getattr(self.instance, 'max_songs', 0))
    if max_songs < 0:
        raise serializers.ValidationError({
            'max_songs': 'max_songs cannot be negative.'
        })
    if max_songs > 10000:
        raise serializers.ValidationError({
            'max_songs': 'max_songs cannot exceed 10000.'
        })

    return data
```

#### 5.2 Consistent Error Responses

**File**: `playlistapp/views.py` — Use consistent error format

**Error Response Format**:
```json
{
    "error": "error_code",
    "message": "Human-readable message",
    "details": {...}  // Optional additional context
}
```

**Error Codes**:
- `playlist_not_found` — 404
- `forbidden` — 403
- `invalid_input` — 400
- `duplicate_name` — 409
- `max_songs_exceeded` — 400
- `not_authorized` — 403

#### 5.3 Performance Optimizations

**Indexes to Add**:
```python
# In Playlist.Meta.indexes
models.Index(fields=['owner_id', 'visibility']),  # For user's public playlists
models.Index(fields=['visibility', 'playlist_type']),  # For discovery
models.Index(fields=['owner_id', 'updated_at']),  # For user's playlists sorted
```

**Query Optimization**:
```python
# Use select_related for FKs
Playlist.objects.select_related()

# Use prefetch_related for reverse FKs
Playlist.objects.prefetch_related('tracks__song__artist')

# Use only() to fetch specific fields
Playlist.objects.only('id', 'name', 'cover_url')

# Use annotate for aggregates
Playlist.objects.annotate(track_count=Count('tracks'))
```

**Pagination**:
```python
# For large lists (featured, suggested, etc.)
from rest_framework.pagination import PageNumberPagination

class PlaylistPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
```

---

### Phase 6: Integration & Documentation

#### 6.1 Track Operations Integration (Proxy Endpoints)

**File**: `playlistapp/urls.py` — Add track-related routes

**Routes**:
```python
# Track operations (proxy to trackapp or direct cross-app calls)
path('<int:playlist_id>/add-track/', AddTrackProxyView.as_view()),
path('<int:playlist_id>/tracks/<int:track_id>/', RemoveTrackProxyView.as_view()),
path('<int:playlist_id>/tracks/batch-delete/', BatchRemoveTracksProxyView.as_view()),
path('<int:playlist_id>/reorder/', ReorderTracksProxyView.as_view()),
path('<int:playlist_id>/shuffle/', ShuffleView.as_view()),  # From Phase 4
```

**File**: `playlistapp/views.py` — Add proxy view classes

**Example Proxy View**:
```python
class AddTrackProxyView(APIView):
    """
    Proxy to trackapp's TrackListView.post()
    Provides playlist-centric API: POST /api/playlists/{id}/add-track/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, playlist_id):
        # Option A: Direct cross-app call (same Django project)
        from trackapp.views import TrackListView
        from trackapp.models import Track
        from trackapp.serializers import TrackSerializer

        # Mimic trackapp logic
        song_id = request.data.get('song_id')
        # ... (trackapp add logic here)

        # Option B: HTTP call to trackapp service
        # TRACK_SERVICE_URL = os.environ.get('TRACK_SERVICE_URL', 'http://core:8002')
        # response = requests.post(
        #     f'{TRACK_SERVICE_URL}/api/tracks/{playlist_id}/',
        #     json=request.data,
        #     headers={'Authorization': request.headers.get('Authorization')}
        # )
        # return Response(response.json(), status=response.status_code)
```

**Decision**: Use direct cross-app calls (Option A) because trackapp and playlistapp share the same Django project (core service). No HTTP overhead needed.

#### 6.2 Integration Tests

**File**: `docs/PLAYLIST_TESTING.md` — Create testing guide

**Test Cases**:
```bash
# Phase 1: Filtering
GET /api/playlists/?visibility=public&type=collaborative
GET /api/playlists/?q=chill&min_tracks=10
GET /api/playlists/{id}/stats/

# Phase 2: Operations
POST /api/playlists/{id}/duplicate/
POST /api/playlists/{id}/cover/  # with multipart file
DELETE /api/playlists/batch-delete/  # {"playlist_ids": [1,2]}

# Phase 3: Social
POST /api/playlists/{id}/follow/
GET /api/playlists/followed/
POST /api/playlists/{id}/like/
GET /api/playlists/liked/

# Phase 4: Smart
POST /api/playlists/generate/  # {"type": "top_songs", "params": {"days": 30}}
GET /api/playlists/suggested/
POST /api/playlists/{id}/shuffle/

# Phase 5: Validation
POST /api/playlists/  # {"name": "AB"}  # Should fail - too short
POST /api/playlists/  # {"max_songs": -1}  # Should fail - negative
```

#### 6.3 Documentation Updates

**Files to Update**:
- `docs/SCHEMA.md` — Add new models (UserPlaylistFollow, UserPlaylistLike)
- `docs/AGENT-GUIDE.md` — Add playlistapp command examples
- `docs/API.md` — Complete API endpoint reference (create if not exists)
- `README.md` — Update features list

---

## 5. Implementation Order (By Phase)

### Commit 1: Phase 1 — Filtering & Stats
**Scope**: Foundation for enhanced playlist discovery

**Files to Modify**:
- `playlistapp/views.py` — Update PlaylistViewSet.get_queryset(), add PlaylistStatsView, FeaturedPlaylistsView
- `playlistapp/urls.py` — Register stats/, featured/ routes
- `playlistapp/serializers.py` — Add PlaylistStatsSerializer
- `services/core/core/settings.py` — No changes needed (already has playlistapp)

**Migration**: None (no model changes yet)

**Tests**:
- Filter by visibility, type, search query
- Stats endpoint returns correct counts
- Featured playlists endpoint works

---

### Commit 2: Phase 2 — Core Operations
**Scope**: Playlist duplication, batch ops, cover upload

**Files to Modify**:
- `playlistapp/models.py` — No model changes (cover is just URL field)
- `playlistapp/views.py` — Add DuplicatePlaylistView, BatchDeleteView, BatchUpdateView, CoverUploadView, CoverDeleteView
- `playlistapp/urls.py` — Register duplicate/, batch-delete/, batch-update/, cover/ routes
- `services/core/core/settings.py` — Add `pillow` to INSTALLED_APPS if doing image processing
- `services/core/pyproject.toml` — Add `Pillow` dependency

**Migration**: None (cover URL already exists)

**Tests**:
- Duplicate playlist has all tracks
- Batch delete only deletes user's own playlists
- Cover upload returns public URL

---

### Commit 3: Phase 3 — Social Features
**Scope**: Follow, like, collaborator integration

**Files to Modify**:
- `playlistapp/models.py` — Add UserPlaylistFollow, UserPlaylistLike models
- `playlistapp/views.py` — Add FollowView, FollowedPlaylistsView, LikeView, LikedPlaylistsView, CollaboratorsView
- `playlistapp/serializers.py` — Add likes_count to PlaylistSerializer
- `playlistapp/urls.py` — Register follow/, like/, collaborators/ routes
- `services/core/searchapp/views.py` — Update SearchView to exclude followed/liked if needed

**Migration**:
```bash
docker-compose exec core uv run python manage.py makemigrations playlistapp
docker-compose exec core uv run python manage.py migrate
```

**Tests**:
- Follow/unfollow toggles correctly
- Like count increments/decrements
- Can't follow own playlist
- Collaborators endpoint returns data

---

### Commit 4: Phase 4 — Smart Features
**Scope**: Auto-generate, suggestions, smart shuffle

**Files to Modify**:
- `playlistapp/views.py` — Add GeneratePlaylistView, SuggestedPlaylistsView, ShuffleView
- `playlistapp/urls.py` — Register generate/, suggested/, shuffle/ routes
- `playlistapp/serializers.py` — Add GeneratePlaylistSerializer

**Migration**: None (no new models)

**Tests**:
- Top songs generation works
- Genre-based shuffle groups correctly
- Suggestions return relevant playlists

---

### Commit 5: Phase 5 — Validation & Quality
**Scope**: Enhanced validation, error handling, performance

**Files to Modify**:
- `playlistapp/serializers.py` — Enhanced validate() method
- `playlistapp/views.py` — Consistent error responses, pagination
- `playlistapp/models.py` — Add Meta indexes
- `services/core/core/settings.py` — Add REST framework pagination settings

**Migration**:
```bash
docker-compose exec core uv run python manage.py makemigrations playlistapp
docker-compose exec core uv run python manage.py migrate
```

**Tests**:
- Validation catches all edge cases
- Error responses are consistent
- Pagination works for large lists

---

### Commit 6: Phase 6 — Integration & Documentation
**Scope**: Track proxy endpoints, testing guide, docs

**Files to Modify**:
- `playlistapp/views.py` — Add proxy views for track operations
- `playlistapp/urls.py` — Register track proxy routes
- `docs/PLAYLIST_TESTING.md` — CREATE: Comprehensive testing guide
- `docs/SCHEMA.md` — UPDATE: Add new models, update schema
- `docs/AGENT-GUIDE.md` — UPDATE: Add playlistapp examples
- `docs/API.md` — CREATE: Complete API reference

**Migration**: None (docs only)

**Tests**:
- All proxy endpoints work correctly
- Documentation is complete
- API reference matches implementation

---

## 6. File-by-File Change Summary

| File | Commit | Change Type |
|------|--------|-------------|
| `playlistapp/models.py` | 3, 5 | MODIFY (add follow/like models in commit 3; add indexes in commit 5) |
| `playlistapp/serializers.py` | 1, 3, 5 | MODIFY (stats serializer in commit 1; likes_count in commit 3; validation in commit 5) |
| `playlistapp/views.py` | ALL | OVERWRITE (complete rewrite with all new views) |
| `playlistapp/urls.py` | ALL | MODIFY (add all new routes across commits) |
| `services/core/core/settings.py` | 2, 5 | MODIFY (add pillow in commit 2; pagination in commit 5) |
| `services/core/pyproject.toml` | 2 | MODIFY (add Pillow dependency) |
| `docs/PLAYLIST_TESTING.md` | 6 | CREATE (testing guide) |
| `docs/API.md` | 6 | CREATE (API reference) |
| `docs/SCHEMA.md` | 6 | MODIFY (add follow/like models) |
| `docs/AGENT-GUIDE.md` | 6 | MODIFY (add playlistapp examples) |
| `playlistapp/migrations/0002_add_follow_like.py` | 3 | CREATE (generated + manual adjustments) |
| `playlistapp/migrations/0003_add_indexes.py` | 5 | CREATE (generated) |

---

## 7. Database Migrations

### Commit 3 — Social Models
**Migration File**: `playlistapp/migrations/0002_add_social_features.py`

**Operations**:
1. Create `UserPlaylistFollow` model
2. Create `UserPlaylistLike` model
3. Add indexes for performance

**Manual Migration (if needed)**:
```python
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('playlistapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserPlaylistFollow',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('user_id', models.IntegerField()),
                ('followed_at', models.DateTimeField(auto_now_add=True)),
                ('playlist', models.ForeignKey(
                    on_delete=models.CASCADE,
                    related_name='followed_by',
                    to='playlistapp.playlist'
                )),
            ],
            options={
                'unique_together': {('user_id', 'playlist')},
            },
        ),
        migrations.CreateModel(
            name='UserPlaylistLike',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('user_id', models.IntegerField()),
                ('liked_at', models.DateTimeField(auto_now_add=True)),
                ('playlist', models.ForeignKey(
                    on_delete=models.CASCADE,
                    related_name='liked_by',
                    to='playlistapp.playlist'
                )),
            ],
            options={
                'unique_together': {('user_id', 'playlist')},
            },
        ),
    ]
```

---

## 8. Open Questions & Decisions Needed

### Q1: Cover Image Upload — Which Approach?

**Options**:
1. **Direct to Supabase Storage** (Recommended)
   - Pros: Scalable, CDN-backed, production-ready
   - Cons: Requires Supabase configuration, dependency

2. **Django MEDIA_ROOT**
   - Pros: Simple, no external dependency
   - Cons: Not scalable, serves from Django (slow), needs nginx/media server

3. **External Service (Cloudinary, AWS S3)**
   - Pros: Highly scalable, transformations
   - Cons: External dependency, cost

**Decision**: **Option 1 (Supabase)** if already using Supabase for songs. Otherwise **Option 2** for development, migrate to Option 1 later.

### Q2: Track Operations — Proxy or Direct?

**Options**:
1. **Proxy endpoints in playlistapp** (Recommended)
   - URL pattern: `/api/playlists/{id}/add-track/`
   - Calls trackapp logic directly (same Django project)
   - Pros: Clean API, playlist-centric URLs, no HTTP overhead

2. **Keep in trackapp only**
   - URL pattern: `/api/tracks/{id}/` (current state)
   - Pros: Separation of concerns, no duplication
   - Cons: Less intuitive for frontend

**Decision**: **Option 1** — Add proxy endpoints in playlistapp that call trackapp functions. Best of both worlds.

### Q3: Featured Playlists — How to Mark?

**Options**:
1. **Add `is_featured` BooleanField to Playlist**
   - Pros: Simple query, explicit
   - Cons: Extra field, migration needed

2. **Filter by owner_id (admin users)**
   - Pros: No model change, uses existing data
   - Cons: Need to define "admin users", less explicit

3. **Tag system (add `tags` field)**
   - Pros: Flexible, can have multiple tags
   - Cons: More complex, requires tag model

**Decision**: **Option 1** (is_featured) for simplicity. Can evolve to Option 3 (tags) later if needed.

### Q4: Auto-Generated Playlists — When to Regenerate?

**Options**:
1. **Manual regeneration only**
   - User calls `/generate/` endpoint explicitly
   - Pros: Simple, predictable, no background jobs
   - Cons: Stale data

2. **Scheduled regeneration**
   - Background task regenerates daily/weekly
   - Pros: Always fresh
   - Cons: Requires Celery/worker, complexity

3. **Hybrid: Manual + "regenerate" button**
   - Initial manual generation
   - "Regenerate" endpoint updates existing auto-generated playlist
   - Pros: Balance of simplicity and freshness
   - Cons: Still can get stale

**Decision**: **Option 3** (Hybrid). Manual generation with regenerate endpoint. No scheduled jobs for now (can add in Phase 7).

---

## 9. Session Workflow

### Before Each Session:
1. Read this file (TASKEEN_PROGRESS_PLAN.md)
2. Read the latest session doc: `ls -lt docs/SESSION-*.md | head -3`
3. Identify which commit/phase you're working on
4. Read existing playlistapp files BEFORE editing

### During Session:
1. Make changes following the plan exactly
2. Test each endpoint manually
3. Document any deviations from the plan

### After Each Session:
1. Update session doc: `docs/SESSION-YYYY-MM-DD.md`
2. List files changed
3. Note any deviations or issues
4. Ask user to commit (NEVER run git yourself)

---

## 10. Testing Checklist

### Phase 1 Tests
- [ ] Filter by visibility=public returns only public playlists
- [ ] Filter by type=collaborative returns only collaborative
- [ ] Search query filters by name/description
- [ ] Stats endpoint returns accurate track count
- [ ] Stats endpoint returns duration correctly
- [ ] Featured playlists endpoint works

### Phase 2 Tests
- [ ] Duplicate playlist has all original tracks
- [ ] Duplicate playlist name has "(Copy)" suffix
- [ ] Batch delete removes multiple playlists
- [ ] Batch update modifies metadata correctly
- [ ] Cover upload returns valid URL
- [ ] Cover deletion clears cover_url field

### Phase 3 Tests
- [ ] Follow/unfollow toggles state
- [ ] Followed playlists excluded from main list
- [ ] Can't follow own playlist
- [ ] Like count increments correctly
- [ ] Can't like own playlist
- [ ] Collaborators endpoint returns data

### Phase 4 Tests
- [ ] Top songs generation creates correct playlist
- [ ] Recent songs generation works
- [ ] Genre-based shuffle groups songs
- [ ] Random shuffle reorders all tracks
- [ ] Suggestions return relevant playlists

### Phase 5 Tests
- [ ] Name < 3 chars returns validation error
- [ ] Description > 1000 chars returns validation error
- [ ] Negative max_songs returns validation error
- [ ] Error responses have consistent format
- [ ] Pagination works for large lists

---

## 11. API Endpoint Reference (Complete)

### Existing Endpoints
```
GET    /api/playlists/                          List owner's playlists
POST   /api/playlists/                          Create new playlist
GET    /api/playlists/{id}/                     Get playlist detail
PATCH  /api/playlists/{id}/                     Update playlist
DELETE /api/playlists/{id}/                     Delete playlist
GET    /api/playlists/health/                    Health check
```

### Phase 1 Endpoints
```
GET    /api/playlists/{id}/stats/               Playlist statistics
GET    /api/playlists/featured/                  Featured playlists
```

### Phase 2 Endpoints
```
POST   /api/playlists/{id}/duplicate/           Duplicate playlist
DELETE /api/playlists/batch-delete/              Batch delete playlists
PATCH  /api/playlists/batch-update/              Batch update playlists
POST   /api/playlists/{id}/cover/                Upload cover image
DELETE /api/playlists/{id}/cover/                Remove cover image
```

### Phase 3 Endpoints
```
POST   /api/playlists/{id}/follow/               Follow playlist
DELETE /api/playlists/{id}/follow/               Unfollow playlist
GET    /api/playlists/followed/                  List followed playlists
POST   /api/playlists/{id}/like/                 Like playlist
DELETE /api/playlists/{id}/like/                 Unlike playlist
GET    /api/playlists/liked/                     List liked playlists
GET    /api/playlists/{id}/collaborators/       List collaborators
```

### Phase 4 Endpoints
```
POST   /api/playlists/generate/                  Auto-generate playlist
GET    /api/playlists/suggested/                 Suggested playlists
POST   /api/playlists/{id}/shuffle/              Shuffle tracks
```

### Track Proxy Endpoints (Alternative URLs)
```
POST   /api/playlists/{id}/add-track/            Add song to playlist
DELETE /api/playlists/{id}/tracks/{track_id}/    Remove track
DELETE /api/playlists/{id}/remove/                Bulk remove tracks
PUT    /api/playlists/{id}/reorder/               Reorder tracks
POST   /api/playlists/{id}/tracks/{track_id}/hide/   Hide track
DELETE /api/playlists/{id}/tracks/{track_id}/hide/   Unhide track
POST   /api/playlists/{id}/archive/               Archive playlist
DELETE /api/playlists/{id}/archive/               Unarchive playlist
```

---

## 12. Out of Scope

The following items are NOT part of this plan:
- Real-time playlist collaboration (WebSocket)
- Playlist versioning/history
- Playlist export (shareable file format)
- Spotify sync (import from real Spotify)
- Advanced recommendation algorithms
- Background/scheduled tasks (Celery)
- Email notifications for playlist changes
- Playlist analytics (plays, skips, etc.)

---

## 13. Success Criteria

### Phase 1 Complete When:
- All filters work correctly
- Stats endpoint returns accurate data
- Featured playlists endpoint works

### Phase 2 Complete When:
- Can duplicate playlist with all tracks
- Batch operations work efficiently
- Cover image uploads to Supabase successfully

### Phase 3 Complete When:
- Follow/unfollow works as expected
- Like counts update correctly
- Collaborators integration works

### Phase 4 Complete When:
- Auto-generated playlists create successfully
- Suggestions return relevant results
- Shuffle reorders tracks correctly

### Phase 5 Complete When:
- All validations enforce business rules
- Error responses are consistent
- Performance is acceptable (< 200ms for most queries)

### Phase 6 Complete When:
- All proxy endpoints work
- Documentation is complete
- Tests are documented

---

**Last Updated**: 2026-03-30
**Status**: Planning Complete — Ready to Begin Implementation
**Next Step**: Start with Commit 1 (Phase 1 — Filtering & Stats)

---

## Appendix A: Query Parameter Reference

### Playlist List Filters
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `visibility` | string | — | Filter: `public` or `private` |
| `type` | string | — | Filter: `solo` or `collaborative` |
| `q` | string | — | Search in name and description |
| `min_tracks` | int | — | Minimum track count |
| `max_tracks` | int | — | Maximum track count |
| `created_after` | date | — | ISO date string (YYYY-MM-DD) |
| `created_before` | date | — | ISO date string (YYYY-MM-DD) |
| `sort` | string | `updated_at` | Sort field: `name`, `created_at`, `updated_at`, `track_count` |
| `order` | string | `desc` | Sort order: `asc` or `desc` |
| `include_archived` | bool | `false` | Include archived playlists |
| `include_followed` | bool | `false` | Include followed playlists |
| `filter` | string | — | Special filter: `followed`, `liked` |

### Examples
```
GET /api/playlists/?visibility=public&type=collaborative
GET /api/playlists/?q=chill&min_tracks=10&sort=name&order=asc
GET /api/playlists/?created_after=2026-03-01&sort=created_at&order=desc
GET /api/playlists/?filter=followed
```

---

## Appendix B: Error Response Format

All errors follow this consistent format:

```json
{
    "error": "error_code",
    "message": "Human-readable description",
    "details": {
        "field": "Additional context"
    }
}
```

**Error Codes**:
- `playlist_not_found` — Playlist doesn't exist (404)
- `forbidden` — User not authorized (403)
- `invalid_input` — Invalid request data (400)
- `duplicate_name` — Playlist name already exists (409)
- `max_songs_exceeded` — Song limit reached (400)
- `not_authorized` — Authorization failed (403)
- `invalid_image` — Cover image invalid (400)
- `invalid_file_type` — Wrong file type (400)
- `file_too_large` — Image exceeds max size (400)
- `validation_error` — Validation failed (400)
- `not_found` — Resource not found (404)
