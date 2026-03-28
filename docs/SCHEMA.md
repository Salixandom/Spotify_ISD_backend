# SCHEMA.md
# Spotify ISD Backend — Final Database Schema
# CSE 326 — Information System Design, Group 3
# Version: Final (post-modifications)
# Last Updated: 2026-03-26

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Traefik Gateway :80                           │
├──────────────┬────────────────────────────┬─────────────────────────┤
│ Auth Service │       Core Service         │  Collaboration Service  │
│    :8001     │          :8002             │         :8003           │
│              │                            │                         │
│  auth_user   │  searchapp_artist          │ collabapp_collaborator  │
│  (built-in)  │  searchapp_album           │ collabapp_invitelink    │
│              │  searchapp_song            │ shareapp_sharelink      │
│              │  playlistapp_playlist      │                         │
│              │  trackapp_track            │                         │
│              │  historyapp_play           │                         │
└──────────────┴────────────────────────────┴─────────────────────────┘
                              │
                   ┌──────────────────┐
                   │   PostgreSQL     │
                   │   spotifydb      │
                   └──────────────────┘
```

All three services connect to the same PostgreSQL database. Cross-service
references use plain integers (no FK constraints at the ORM level) because
each Django application only manages the models it declares itself.
Referential correctness is enforced by JWT authentication at the application
layer.

---

## Storage Architecture

```
Supabase Storage Bucket: "songs"  (public read)
├── SoundHelix-Song-1.mp3
├── SoundHelix-Song-2.mp3
│   ...
└── SoundHelix-Song-8.mp3

Song.audio_url    = full Supabase public URL  (used by <audio> element)
Song.storage_path = filename only             (used by seed/management command)
Artist.image_url  = picsum.photos URL         (seeded)
Album.cover_url   = picsum.photos URL         (seeded)
```

---

## Naming Conventions

Two entities are easily confused. This distinction is FINAL and applies to
every model, serializer, view, URL, variable name, and comment.

| Term  | Model | App        | DB Table           | Meaning                                              |
|-------|-------|------------|--------------------|------------------------------------------------------|
| Song  | Song  | searchapp  | searchapp_song     | A catalog entry in the global music library          |
| Track | Track | trackapp   | trackapp_track     | A Song that has been inserted into a specific Playlist |

- **Song**: exists independently. Can be searched, browsed, played from history.
- **Track**: the junction record linking one Song to one Playlist, carrying
  position, who added it, and when. The model class is `Track` and the
  table is `trackapp_track`. Never rename to PlaylistTrack.

---

## Tables

---

### Table 1: auth_user

**Service:** Auth | **Django:** Built-in. Do NOT redefine.

```sql
-- Managed entirely by Django's django.contrib.auth migrations.
-- Do not create, alter, or drop this table manually.
CREATE TABLE auth_user (
    id           BIGSERIAL    PRIMARY KEY,
    username     VARCHAR(150) NOT NULL UNIQUE,
    password     VARCHAR(128) NOT NULL,
    email        VARCHAR(254) NOT NULL DEFAULT '',
    first_name   VARCHAR(150) NOT NULL DEFAULT '',
    last_name    VARCHAR(150) NOT NULL DEFAULT '',
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    is_staff     BOOLEAN      NOT NULL DEFAULT FALSE,
    is_superuser BOOLEAN      NOT NULL DEFAULT FALSE,
    date_joined  TIMESTAMP    NOT NULL DEFAULT NOW(),
    last_login   TIMESTAMP    NULL
);
```

**Django Model:**
```python
# services/auth/authapp/models.py
# File intentionally contains only the import — no custom model defined.
from django.db import models

# The User model used throughout this project is:
from django.contrib.auth.models import User
# AUTH_USER_MODEL is NOT overridden in settings.py.
# Django defaults to 'auth.User'.
```

**Serializers (services/auth/authapp/serializers.py):**
```python
from django.contrib.auth.models import User
from rest_framework import serializers

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model  = User
        fields = ['id', 'username', 'password']

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'username']
```

**API Response:**
```json
{ "id": 1, "username": "sakib" }
```

**Registration requires only:** `username`, `password`

---

### Table 2: searchapp_artist

**Service:** Core (searchapp app)  
**Purpose:** Artist profiles. Songs belong to artists.
`monthly_listeners` is seeded with realistic numbers. In production it would
be aggregated from `historyapp_play`.

```sql
CREATE TABLE searchapp_artist (
    id                BIGSERIAL    PRIMARY KEY,
    name              VARCHAR(255) NOT NULL UNIQUE,
    image_url         VARCHAR(500) NOT NULL DEFAULT '',
    bio               TEXT         NOT NULL DEFAULT '',
    monthly_listeners INTEGER      NOT NULL DEFAULT 0,
    created_at        TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_artist_name ON searchapp_artist (name);
```

**Django Model (services/core/searchapp/models.py):**
```python
class Artist(models.Model):
    name              = models.CharField(max_length=255, unique=True)
    image_url         = models.URLField(max_length=500, blank=True, default='')
    bio               = models.TextField(default='')
    monthly_listeners = models.IntegerField(default=0)
    created_at        = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['name'])]

    def __str__(self):
        return self.name
```

**API Response:**
```json
{
    "id": 1,
    "name": "The Weeknd",
    "image_url": "https://picsum.photos/seed/weeknd/300/300",
    "bio": "",
    "monthly_listeners": 82400000,
    "created_at": "2026-03-26T10:00:00Z"
}
```

**Monthly listeners aggregation (future — when historyapp has data):**
```python
from django.db.models import Count
from django.utils import timezone
from datetime import timedelta

thirty_days_ago = timezone.now() - timedelta(days=30)
monthly_listeners = Play.objects.filter(
    song__artist_id=artist.id,
    played_at__gte=thirty_days_ago
).values('user_id').distinct().count()
```

---

### Table 3: searchapp_album

**Service:** Core (searchapp app)  
**Purpose:** Albums belong to one artist. Songs belong to one album (optionally).
The same artist cannot have two albums with the same name.

```sql
CREATE TABLE searchapp_album (
    id           BIGSERIAL    PRIMARY KEY,
    artist_id    BIGINT       NOT NULL REFERENCES searchapp_artist(id) ON DELETE CASCADE,
    name         VARCHAR(255) NOT NULL,
    cover_url    VARCHAR(500) NOT NULL DEFAULT '',
    release_year INTEGER      NULL,
    created_at   TIMESTAMP    NOT NULL DEFAULT NOW(),

    UNIQUE (artist_id, name)
);

CREATE INDEX idx_album_artist ON searchapp_album (artist_id);
CREATE INDEX idx_album_name   ON searchapp_album (name);
```

**Django Model (services/core/searchapp/models.py):**
```python
class Album(models.Model):
    artist       = models.ForeignKey(
                       Artist,
                       on_delete=models.CASCADE,
                       related_name='albums'
                   )
    name         = models.CharField(max_length=255)
    cover_url    = models.URLField(max_length=500, blank=True, default='')
    release_year = models.IntegerField(null=True, blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('artist', 'name')
        indexes = [
            models.Index(fields=['artist']),
            models.Index(fields=['name']),
        ]

    def __str__(self):
        return f"{self.name} — {self.artist.name}"
```

**API Response (artist always nested):**
```json
{
    "id": 1,
    "name": "After Hours",
    "cover_url": "https://picsum.photos/seed/afterhours/300/300",
    "release_year": 2020,
    "artist": {
        "id": 1,
        "name": "The Weeknd",
        "image_url": "https://picsum.photos/seed/weeknd/300/300",
        "monthly_listeners": 82400000
    }
}
```

---

### Table 4: searchapp_song

**Service:** Core (searchapp app)  
**Purpose:** Individual songs in the global catalog. Each song belongs to one
artist (required) and one album (optional — a song may be a standalone single).
Songs are the unit of playback and the entity added to playlists.

```sql
CREATE TABLE searchapp_song (
    id               BIGSERIAL    PRIMARY KEY,
    artist_id        BIGINT       NOT NULL REFERENCES searchapp_artist(id) ON DELETE CASCADE,
    album_id         BIGINT       NULL     REFERENCES searchapp_album(id)  ON DELETE SET NULL,
    -- album_id is nullable: a song may have no album (standalone single)
    title            VARCHAR(255) NOT NULL,
    genre            VARCHAR(100) NOT NULL DEFAULT '',
    release_year     INTEGER      NULL,
    duration_seconds INTEGER      NOT NULL DEFAULT 0,
    cover_url        VARCHAR(500) NOT NULL DEFAULT '',
    -- Song-level cover (often same as album cover but can differ)
    audio_url        VARCHAR(500) NOT NULL DEFAULT '',
    -- Full Supabase public URL for the MP3 file
    storage_path     VARCHAR(500) NOT NULL DEFAULT '',
    -- Filename inside Supabase "songs" bucket (e.g. "SoundHelix-Song-1.mp3")
    created_at       TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_song_artist ON searchapp_song (artist_id);
CREATE INDEX idx_song_album  ON searchapp_song (album_id);
CREATE INDEX idx_song_title  ON searchapp_song (title);
CREATE INDEX idx_song_genre  ON searchapp_song (genre);
CREATE INDEX idx_song_year   ON searchapp_song (release_year);
```

**Django Model (services/core/searchapp/models.py):**
```python
class Song(models.Model):
    artist           = models.ForeignKey(
                           Artist,
                           on_delete=models.CASCADE,
                           related_name='songs'
                       )
    album            = models.ForeignKey(
                           Album,
                           on_delete=models.SET_NULL,
                           null=True,
                           blank=True,
                           related_name='songs'
                       )
    title            = models.CharField(max_length=255)
    genre            = models.CharField(max_length=100, default='')
    release_year     = models.IntegerField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    cover_url        = models.URLField(max_length=500, blank=True, default='')
    audio_url        = models.URLField(max_length=500, blank=True, default='')
    storage_path     = models.CharField(max_length=500, blank=True, default='')
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['artist']),
            models.Index(fields=['album']),
            models.Index(fields=['title']),
            models.Index(fields=['genre']),
            models.Index(fields=['release_year']),
        ]

    def __str__(self):
        return f"{self.title} — {self.artist.name}"
```

**API Response (artist always nested; album nested when present, null when absent):**
```json
{
    "id": 1,
    "title": "Blinding Lights",
    "artist": {
        "id": 1,
        "name": "The Weeknd",
        "image_url": "https://picsum.photos/seed/weeknd/300/300",
        "monthly_listeners": 82400000
    },
    "album": {
        "id": 1,
        "name": "After Hours",
        "cover_url": "https://picsum.photos/seed/afterhours/300/300",
        "release_year": 2020
    },
    "genre": "Pop",
    "release_year": 2019,
    "duration_seconds": 200,
    "cover_url": "https://picsum.photos/seed/blinding/200/200",
    "audio_url": "https://YOURREF.supabase.co/storage/v1/object/public/songs/SoundHelix-Song-1.mp3",
    "storage_path": "SoundHelix-Song-1.mp3"
}
```

**When album is null (standalone single):**
```json
{
    "id": 9,
    "title": "Standalone Single",
    "artist": { "id": 2, "name": "Some Artist", ... },
    "album": null,
    ...
}
```

**Search sort fields:**

| `sort=`     | Django `order_by`  |
|-------------|--------------------|
| `title`     | `title`            |
| `artist`    | `artist__name`     |
| `album`     | `album__name`      |
| `genre`     | `genre`            |
| `duration`  | `duration_seconds` |
| `year`      | `release_year`     |
| `relevance` | (default, no sort) |

---

### Table 5: playlistapp_playlist

**Service:** Core (playlistapp app)  
**Purpose:** User-owned playlists. A playlist is either solo or collaborative.
A collaborative playlist MUST be private (enforced in serializer).

```sql
CREATE TABLE playlistapp_playlist (
    id            BIGSERIAL    PRIMARY KEY,
    owner_id      INTEGER      NOT NULL,
    -- References auth_user.id — plain integer, no FK constraint (cross-service)
    name          VARCHAR(255) NOT NULL,
    description   TEXT         NOT NULL DEFAULT '',
    visibility    VARCHAR(10)  NOT NULL DEFAULT 'public',
    -- Allowed values: 'public', 'private'
    -- RULE: collaborative playlists MUST be 'private'
    playlist_type VARCHAR(15)  NOT NULL DEFAULT 'solo',
    -- Allowed values: 'solo', 'collaborative'
    cover_url     VARCHAR(500) NOT NULL DEFAULT '',
    -- Empty string means the frontend renders a gradient placeholder
    max_songs     INTEGER      NOT NULL DEFAULT 0,
    -- 0 = no limit. Positive integer = maximum tracks allowed in this playlist.
    -- Enforced by the trackapp add-track view.
    created_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_playlist_owner    ON playlistapp_playlist (owner_id);
CREATE INDEX idx_playlist_name     ON playlistapp_playlist (name);
CREATE INDEX idx_playlist_created  ON playlistapp_playlist (created_at);
CREATE INDEX idx_playlist_updated  ON playlistapp_playlist (updated_at);
CREATE INDEX idx_playlist_type     ON playlistapp_playlist (playlist_type);
```

**Django Model (services/core/playlistapp/models.py):**
```python
from django.db import models


class Playlist(models.Model):
    VISIBILITY_CHOICES = [('public', 'Public'), ('private', 'Private')]
    TYPE_CHOICES       = [('solo', 'Solo'), ('collaborative', 'Collaborative')]

    owner_id      = models.IntegerField()
    name          = models.CharField(max_length=255)
    description   = models.TextField(default='')
    visibility    = models.CharField(
                        max_length=10,
                        choices=VISIBILITY_CHOICES,
                        default='public'
                    )
    playlist_type = models.CharField(
                        max_length=15,
                        choices=TYPE_CHOICES,
                        default='solo'
                    )
    cover_url     = models.URLField(max_length=500, blank=True, default='')
    max_songs     = models.IntegerField(default=0)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['owner_id']),
            models.Index(fields=['name']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['playlist_type']),
        ]

    def __str__(self):
        return self.name
```

**Note on VISIBILITY_CHOICES / TYPE_CHOICES format:**
Each tuple is `(database_value, display_label)`. The first element is stored
in the database (e.g. `'public'`); the second is shown in Django admin and
forms (e.g. `'Public'`). This is standard Django choices syntax — the apparent
duplication is intentional.

**API Response:**
```json
{
    "id": 1,
    "owner_id": 3,
    "name": "My Chill Playlist",
    "description": "Songs for studying",
    "visibility": "private",
    "playlist_type": "collaborative",
    "cover_url": "",
    "max_songs": 0,
    "created_at": "2026-03-26T10:00:00Z",
    "updated_at": "2026-03-26T12:00:00Z"
}
```

**Playlist sort fields:**

| `sort=`                | Django `order_by` |
|------------------------|-------------------|
| `updated_at` (default) | `-updated_at`     |
| `name`                 | `name`            |
| `created_at`           | `created_at`      |

---

### Table 6: trackapp_track

**Service:** Core (trackapp app)  
**Purpose:** Junction table linking Playlist ↔ Song. Records who added a song,
when, and its position in the playlist. The same song can only appear ONCE
per playlist.

**Model class: `Track` — do NOT rename. Table: `trackapp_track`.**

```sql
CREATE TABLE trackapp_track (
    id          BIGSERIAL PRIMARY KEY,
    playlist_id BIGINT    NOT NULL REFERENCES playlistapp_playlist(id) ON DELETE CASCADE,
    song_id     BIGINT    NOT NULL REFERENCES searchapp_song(id)        ON DELETE CASCADE,
    added_by_id INTEGER   NOT NULL,
    -- References auth_user.id — plain integer, no FK constraint (cross-service)
    position    INTEGER   NOT NULL DEFAULT 0,
    -- 0-indexed. Preserved when sorting by other fields.
    added_at    TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE (playlist_id, song_id)
);

CREATE INDEX idx_track_playlist_pos   ON trackapp_track (playlist_id, position);
CREATE INDEX idx_track_playlist_added ON trackapp_track (playlist_id, added_at);
CREATE INDEX idx_track_added_by       ON trackapp_track (added_by_id);
```

**Django Model (services/core/trackapp/models.py):**
```python
from django.db import models
from playlistapp.models import Playlist
from searchapp.models import Song


class Track(models.Model):
    playlist    = models.ForeignKey(
                      Playlist,
                      on_delete=models.CASCADE,
                      related_name='tracks'
                  )
    song        = models.ForeignKey(
                      Song,
                      on_delete=models.CASCADE,
                      related_name='playlist_entries'
                  )
    added_by_id = models.IntegerField()
    position    = models.IntegerField(default=0)
    added_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('playlist', 'song')
        ordering        = ['position']
        indexes         = [
            models.Index(fields=['playlist', 'position']),
            models.Index(fields=['playlist', 'added_at']),
            models.Index(fields=['added_by_id']),
        ]

    def __str__(self):
        return f"{self.song.title} in {self.playlist.name} @ pos {self.position}"
```

**Cross-app imports are valid here** because `Playlist` (playlistapp) and
`Song` (searchapp) both live inside the same core service Django project.

**API Response (song always fully nested with artist and album):**
```json
{
    "id": 5,
    "playlist_id": 1,
    "song": {
        "id": 1,
        "title": "Blinding Lights",
        "artist": {
            "id": 1,
            "name": "The Weeknd",
            "image_url": "https://picsum.photos/seed/weeknd/300/300",
            "monthly_listeners": 82400000
        },
        "album": {
            "id": 1,
            "name": "After Hours",
            "cover_url": "https://picsum.photos/seed/afterhours/300/300",
            "release_year": 2020
        },
        "genre": "Pop",
        "release_year": 2019,
        "duration_seconds": 200,
        "cover_url": "https://picsum.photos/seed/blinding/200/200",
        "audio_url": "https://YOURREF.supabase.co/storage/v1/object/public/songs/SoundHelix-Song-1.mp3",
        "storage_path": "SoundHelix-Song-1.mp3"
    },
    "added_by_id": 3,
    "position": 0,
    "added_at": "2026-03-26T11:00:00Z"
}
```

**Frontend sends when adding a track:**
```json
POST /api/tracks/1/
{ "song_id": 12 }
```

**max_songs enforcement in add-track view:**
```python
if playlist.max_songs > 0:
    count = Track.objects.filter(playlist=playlist).count()
    if count >= playlist.max_songs:
        return Response(
            {"error": "playlist_song_limit_reached", "max_songs": playlist.max_songs},
            status=status.HTTP_400_BAD_REQUEST
        )
```

**Track sort fields:**

| `sort=`              | Django `order_by`      |
|----------------------|------------------------|
| `custom` (default)   | `position`             |
| `title`              | `song__title`          |
| `artist`             | `song__artist__name`   |
| `album`              | `song__album__name`    |
| `genre`              | `song__genre`          |
| `duration`           | `song__duration_seconds` |
| `year`               | `song__release_year`   |
| `added_at`           | `added_at`             |

---

### Table 7: historyapp_play

**Service:** Core (historyapp app — new Django app inside core service)  
**Purpose:** Records every song play event per user. Drives the "Recently
played" section on the home page. Will drive real `monthly_listeners`
aggregation in production.

```sql
CREATE TABLE historyapp_play (
    id        BIGSERIAL PRIMARY KEY,
    user_id   INTEGER   NOT NULL,
    -- References auth_user.id — plain integer, no FK constraint (cross-service)
    song_id   BIGINT    NOT NULL REFERENCES searchapp_song(id) ON DELETE CASCADE,
    played_at TIMESTAMP NOT NULL DEFAULT NOW()
    -- No UNIQUE constraint — the same song can be played many times
);

CREATE INDEX idx_play_user_time ON historyapp_play (user_id, played_at DESC);
CREATE INDEX idx_play_song_time ON historyapp_play (song_id, played_at DESC);
-- Composite indexes for fast "recent plays by user" and "plays per song" queries
```

**Django Model (services/core/historyapp/models.py):**
```python
from django.db import models
from searchapp.models import Song


class Play(models.Model):
    user_id   = models.IntegerField()
    song      = models.ForeignKey(
                    Song,
                    on_delete=models.CASCADE,
                    related_name='plays'
                )
    played_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id', '-played_at']),
            models.Index(fields=['song', '-played_at']),
        ]

    def __str__(self):
        return f"User {self.user_id} played {self.song.title}"
```

**Views (services/core/historyapp/views.py):**

`POST /api/history/played/` — called by BottomPlayer when a song starts:
```python
class RecordPlayView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        song_id = request.data.get('song_id')
        if not song_id:
            return Response({'error': 'song_id required'}, status=400)
        try:
            song = Song.objects.get(id=song_id)
            Play.objects.create(user_id=request.user.id, song=song)
            return Response({'status': 'recorded'}, status=201)
        except Song.DoesNotExist:
            return Response({'error': 'Song not found'}, status=404)
```

`GET /api/history/recent/` — returns last 10 distinct songs:
```python
class RecentPlaysView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        seen   = set()
        recent = []
        plays  = Play.objects.filter(
                     user_id=request.user.id
                 ).select_related(
                     'song', 'song__artist', 'song__album'
                 ).order_by('-played_at')

        for play in plays:
            if play.song_id not in seen:
                seen.add(play.song_id)
                recent.append(play.song)
            if len(recent) >= 10:
                break

        return Response(SongSerializer(recent, many=True).data)
```

**API Response (recent plays):**
```json
[
    {
        "id": 1,
        "title": "Blinding Lights",
        "artist": { "id": 1, "name": "The Weeknd", ... },
        "album": { "id": 1, "name": "After Hours", ... },
        "genre": "Pop",
        "duration_seconds": 200,
        "audio_url": "https://YOURREF.supabase.co/...",
        "storage_path": "SoundHelix-Song-1.mp3"
    }
]
```

---

### Table 8: collabapp_collaborator

**Service:** Collaboration  
**Purpose:** Tracks which users are collaborators on collaborative playlists.
The owner is NEVER stored here — ownership is always derived from
`playlist.owner_id == request.user.id`. Every record in this table is a
collaborator by definition, so no `role` field is needed or present.

```sql
CREATE TABLE collabapp_collaborator (
    id          BIGSERIAL PRIMARY KEY,
    playlist_id INTEGER   NOT NULL,
    -- References playlistapp_playlist.id — plain integer, no FK (cross-service)
    user_id     INTEGER   NOT NULL,
    -- References auth_user.id — plain integer, no FK (cross-service)
    joined_at   TIMESTAMP NOT NULL DEFAULT NOW(),

    UNIQUE (playlist_id, user_id)
);

CREATE INDEX idx_collab_playlist ON collabapp_collaborator (playlist_id);
CREATE INDEX idx_collab_user     ON collabapp_collaborator (user_id);
```

**Django Model (services/collaboration/collabapp/models.py):**
```python
from django.db import models


class Collaborator(models.Model):
    playlist_id = models.IntegerField()
    user_id     = models.IntegerField()
    joined_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('playlist_id', 'user_id')
        indexes = [
            models.Index(fields=['playlist_id']),
            models.Index(fields=['user_id']),
        ]

    def __str__(self):
        return f"User {self.user_id} collaborates on playlist {self.playlist_id}"
```

**API Response:**
```json
{
    "id": 2,
    "playlist_id": 1,
    "user_id": 7,
    "joined_at": "2026-03-26T11:30:00Z"
}
```

**Note on IDs:** The `id` field is the auto PK of the Collaborator record
itself. The `user_id` field is the referenced auth user's ID. Both are needed.
The `unique_together` constraint ensures a user appears at most once per playlist.

---

### Table 9: collabapp_invitelink

**Service:** Collaboration  
**Purpose:** Invite tokens for joining collaborative playlists. When a user
joins via an invite link, a `Collaborator` record is created for them,
granting edit access (add/remove/reorder tracks).

```sql
CREATE TABLE collabapp_invitelink (
    id            BIGSERIAL PRIMARY KEY,
    playlist_id   INTEGER   NOT NULL,
    -- References playlistapp_playlist.id — plain integer, no FK (cross-service)
    token         UUID      NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    created_by_id INTEGER   NOT NULL,
    -- References auth_user.id — plain integer, no FK (cross-service)
    is_active     BOOLEAN   NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMP NULL
);

CREATE INDEX idx_invite_token           ON collabapp_invitelink (token);
CREATE INDEX idx_invite_playlist_active ON collabapp_invitelink (playlist_id, is_active);
```

**Django Model (services/collaboration/collabapp/models.py):**
```python
import uuid
from django.db import models
from django.utils import timezone


class InviteLink(models.Model):
    playlist_id   = models.IntegerField()
    token         = models.UUIDField(
                        default=uuid.uuid4,
                        unique=True,
                        editable=False
                    )
    created_by_id = models.IntegerField()
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['playlist_id', 'is_active']),
        ]

    @property
    def is_valid(self):
        """
        Use this instead of checking is_active alone.
        Returns False if deactivated OR if the expiry time has passed.
        """
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def __str__(self):
        return f"InviteLink {self.token} for playlist {self.playlist_id}"
```

**API Response:**
```json
{
    "id": 1,
    "playlist_id": 1,
    "token": "550e8400-e29b-41d4-a716-446655440000",
    "created_by_id": 3,
    "is_active": true,
    "is_valid": true,
    "created_at": "2026-03-26T10:00:00Z",
    "expires_at": null
}
```

**`is_valid` in serializer (SerializerMethodField — read-only):**
```python
class InviteLinkSerializer(serializers.ModelSerializer):
    is_valid = serializers.SerializerMethodField()

    class Meta:
        model  = InviteLink
        fields = '__all__'
        read_only_fields = ['token', 'created_by_id', 'created_at', 'is_valid']

    def get_is_valid(self, obj):
        return obj.is_valid
```

**Always use `invite.is_valid` in views, never `invite.is_active` alone.**

---

### Table 10: shareapp_sharelink

**Service:** Collaboration (shareapp — new Django app inside collaboration service)  
**Purpose:** Share tokens for read-only access to playlists. When a user visits
a share link, they can VIEW the playlist and listen to songs but cannot add,
remove, or reorder tracks. No `Collaborator` record is created.

**KEY DIFFERENCE from InviteLink:**
- `InviteLink` → user joins → `Collaborator` record created → **edit access**
- `ShareLink`  → user visits → NO record created → **view-only access**

```sql
CREATE TABLE shareapp_sharelink (
    id            BIGSERIAL PRIMARY KEY,
    playlist_id   INTEGER   NOT NULL,
    -- References playlistapp_playlist.id — plain integer, no FK (cross-service)
    token         UUID      NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    created_by_id INTEGER   NOT NULL,
    -- References auth_user.id — plain integer, no FK (cross-service)
    is_active     BOOLEAN   NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at    TIMESTAMP NULL
);

CREATE INDEX idx_share_token           ON shareapp_sharelink (token);
CREATE INDEX idx_share_playlist_active ON shareapp_sharelink (playlist_id, is_active);
```

**Django Model (services/collaboration/shareapp/models.py):**
```python
import uuid
from django.db import models
from django.utils import timezone


class ShareLink(models.Model):
    playlist_id   = models.IntegerField()
    token         = models.UUIDField(
                        default=uuid.uuid4,
                        unique=True,
                        editable=False
                    )
    created_by_id = models.IntegerField()
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    expires_at    = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['playlist_id', 'is_active']),
        ]

    @property
    def is_valid(self):
        """
        Use this instead of checking is_active alone.
        Returns False if deactivated OR if the expiry time has passed.
        """
        if not self.is_active:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def __str__(self):
        return f"ShareLink {self.token} for playlist {self.playlist_id}"
```

**API Response:**
```json
{
    "id": 1,
    "playlist_id": 1,
    "token": "7b9e6679-7425-40de-944b-e07fc1f90ae7",
    "created_by_id": 3,
    "is_active": true,
    "is_valid": true,
    "created_at": "2026-03-26T10:00:00Z",
    "expires_at": null
}
```

---

## Entity Relationship Diagram

```
auth_user  (Auth Service — Django built-in)
    │
    │  owner_id ─────────────────────────────► playlistapp_playlist
    │                                                   │
    │  added_by_id ──────────────────────────► trackapp_track ◄─── playlist FK
    │                                                   │
    │  user_id ──────────────────────────────► historyapp_play     song FK
    │                                                   │             │
    │                                                   └─────────────┼──► searchapp_song
    │                                                                 │        │
    │                                                                 │   artist FK ──► searchapp_artist
    │                                                                 │   album FK ───► searchapp_album ──► searchapp_artist
    │                                                                 │                    (artist FK)
    │  user_id ──────────────────────────────► collabapp_collaborator
    │                                          playlist_id ──────────► playlistapp_playlist
    │
    │  created_by_id ─────────────────────────► collabapp_invitelink
    │                                           playlist_id ─────────► playlistapp_playlist
    │
    └─ created_by_id ─────────────────────────► shareapp_sharelink
                                                playlist_id ─────────► playlistapp_playlist
```

**Solid arrows (►) = plain integer cross-service references (no DB FK constraint)**  
**FK labels inside core service = real Django ForeignKey with DB constraint**

---

## Relationship Summary

| Relationship                          | Type          | Via                              |
|---------------------------------------|---------------|----------------------------------|
| Artist → Albums                       | One-to-Many   | Album.artist FK                  |
| Artist → Songs                        | One-to-Many   | Song.artist FK                   |
| Album → Songs                         | One-to-Many   | Song.album FK (nullable)         |
| User → Playlists (owns)               | One-to-Many   | Playlist.owner_id (int)          |
| Playlist → Tracks                     | One-to-Many   | Track.playlist FK                |
| Song → Tracks                         | One-to-Many   | Track.song FK                    |
| Playlist ↔ Song                       | Many-to-Many  | via trackapp_track               |
| User → Tracks (added_by)              | One-to-Many   | Track.added_by_id (int)          |
| User → Plays                          | One-to-Many   | Play.user_id (int)               |
| Song → Plays                          | One-to-Many   | Play.song FK                     |
| Playlist → Collaborators              | One-to-Many   | Collaborator.playlist_id (int)   |
| User → Collaborator memberships       | One-to-Many   | Collaborator.user_id (int)       |
| Playlist → InviteLinks                | One-to-Many   | InviteLink.playlist_id (int)     |
| Playlist → ShareLinks                 | One-to-Many   | ShareLink.playlist_id (int)      |

---

## Migration Order

### Core Service — migration dependency chain

```
searchapp (Artist → Album → Song)
    ↓                  ↓
playlistapp (Playlist — no FK dependency on searchapp, can run in parallel)
    ↓  (depends on BOTH Playlist and Song)
trackapp (Track — FKs to playlistapp_playlist and searchapp_song)
    ↓  (depends on Song)
historyapp (Play — FK to searchapp_song)
```

### Exact commands

```bash
# --- Core Service ---
docker-compose exec core uv run python manage.py makemigrations searchapp
docker-compose exec core uv run python manage.py makemigrations playlistapp
docker-compose exec core uv run python manage.py makemigrations trackapp
docker-compose exec core uv run python manage.py makemigrations historyapp
docker-compose exec core uv run python manage.py migrate

# --- Auth Service ---
docker-compose exec auth uv run python manage.py migrate
# (no custom models — Django's own auth migrations run)

# --- Collaboration Service ---
docker-compose exec collaboration uv run python manage.py makemigrations collabapp
docker-compose exec collaboration uv run python manage.py makemigrations shareapp
docker-compose exec collaboration uv run python manage.py migrate

# --- Seed data (core service) ---
docker-compose exec core uv run python manage.py seed_songs
```

### Database reset (required before Commit 2 schema changes)

The searchapp_song and trackapp_track tables are fundamentally restructured.
A fresh database is required before applying Commit 2.

```bash
docker-compose down -v      # removes containers AND volumes (all DB data)
docker-compose up -d        # fresh DB — entrypoints auto-run all migrations
```

---

## Business Rules

1. **Collaborative playlist must be private.**
   If `playlist_type == 'collaborative'` then `visibility` must be `'private'`.
   Enforced in `PlaylistSerializer.validate()`. Returns HTTP 400 if violated.

2. **A song can appear only once per playlist.**
   `unique_together = ('playlist', 'song')` on `trackapp_track`.
   Attempting to add a duplicate returns HTTP 400.

3. **max_songs limit on playlists.**
   If `playlist.max_songs > 0`, the add-track view checks the current track
   count. If `count >= max_songs`, it returns HTTP 400 with
   `{"error": "playlist_song_limit_reached", "max_songs": N}`.
   A value of `0` means no limit (unlimited tracks allowed).

4. **Owner is never stored in the Collaborator table.**
   The `collabapp_collaborator` table contains only non-owner collaborators.
   Ownership is always determined by `playlist.owner_id == request.user.id`.

5. **Only owner can:** edit playlist metadata, delete the playlist, generate
   invite links, deactivate invite/share links, remove collaborators.

6. **Owner AND collaborators can:** add tracks, remove tracks, reorder tracks.

7. **Share link visitors can:** view the playlist and listen to songs only.
   They cannot add, remove, or reorder tracks. No `Collaborator` record is
   created when accessing a ShareLink.

8. **is_valid checks both is_active AND expires_at.**
   Always use `invite.is_valid` / `share.is_valid` in views, never
   `is_active` alone. `is_valid` returns `False` if `is_active=False` OR
   if `expires_at` is set and the current time is past it.

9. **Joining a playlist when already a collaborator.**
   Attempting to join via InviteLink when already a Collaborator returns
   HTTP 200 with `{"error": "already_member"}` (not 400 or 409).

10. **audio_url is the Supabase public URL.**
    It is used directly by the HTML5 `<audio>` element. `storage_path` is
    the filename inside the bucket and is used by the seed management command.

11. **Song album is optional.**
    A song may have `album = null` (standalone single). Serializers handle
    this by returning `"album": null`. Artist is always required and never null.

12. **Monthly listeners is seeded for demo purposes.**
    The `Artist.monthly_listeners` field is populated by the seed command with
    realistic static values. The `historyapp_play` table is in place so that
    real aggregation can replace it in production.

13. **Position is 0-indexed.**
    Track positions start at 0. Auto-assigned as `max(position) + 1` when
    adding a new track. The reorder endpoint accepts a full `track_ids` array
    and reassigns positions from 0 upward.

14. **Cross-service references use plain integers.**
    Any field referencing a model in another service (auth_user, playlist from
    collaboration service) is a plain `IntegerField`. Django FK constraints are
    only used within the same service's Django project. This is the standard
    shared-database microservices pattern for this architecture.

---

## Complete API Endpoint Reference

### Auth Service — `http://localhost/api/auth/`

| Method | Endpoint                    | Auth     | Description                         |
|--------|-----------------------------|----------|-------------------------------------|
| POST   | `/api/auth/register/`       | Open     | Register. Body: `{username, password}` |
| POST   | `/api/auth/login/`          | Open     | Obtain JWT pair. Body: `{username, password}` |
| POST   | `/api/auth/token/refresh/`  | Open     | Refresh access token. Body: `{refresh}` |
| GET    | `/api/auth/me/`             | Required | Return current user `{id, username}` |
| GET    | `/api/auth/health/`         | Open     | Health check                        |

---

### Core Service — Playlists — `http://localhost/api/playlists/`

| Method | Endpoint                 | Auth     | Description                                       |
|--------|--------------------------|----------|---------------------------------------------------|
| GET    | `/api/playlists/`        | Required | List owner's playlists. `?sort=name\|created_at\|updated_at&order=asc\|desc` |
| POST   | `/api/playlists/`        | Required | Create playlist. `owner_id` auto-set from token   |
| GET    | `/api/playlists/:id/`    | Required | Get playlist detail                               |
| PATCH  | `/api/playlists/:id/`    | Required | Update playlist (owner only)                      |
| DELETE | `/api/playlists/:id/`    | Required | Delete playlist (owner only)                      |
| GET    | `/api/playlists/health/` | Open     | Health check                                      |

---

### Core Service — Tracks — `http://localhost/api/tracks/`

| Method | Endpoint                             | Auth     | Description                                               |
|--------|--------------------------------------|----------|-----------------------------------------------------------|
| GET    | `/api/tracks/:playlist_id/`          | Required | List tracks. `?sort=custom\|title\|artist\|album\|genre\|duration\|year\|added_at&order=asc\|desc` |
| POST   | `/api/tracks/:playlist_id/`          | Required | Add track. Body: `{"song_id": N}`. Checks max_songs.      |
| DELETE | `/api/tracks/:playlist_id/:track_id/`| Required | Remove track by track ID                                  |
| PUT    | `/api/tracks/:playlist_id/reorder/`  | Required | Reorder. Body: `{"track_ids": [3, 1, 2]}`                 |
| GET    | `/api/tracks/health/`                | Open     | Health check                                              |

---

### Core Service — Search — `http://localhost/api/search/`

| Method | Endpoint                     | Auth     | Description                                                    |
|--------|------------------------------|----------|----------------------------------------------------------------|
| GET    | `/api/search/`               | Required | Search songs. `?q=taylor&genre=Pop&sort=title&order=asc`       |
| GET    | `/api/search/browse/`        | Required | List distinct genres                                           |
| GET    | `/api/search/artists/`       | Required | Search artists. `?q=weeknd`                                    |
| GET    | `/api/search/artists/:id/`   | Required | Artist detail with albums                                      |
| GET    | `/api/search/albums/`        | Required | Search albums. `?q=after+hours`                                |
| GET    | `/api/search/albums/:id/`    | Required | Album detail with songs                                        |
| GET    | `/api/search/health/`        | Open     | Health check                                                   |

---

### Core Service — History — `http://localhost/api/history/`

| Method | Endpoint                    | Auth     | Description                                              |
|--------|-----------------------------|----------|----------------------------------------------------------|
| POST   | `/api/history/played/`      | Required | Record a play. Body: `{"song_id": N}`. Fire-and-forget.  |
| GET    | `/api/history/recent/`      | Required | Last 10 distinct songs played by current user            |
| GET    | `/api/history/health/`      | Open     | Health check                                             |

---

### Core Service — Core Health — `http://localhost/api/core/`

| Method | Endpoint            | Auth | Description              |
|--------|---------------------|------|--------------------------|
| GET    | `/api/core/health/` | Open | Aggregated health check  |

---

### Collaboration Service — Collab — `http://localhost/api/collab/`

| Method | Endpoint                                     | Auth     | Description                                              |
|--------|----------------------------------------------|----------|----------------------------------------------------------|
| GET    | `/api/collab/health/`                        | Open     | Health check                                             |
| POST   | `/api/collab/:playlist_id/invite/`           | Required | Generate an InviteLink for this playlist                 |
| DELETE | `/api/collab/:playlist_id/invite/deactivate/`| Required | Deactivate the active InviteLink for this playlist       |
| GET    | `/api/collab/join/:token/`                   | Required | Validate invite token. Returns `{playlist_id, is_valid}` |
| POST   | `/api/collab/join/:token/`                   | Required | Join playlist via invite. Creates Collaborator record.   |
| GET    | `/api/collab/:playlist_id/members/`          | Required | List collaborators for a playlist                        |
| DELETE | `/api/collab/:playlist_id/members/`          | Required | Remove collaborator. `?user_id=X`                        |
| GET    | `/api/collab/my-collaborations/`             | Required | All playlist_ids where current user is a Collaborator    |
| GET    | `/api/collab/:playlist_id/my-role/`          | Required | Returns `{"role": "collaborator"}` or 404                |

---

### Collaboration Service — Share — `http://localhost/api/share/`

| Method | Endpoint                              | Auth     | Description                                              |
|--------|---------------------------------------|----------|----------------------------------------------------------|
| POST   | `/api/share/:playlist_id/create/`     | Required | Generate a ShareLink for this playlist                   |
| DELETE | `/api/share/:playlist_id/deactivate/` | Required | Deactivate the active ShareLink for this playlist        |
| GET    | `/api/share/view/:token/`             | Required | Validate token and return playlist data (view-only)      |
| GET    | `/api/share/health/`                  | Open     | Health check                                             |

---

## TypeScript Types (client/src/types/index.ts)

```typescript
// ─── Auth ────────────────────────────────────────────────────────────────────
export interface User {
    id:       number;
    username: string;
}

export interface AuthTokens {
    access:  string;
    refresh: string;
}

// ─── Artist ──────────────────────────────────────────────────────────────────
export interface Artist {
    id:                number;
    name:              string;
    image_url:         string;
    bio:               string;
    monthly_listeners: number;
}

// ─── Album ───────────────────────────────────────────────────────────────────
export interface Album {
    id:           number;
    name:         string;
    cover_url:    string;
    release_year: number | null;
    artist:       Artist;
}

// ─── Song ────────────────────────────────────────────────────────────────────
export interface Song {
    id:               number;
    title:            string;
    artist:           Artist;           // always present, never null
    album:            Album | null;     // null for standalone singles
    genre:            string;
    release_year:     number | null;
    duration_seconds: number;
    cover_url:        string;
    audio_url:        string;           // Supabase public URL for <audio>
    storage_path:     string;           // filename in Supabase bucket
}

// ─── Playlist ────────────────────────────────────────────────────────────────
export interface Playlist {
    id:            number;
    owner_id:      number;
    name:          string;
    description:   string;
    visibility:    'public' | 'private';
    playlist_type: 'solo' | 'collaborative';
    cover_url:     string;
    max_songs:     number;              // 0 = no limit
    created_at:    string;
    updated_at:    string;
}

// ─── Track ───────────────────────────────────────────────────────────────────
// A Song inserted into a Playlist. Model name in Django: Track. Table: trackapp_track.
export interface Track {
    id:          number;
    playlist_id: number;
    song:        Song;                  // always fully nested
    added_by_id: number;
    position:    number;
    added_at:    string;
}

// ─── Collaboration ───────────────────────────────────────────────────────────
export interface Collaborator {
    id:          number;
    playlist_id: number;
    user_id:     number;
    joined_at:   string;
}

export interface InviteLink {
    id:            number;
    playlist_id:   number;
    token:         string;
    created_by_id: number;
    is_active:     boolean;
    is_valid:      boolean;             // computed: is_active AND not expired
    created_at:    string;
    expires_at:    string | null;
}

// ─── Share ───────────────────────────────────────────────────────────────────
export interface ShareLink {
    id:            number;
    playlist_id:   number;
    token:         string;
    created_by_id: number;
    is_active:     boolean;
    is_valid:      boolean;             // computed: is_active AND not expired
    created_at:    string;
    expires_at:    string | null;
}

// ─── Sorting ─────────────────────────────────────────────────────────────────
export type TrackSortField =
    | 'custom' | 'title' | 'artist' | 'album'
    | 'genre'  | 'duration' | 'year' | 'added_at';

export type PlaylistSortField = 'updated_at' | 'name' | 'created_at';

export type SearchSortField =
    | 'relevance' | 'title' | 'artist' | 'duration' | 'year';

export type SortOrder = 'asc' | 'desc';

// ─── Player ──────────────────────────────────────────────────────────────────
export type RepeatMode = 'off' | 'all' | 'one';

export interface PlayerState {
    queue:         Track[];
    originalQueue: Track[];
    currentIndex:  number;
    currentTrack:  Track | null;
    isPlaying:     boolean;
    progress:      number;
    duration:      number;
    volume:        number;
    isMuted:       boolean;
    shuffle:       boolean;
    repeatMode:    RepeatMode;
}

// ─── Genre ───────────────────────────────────────────────────────────────────
export interface Genre {
    name:  string;
    color: string;
}
```

---

## Per-Member Ownership

| Member                       | Service        | Tables Owned                                                              |
|------------------------------|----------------|---------------------------------------------------------------------------|
| Sadman Sakib (2105121)       | auth           | auth_user                                                                 |
| Taskeen Towfique (2105122)   | core/playlist  | playlistapp_playlist                                                      |
| Raiyan Siddiqui (2105130)    | core/track     | trackapp_track                                                            |
| Mehedi Khan (2105141)        | core/search+history | searchapp_artist, searchapp_album, searchapp_song, historyapp_play   |
| Mesbah Ahamed (2105139)      | collaboration  | collabapp_collaborator, collabapp_invitelink, shareapp_sharelink          |
| Fatin Arian (2105143)        | frontend only  | none                                                                      |

---

**Maintained by:** Mesbah Ahamed (2105139)  
**Last Updated:** 2026-03-26  
**Status:** Final — all modifications applied