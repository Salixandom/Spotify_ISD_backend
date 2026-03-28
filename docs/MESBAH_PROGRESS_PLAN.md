# Mesbah's Progress Plan
# Spotify ISD Backend — Schema Overhaul & New Apps
# Member: Mesbah Ahamed (2105139)
# Scope: Collaboration service owner + schema-wide modifications

---

## 1. Purpose of This Document

This document is the authoritative planning reference for all schema changes,
new app creations, and commit-by-commit work that Mesbah will execute on the
Spotify ISD backend. No code is written until this plan is complete and agreed
upon. Every future session will begin by reading this file.

---

## 2. Design Question Answers

Before listing modifications, the following architectural questions raised
during schema review are answered here so every decision is recorded.

---

### Q1: Why is there no ForeignKey to auth_user.id in owner_id, added_by_id, user_id fields?

**Answer: Microservices service-boundary convention.**

All three services (auth, core, collaboration) run as separate Django
applications. Even though they share one PostgreSQL database (spotifydb),
each Django app only knows about the models it defines itself. If the core
service imported `from django.contrib.auth.models import User` to create a
real ForeignKey, it would introduce a hard ORM dependency on the auth service's
model layer. This tightly couples two services that are supposed to be
independently deployable and testable.

The JWT token provides application-level integrity: when a request arrives
at the core service, the JWT is verified and `request.user.id` is a trusted
integer. That integer is stored as a plain `IntegerField`. The database
never needs to validate it because the authentication layer already did.

This is the standard "shared database, logical service separation" microservices
pattern: no cross-service FK constraints at the ORM level, referential
correctness enforced by the application (JWT) and the API contract.

**Decision: Keep all cross-service user/playlist references as IntegerField.
Do NOT add ForeignKey to auth_user from core or collaboration service.**

---

### Q2: Why do VISIBILITY_CHOICES and TYPE_CHOICES have two versions of the same word?
### e.g. ('public', 'Public') or ('solo', 'Solo')

**Answer: Standard Django choices tuple pattern — (database_value, display_label).**

Django's `choices` parameter accepts a list of 2-tuples where:
- The FIRST element is what gets stored in the database column (machine-readable,
  lowercase, compact).
- The SECOND element is the human-readable label shown in forms, the Django
  admin panel, and serializer `get_FOO_display()` calls.

So `('public', 'Public')` stores the string `"public"` in the DB but displays
`"Public"` in the admin. This is intentional and is the correct Django pattern.

**Decision: Keep VISIBILITY_CHOICES and TYPE_CHOICES exactly as-is.
No simplification is needed — the duplication is not real duplication,
it is the value/label separation that Django requires.**

---

### Q3: In collabapp_collaborator, shouldn't the collaborator's ID just be the user ID?

**Answer: The two IDs serve different purposes.**

The `Collaborator` model has:
- `id`      — the auto-generated primary key of the Collaborator *record*
               (needed by Django ORM, used in DELETE endpoints by record ID)
- `user_id` — the ID of the auth_user who is collaborating

The `user_id` IS the user's ID. The `id` is just the row identifier for the
collaborator membership record itself. This is correct relational design.
The `unique_together = ('playlist_id', 'user_id')` constraint already ensures
a user can only appear once per playlist.

**Decision: Keep both fields. user_id is the user reference; id is the
record PK. No change to this structure.**

---

### Q4: In collabapp_invitelink, shouldn't playlist_id and created_by_id be ForeignKeys?

**Answer: playlist_id cannot be a Django FK; created_by_id cannot either.**

- `playlist_id` references `playlistapp_playlist.id` which lives in the CORE
  service. The collaboration service has no Django ORM access to that model.
- `created_by_id` references `auth_user.id` which lives in the AUTH service.
  Same problem.

Since all three services share one PostgreSQL database, it would technically
be possible to add raw SQL FK constraints at the database level. However,
Django migrations would not manage them and they would create implicit coupling
between services that breaks independent deployment.

The existing pattern — IntegerField with application-level integrity — is the
correct choice for this architecture. This also applies to `shareapp_sharelink`
(the new model).

**Decision: Keep playlist_id and created_by_id as IntegerField in both
InviteLink and ShareLink. Consistent with every other cross-service
reference in the codebase.**

---

## 3. Naming Conventions (Critical)

Two entities are easily confused. The distinction below is final and applies
to every model, serializer, view, URL, and variable name in the codebase.

| Term    | Model  | App        | Table              | Meaning                                         |
|---------|--------|------------|--------------------|-------------------------------------------------|
| Song    | Song   | searchapp  | searchapp_song     | Standalone
 catalog entry — the music library    |
| Track   | Track  | trackapp   | trackapp_track     | A Song inserted into a specific Playlist        |

- "Song" always means: an entry in the global music catalog.
- "Track" always means: the junction record that places a Song onto a Playlist,
  carrying position, who added it, and when.
- The model class STAYS named `Track`. The table STAYS `trackapp_track`.
  Do NOT rename it to PlaylistTrack anywhere in code or migrations.

---

## 4. Complete Modification List

The following is the exhaustive list of changes derived from the provided
schema context and modifications. Each entry states WHAT changes, WHY, and
any constraints to honour.

---

### 4.1 auth_user — NO CHANGES (Keep Django Built-in User)

**Decision: The default Django User model is kept exactly as-is.**

Django's built-in `User` from `django.contrib.auth.models` is required for
`djangorestframework-simplejwt` to work out of the box. The JWT system binds
to `AUTH_USER_MODEL` and all token serialisation depends on Django's standard
user fields. Replacing it with a custom `AbstractBaseUser` adds migration
complexity and risk with zero benefit for this project.

**What this means in practice:**
- `authapp/models.py` stays empty (imports models, defines nothing).
- `AUTH_USER_MODEL` is NOT set in settings.py (Django defaults to auth.User).
- `django.contrib.auth` stays in INSTALLED_APPS.
- No `authapp/migrations/` folder is needed (Django's own auth migrations
  create auth_user).
- `RegisterSerializer` keeps fields: `id`, `username`, `password` (write-only).
- `UserSerializer` keeps fields: `id`, `username`.

The auth service schema is FROZEN. No commits will touch its models.

---

### 4.2 searchapp_artist — No Schema Change

**Change:** None. Model fields stay exactly as specified in the agreed schema.

**Fields (for reference):**
- `id`                — BigAutoField PK
- `name`              — CharField(255) UNIQUE
- `image_url`         — URLField(500) default=''
- `bio`               — TextField default=''
- `monthly_listeners` — IntegerField default=0
- `created_at`        — DateTimeField auto_now_add

**Index:** on `name`.

**What changes in this commit:** The Artist model is NEW relative to the
current codebase (the current searchapp has no Artist model). A fresh
migration creates it. The serializer is also new.

---

### 4.3 searchapp_album — No max_songs (Keep Schema Clean)

**Change:** The `max_songs` field originally discussed is REMOVED from Album.
Albums have no song-count ceiling enforced by the backend. Song limits, if
ever needed, belong on Playlist (see 4.5), not on Album.

**Fields:**
- `id`           — BigAutoField PK
- `artist`       — ForeignKey(Artist, CASCADE, related_name='albums')
- `name`         — CharField(255)
- `cover_url`    — URLField(500) default=''
- `release_year` — IntegerField null=True blank=True
- `created_at`   — DateTimeField auto_now_add

**Constraints:** unique_together = ('artist', 'name')
**Indexes:** on `artist`, on `name`.

**Migration dependency:** Album depends on Artist. Artist must migrate first.

---

### 4.4 searchapp_song — Album Becomes Optional, Add artist FK, Add Indexes

**Change:** The current `Song` model is a flat table with `artist` and `album`
as plain `CharField`. It is completely replaced.

**New fields:**
- `id`               — BigAutoField PK
- `artist`           — ForeignKey(Artist, CASCADE, related_name='songs') REQUIRED
- `album`            — ForeignKey(Album, SET_NULL, null=True, blank=True, related_name='songs')
                       OPTIONAL — a song may be a standalone single with no album
- `title`            — CharField(255)
- `genre`            — CharField(100) default=''
- `release_year`     — IntegerField null=True blank=True
- `duration_seconds` — IntegerField default=0
- `cover_url`        — URLField(500) default=''
- `audio_url`        — URLField(500) default=''
                       Full Supabase public URL used by the audio element
- `storage_path`     — CharField(500) default=''
                       Filename inside the Supabase "songs" bucket
- `created_at`       — DateTimeField auto_now_add

**Indexes:** on artist, album, title, genre, release_year.

**Migration dependency:** Song depends on both Artist and Album.

**Serializer note:** `SongSerializer` must handle `album=None` gracefully,
returning `"album": null` in JSON. Use `AlbumSerializer(allow_null=True)`.
Artist is always nested. Album is nested when present, null when absent.

---

### 4.5 playlistapp_playlist — Remove snapshot_id, Add max_songs and cover_url, Add Indexes

**Changes:**
- REMOVE `snapshot_id` — eliminated per instruction; simplifies the model
- ADD    `cover_url`   — URLField(max_length=500, blank=True, default='')
                         (empty string = gradient placeholder on frontend)
- ADD    `max_songs`   — IntegerField(default=0)
                         0 means no limit. Any positive integer caps how many
                         tracks can be added to this playlist. Enforced by
                         the trackapp add-track view.
- CHANGE `description` — add default='' (currently blank=True only)
- ADD    indexes on owner_id, name, created_at, updated_at, playlist_type

**Fields retained unchanged:**
- `owner_id`, `name`, `visibility`, `playlist_type`, `created_at`, `updated_at`
- `VISIBILITY_CHOICES`, `TYPE_CHOICES` unchanged

**Business rule enforced in PlaylistSerializer.validate():**
If `playlist_type == 'collaborative'` then `visibility` MUST be `'private'`.
Raise `serializers.ValidationError` if a collaborative playlist is set public.

**View changes:**
- `get_queryset()` gains sort support: `?sort=name|created_at|updated_at`
  and `?order=asc|desc` (default: `-updated_at`)
- Owner logic unchanged: `owner_id=request.user.id`

**Migration strategy:** If the DB is fresh (after docker-compose down -v),
replace 0001_initial.py entirely. If migrations were already applied, add
0002_add_cover_max_songs_remove_snapshot.py on top.

---

### 4.6 trackapp_track — Replace Flat Fields with Real FKs to Playlist and Song

**The model class name STAYS `Track`. The table name STAYS `trackapp_track`.**

**What changes:** The current `Track` stores its own title/artist/album/etc.
These flat fields are removed. Instead, `Track` becomes a true junction table
linking `Playlist` ↔ `Song`, both of which live in the same core service
and can therefore use real Django ForeignKey relationships.

**Old fields REMOVED:**
- `playlist_id` (IntegerField) — replaced by real FK below
- `title`, `artist`, `album`  — belong to Song, not Track
- `duration_seconds`          — belongs to Song
- `cover_url`, `audio_url`    — belong to Song

**New / retained fields:**
- `id`          — BigAutoField PK (unchanged)
- `playlist`    — ForeignKey(Playlist, CASCADE, related_name='tracks')
                  Real Django FK — Playlist is in the SAME core service
- `song`        — ForeignKey(Song, CASCADE, related_name='playlist_entries')
                  Real Django FK — Song is in the SAME core service
- `added_by_id` — IntegerField() — cross-service ref to auth_user, stays plain

- `position`    — IntegerField(default=0) — 0-indexed ordering key
- `added_at`    — DateTimeField(auto_now_add=True)

**Constraints:**
- `unique_together = ('playlist', 'song')` — same song cannot appear twice
- `ordering = ['position']`
- Indexes: (playlist, position), (playlist, added_at), (added_by_id,)

**max_songs enforcement in add-track view:**
```
if playlist.max_songs > 0:
    count = Track.objects.filter(playlist=playlist).count()
    if count >= playlist.max_songs:
        return Response(
            {"error": "playlist_song_limit_reached", "max_songs": playlist.max_songs},
            status=400
        )
```

**API contract change:** Frontend sends `{ "song_id": 12 }` when adding a
track. The view resolves `Song.objects.get(id=song_id)` before creating Track.

**Serializer:** `TrackSerializer` nests full `SongSerializer` (which itself
nests ArtistSerializer and optionally AlbumSerializer). The `playlist_id`
is exposed as a read-only integer derived from the FK.

**Migration strategy:** Replace 0001_initial.py entirely with a new migration
for the new Track schema. The old Track table is incompatible.

---

### 4.7 historyapp_play — NEW App in Core Service

**Change:** Create `historyapp` as a new Django app inside the core service
at `services/core/historyapp/`.

**Model: Play**
- `id`        — BigAutoField PK
- `user_id`   — IntegerField() — cross-service auth ref, stays plain
- `song`      — ForeignKey(Song, CASCADE, related_name='plays')
- `played_at` — DateTimeField(auto_now_add=True)
- No unique constraint — same song can be played many times

**Indexes:** composite (user_id, -played_at) and (song, -played_at)

**Endpoints:**
- `POST /api/history/played/` — body: `{"song_id": 12}` — record a play event
- `GET  /api/history/recent/` — returns last 10 distinct songs for current user
- `GET  /api/history/health/` — health check

**RecentPlaysView logic:** Iterate plays ordered by `-played_at`, collect
song_ids into a seen set, append song to result list when unseen, stop at 10.
Use `select_related('song__artist', 'song__album')` for performance.

**Settings change:** Add `'historyapp'` to `INSTALLED_APPS` in core/settings.py
**URL change:** Add `path('api/history/', include('historyapp.urls'))` in core/urls.py
**Migration dependency:** Play FK on Song → searchapp migration must run first.

---

### 4.8 collabapp_collaborator — Remove role Field, Add Indexes

**Change:** Remove the `role` field entirely.

**Reasoning:** The only defined value was `'collaborator'`. The owner is NEVER
stored in this table — ownership is always determined by
`playlist.owner_id == request.user.id`. Every record in this table is a
collaborator by definition, so the role field adds no information.

**Fields retained:**
- `id`          — BigAutoField PK
- `playlist_id` — IntegerField (cross-service, stays plain)
- `user_id`     — IntegerField (cross-service, stays plain)
- `joined_at`   — DateTimeField auto_now_add

**Constraints:** unique_together = ('playlist_id', 'user_id')
**New indexes:** on playlist_id, on user_id separately.

**New endpoints added in this commit:**
- `GET /api/collab/my-collaborations/` — returns all playlist_ids where
  current user has a Collaborator record
- `GET /api/collab/:playlist_id/my-role/` — returns `{"role": "owner"}` if
  playlist.owner_id == user.id (requires a cross-service assumption or simple
  lookup by absence of collaborator record), else `{"role": "collaborator"}`
  if record exists, else 403
- `DELETE /api/collab/:playlist_id/invite/deactivate/` — sets is_active=False
  on active InviteLink for this playlist

---

### 4.9 collabapp_invitelink — Add is_valid Property, Add Indexes

**Fields unchanged:**
- `playlist_id`   — IntegerField (cross-service, stays plain)
- `token`         — UUIDField(default=uuid4, unique=True, editable=False)
- `created_by_id` — IntegerField (cross-service, stays plain)
- `is_active`     — BooleanField default=True
- `created_at`    — DateTimeField auto_now_add
- `expires_at`    — DateTimeField null=True blank=True

**Changes:**
- ADD `@property is_valid` — checks both is_active AND expires_at
- ADD `editable=False` to token field
- ADD indexes: on token, on (playlist_id, is_active)

**Serializer:** Expose `is_valid` as read-only via `SerializerMethodField`.
Always use `invite.is_valid` in views, never `invite.is_active` alone.

**Business rule:** Joining when already a collaborator returns HTTP 200 with
`{"error": "already_member"}` (not 400, not 409).

---

### 4.10 shareapp_sharelink — NEW App in Collaboration Service

**Change:** Create `shareapp` as a new Django app inside the collaboration
service at `services/collaboration/shareapp/`.

**Model: ShareLink** (mirrors InviteLink schema exactly):
- `id`            — BigAutoField PK
- `playlist_id`   — IntegerField (cross-service, stays plain)
- `token`         — UUIDField(default=uuid4, unique=True, editable=False)
- `created_by_id` — IntegerField (cross-service, stays plain)
- `is_active`     — BooleanField default=True
- `created_at`    — DateTimeField auto_now_add
- `expires_at`    — DateTimeField null=True blank=True

**Indexes:** on token, on (playlist_id, is_active).
**@property is_valid:** identical to InviteLink.

**KEY DIFFERENCE from InviteLink:**
- `InviteLink` token → joining creates a `Collaborator` record → user can
  add/remove/reorder tracks (edit access).
- `ShareLink` token → joining creates NO Collaborator record → user can only
  VIEW the playlist and listen to songs. Cannot modify anything.

**Endpoints:**
- `POST   /api/share/:playlist_id/create/`      — generate a share link
- `DELETE /api/share/:playlist_id/deactivate/`  — deactivate share link
- `GET    /api/share/view/:token/`              — validate token, return
                                                  playlist data (view-only)
- `GET    /api/share/health/`                   — health check

**Settings change:** Add `'shareapp'` to `INSTALLED_APPS` in collab settings.py
**URL change:** Add `path('api/share/', include('shareapp.urls'))` in collab urls.py

---

## 5. Commit Plan

Total commits: 3.
Commit 1 is the foundation. Commit 2 covers both core and collaboration
service schema updates (original Commits 2 and 3 merged into one).
Commit 3 is integration, cleanup, and documentation.
The auth service has no schema changes and does not get its own commit.

NO git commands are issued by the assistant. All git operations are done by Mesbah.

---

### COMMIT 1 — Documentation + New App Skeletons

**Scope:** Create the authoritative SCHEMA.md and introduce the two new apps
(historyapp, shareapp) fully implemented from day one. These apps are created
here rather than later because they have no dependency on the model changes
coming in Commit 2 beyond the existing Song model.

**Commit message:** `feat(docs+apps): add SCHEMA.md, historyapp in core, shareapp in collaboration`

#### Part A — docs/SCHEMA.md

File: `docs/SCHEMA.md`

Contents:
- Final schema for all 9 tables (with all modifications applied)
- Entity relationship diagram (text-based, ASCII)
- Complete field-by-field table definitions in Django model syntax
- Migration order with exact commands
- All business rules numbered
- Complete API endpoint list
- Storage architecture note (Supabase "songs" bucket)
- TypeScript types for frontend reference
- Naming conventions (Song vs Track distinction)

#### Part B — historyapp (Core Service)

Files to CREATE:
```
services/core/historyapp/__init__.py
services/core/historyapp/models.py            Play model
services/core/historyapp/serializers.py       PlaySerializer, SongSerializer import
services/core/historyapp/views.py             RecordPlayView, RecentPlaysView, health_check
services/core/historyapp/urls.py              URL patterns
services/core/historyapp/migrations/__init__.py
services/core/historyapp/migrations/0001_initial.py
```

Files to MODIFY:
```
services/core/core/settings.py    add 'historyapp' to INSTALLED_APPS
services/core/core/urls.py        add path('api/history/', include('historyapp.urls'))
```

#### Part C — shareapp (Collaboration Service)

Files to CREATE:
```
services/collaboration/shareapp/__init__.py
services/collaboration/shareapp/models.py           ShareLink model
services/collaboration/shareapp/serializers.py       ShareLinkSerializer
services/collaboration/shareapp/views.py             CreateShareLinkView, DeactivateShareLinkView,
                                                     ViewShareLinkView, health_check
services/collaboration/shareapp/urls.py              URL patterns
services/collaboration/shareapp/migrations/__init__.py
services/collaboration/shareapp/migrations/0001_initial.py
```

Files to MODIFY:
```
services/collaboration/core/settings.py    add 'shareapp' to INSTALLED_APPS
services/collaboration/core/urls.py        add path('api/share/', include('shareapp.urls'))
```

---

### COMMIT 2 — Core Service + Collaboration Service Schema Update

**Scope:** All schema changes across both the core service and the
collaboration service. This commit merges what was originally planned as
separate Commits 2 and 3 into a single commit.

**Core side:** Three Django apps updated (searchapp, playlistapp, trackapp).
The historyapp created in Commit 1 gains a correct migration dependency on
the updated Song model. All new serializers, views, and URLs are written.

**Collaboration side:** collabapp models updated (Collaborator role removed,
InviteLink is_valid added, indexes added). New endpoints added. The shareapp
created in Commit 1 is verified and any corrections applied.

**Commit message:** `feat(core+collab): update searchapp/playlistapp/trackapp schemas and collabapp models, add new endpoints`

**DB note:** If migrations from Commit 1 or before were already applied,
run `docker-compose down -v` before applying this commit to get a fresh DB.
This is necessary because the old trackapp_track and searchapp_song tables
are incompatible with the new schemas.

#### searchapp Changes

Files to MODIFY:
```
services/core/searchapp/models.py
```
- ADD `Artist` model (new)
- ADD `Album` model (new, FK to Artist, no max_songs)
- REWRITE `Song` model:
  - ADD artist ForeignKey (required)
  - ADD album ForeignKey (optional, null=True)
  - ADD storage_path, release_year
  - REMOVE flat artist/album CharField fields
  - ADD all indexes

```
services/core/searchapp/serializers.py
```
- ADD `ArtistSerializer`
- ADD `AlbumSerializer` (nests ArtistSerializer)
- REWRITE `SongSerializer` (nests ArtistSerializer + AlbumSerializer, handles null album)

```
services/core/searchapp/views.py
```
- UPDATE `SearchView`: add genre filter, add sort (title/artist/album/genre/
  duration/year), add order (asc/desc), limit 20, select_related
- UPDATE `BrowseView`: return distinct genres (unchanged concept)
- ADD `ArtistListView`: `GET /api/search/artists/?q=`
- ADD `ArtistDetailView`: `GET /api/search/artists/:id/`
- ADD `AlbumListView`: `GET /api/search/albums/?q=`
- ADD `AlbumDetailView`: `GET /api/search/albums/:id/`
- Keep `health_check`

```
services/core/searchapp/urls.py
```
- ADD routes for artists/ and albums/ list + detail

```
services/core/searchapp/migrations/0001_initial.py
```
- REPLACE entirely: new migration covers Artist, Album, Song in dependency order

#### playlistapp Changes

```
services/core/playlistapp/models.py
```
- REMOVE `snapshot_id`
- ADD `cover_url` URLField(500) default=''
- ADD `max_songs` IntegerField(default=0)
- CHANGE `description` to add default=''
- ADD Meta indexes on owner_id, name, created_at, updated_at, playlist_type

```
services/core/playlistapp/serializers.py
```
- REMOVE snapshot_id from fields
- ADD max_songs, cover_url to fields
- ADD validate() method: collaborative playlist must be private

```
services/core/playlistapp/views.py
```
- UPDATE get_queryset() to support ?sort= and ?order=
- keep owner_id enforcement

```
services/core/playlistapp/migrations/0001_initial.py
```
- REPLACE entirely: clean migration with new Playlist schema

#### trackapp Changes

```
services/core/trackapp/models.py
```
- REWRITE `Track` model:
  - REMOVE playlist_id IntegerField
  - REMOVE flat fields (title, artist, album, duration_seconds, cover_url, audio_url)
  - ADD playlist ForeignKey(Playlist, CASCADE, related_name='tracks')
  - ADD song ForeignKey(Song, CASCADE, related_name='playlist_entries')
  - KEEP added_by_id IntegerField
  - KEEP position IntegerField(default=0)
  - KEEP added_at DateTimeField(auto_now_add=True)
  - ADD unique_together = ('playlist', 'song')
  - ADD indexes: (playlist, position), (playlist, added_at), (added_by_id,)

```
services/core/trackapp/serializers.py
```
- REWRITE `TrackSerializer`: nest full SongSerializer in song field,
  expose playlist_id as read-only integer

```
services/core/trackapp/views.py
```
- UPDATE `TrackListView.get()`: add sort support (?sort=custom/title/artist/
  album/genre/duration/year/added_at, ?order=asc/desc)
- UPDATE `TrackListView.post()`: accept {song_id}, resolve Song, check
  unique_together, enforce max_songs if > 0, auto-assign position
- Keep `TrackDetailView.delete()` and `TrackReorderView.put()`
- Use select_related('song__artist', 'song__album') everywhere

```
services/core/trackapp/migrations/0001_initial.py
```
- REPLACE entirely: clean migration for new Track schema

#### historyapp Migration Update (Commit 1 → Commit 2 dependency fix)

```
services/core/historyapp/migrations/0001_initial.py
```
- UPDATE dependencies to reference new searchapp migration (not old flat Song)
- This is needed because Commit 1 created historyapp based on whatever Song
  existed then; Commit 2 replaces the Song migration entirely

---

#### collabapp Changes

```
services/collaboration/collabapp/models.py
```
- `Collaborator`: REMOVE role field and ROLE_CHOICES entirely
- `Collaborator`: ADD Meta indexes on playlist_id and user_id
- `InviteLink`: ADD @property is_valid (check is_active AND expires_at)
- `InviteLink`: ADD editable=False to token
- `InviteLink`: ADD Meta indexes on token and (playlist_id, is_active)

```
services/collaboration/collabapp/serializers.py
```
- `CollaboratorSerializer`: drop role field
- `InviteLinkSerializer`: add is_valid as SerializerMethodField (read-only)

```
services/collaboration/collabapp/views.py
```
- Keep `GenerateInviteView` (unchanged)
- Update `JoinView.post()`: check already_member → return 200 + {"error":"already_member"}
- Keep `CollaboratorListView` (drop role from output)
- ADD `MyCollaborationsView`:
    GET /api/collab/my-collaborations/
    Returns all playlist_ids where request.user.id appears as a Collaborator
- ADD `MyRoleView`:
    GET /api/collab/:playlist_id/my-role/
    Checks if Collaborator record exists for user+playlist
    Returns {"role": "collaborator"} or 404 if not a collaborator
    (Owner check handled client-side by comparing playlist.owner_id)
- ADD `DeactivateInviteView`:
    DELETE
 /api/collab/:playlist_id/invite/deactivate/
    Sets is_active=False on the active InviteLink for this playlist
- Keep `HealthCheckView`

```
services/collaboration/collabapp/urls.py
```
- ADD routes: my-collaborations/, :playlist_id/invite/deactivate/, :playlist_id/my-role/

```
services/collaboration/collabapp/migrations/0001_initial.py
```
- REPLACE entirely: clean migration with role removed from Collaborator
  and indexes added to both Collaborator and InviteLink

#### shareapp Verification

```
services/collaboration/shareapp/
```
- Verify all files from Commit 1 are correct
- Apply any corrections to models, serializers, views, urls identified
  during Commit 2 work

---

### COMMIT 3 — Expiry Defaults, Endpoint Removal, Cleanup, and Documentation Update

**Scope:** Two categories of work in one commit.

**Category A — InviteLink and ShareLink behaviour change:**
Both token models previously had an optional `expires_at` field. The design
is now finalised: links expire automatically after 30 days from creation.
Manual deactivation via an API endpoint is removed entirely.

- `InviteLink.expires_at` — changed from `null=True, blank=True` to
  `default=default_expires_at` (30 days from now). Non-nullable.
- `ShareLink.expires_at` — same change.
- `InviteLink.is_valid` — simplified to `is_active and now <= expires_at`.
- `ShareLink.is_valid` — same simplification.
- `DeactivateInviteView` removed from collabapp views and urls.
- `DeactivateShareLinkView` removed from shareapp views and urls.

**Category B — Integration, cleanup, and documentation:**
Cross-cutting verification and documentation update to reflect the final
state of the codebase after all schema work.

**Commit message:** `feat(collab+core): auto-expire links after 30 days, fix trackapp races and reorder-remove, playlistapp field fixes, regenerate all migrations; update docs`

#### Category A — collabapp Changes

```
services/collaboration/collabapp/models.py
```
- ADD `default_expires_at()` function: `timezone.now() + timedelta(days=30)`
- CHANGE `InviteLink.expires_at`: remove `null=True, blank=True`,
  add `default=default_expires_at`
- SIMPLIFY `InviteLink.is_valid`: `return self.is_active and timezone.now() <= self.expires_at`

```
services/collaboration/collabapp/views.py
```
- REMOVE `DeactivateInviteView` class entirely

```
services/collaboration/collabapp/urls.py
```
- REMOVE `<int:playlist_id>/invite/deactivate/` route and import

```
services/collaboration/collabapp/migrations/0001_initial.py
```
- REPLACE: `expires_at` is now `DateTimeField(default=default_expires_at)`,
  no longer nullable

#### Category A — shareapp Changes

```
services/collaboration/shareapp/models.py
```
- ADD `default_expires_at()` function (same as collabapp)
- CHANGE `ShareLink.expires_at`: same change as InviteLink
- SIMPLIFY `ShareLink.is_valid`: same simplification

```
services/collaboration/shareapp/views.py
```
- REMOVE `DeactivateShareLinkView` class entirely

```
services/collaboration/shareapp/urls.py
```
- REMOVE `<int:playlist_id>/deactivate/` route and import

```
services/collaboration/shareapp/migrations/0001_initial.py
```
- REPLACE: `expires_at` is now `DateTimeField(default=default_expires_at)`

#### Category B — Core Service Bug Fixes & Model Corrections

```
services/core/playlistapp/models.py
```
- CHANGE `description`: add `blank=True` (was `default=''` only — DRF form validation
  would reject empty string without blank=True)
- CHANGE `max_songs`: `IntegerField` → `PositiveIntegerField` (negative values are invalid)

```
services/core/trackapp/models.py
```
- ADD comment block on Meta class explaining the (playlist, position) index role
  and the unique constraint's purpose in the reorder-remove workflow

```
services/core/trackapp/views.py
```
- WRAP `TrackListView.post()` in `transaction.atomic()` with
  `Playlist.objects.select_for_update()` to prevent race conditions on concurrent
  add-track requests. Add `IntegrityError` catch as a safety net.
- RENAME `TrackReorderView` → `TrackReorderRemoveView`; implement reorder-remove:
  tracks absent from the submitted `track_ids` list are deleted atomically before
  positions are reassigned.

```
services/core/trackapp/urls.py
```
- UPDATE import and route to reference `TrackReorderRemoveView`

```
services/collaboration/collabapp/views.py
```
- ADD TODO comment block on `CollaboratorListView.delete()` documenting the missing
  owner/admin authorization check and cross-service verification requirement

#### Category C — Migration Regeneration

```
services/core/searchapp/migrations/0001_initial.py         (deleted + regenerated)
services/core/playlistapp/migrations/0001_initial.py       (deleted + regenerated)
services/core/trackapp/migrations/0001_initial.py          (deleted + regenerated)
services/core/historyapp/migrations/0001_initial.py        (deleted + regenerated)
services/collaboration/collabapp/migrations/0001_initial.py (deleted + regenerated)
services/collaboration/shareapp/migrations/0001_initial.py  (deleted + regenerated)
```
All handwritten migration files were deleted and regenerated via
`docker-compose exec <svc> uv run python manage.py makemigrations <app>`
to ensure migrations are always auto-generated and consistent with the models,
not hand-maintained.

#### Category D — Documentation Updates

```
docs/AGENT-GUIDE.md
```
- Update service architecture section: add historyapp and shareapp to core/collab
  directory trees with descriptions
- Update health check commands: add search, history, share endpoints
- Update recommended reading order: point to latest session + SCHEMA.md

```
docs/MIGRATION-WORKFLOW.md
```
- ADD "Schema Overhaul: DB Reset Requirement" section explaining when and
  how to reset the DB, with explicit migration order commands for core service

```
docs/CONTRIBUTING.md
```
- REWRITE service-specific guidelines:
  - Auth: JWT + built-in User note
  - Core: table of all 4 apps with responsibilities; naming convention reminder
  - Collaboration: table of both apps; 30-day expiry note; is_valid usage rule

---

## 6. File-by-File Change Summary

Quick lookup table: every file that will be touched and in which commit.
AUTH files are omitted — no changes to the auth service.

| File | Commit | Change Type |
|------|--------|-------------|
| `docs/SCHEMA.md` | 1 | CREATE |
| `services/core/historyapp/__init__.py` | 1 | CREATE |
| `services/core/historyapp/models.py` | 1 | CREATE |
| `services/core/historyapp/serializers.py` | 1 | CREATE |
| `services/core/historyapp/views.py` | 1 | CREATE |
| `services/core/historyapp/urls.py` | 1 | CREATE |
| `services/core/historyapp/migrations/__init__.py` | 1 | CREATE |
| `services/core/historyapp/migrations/0001_initial.py` | 1+2 | CREATE then UPDATE |
| `services/core/core/settings.py` | 1 | MODIFY (add historyapp) |
| `services/core/core/urls.py` | 1 | MODIFY (add history urls) |
| `services/collaboration/shareapp/__init__.py` | 1 | CREATE |
| `services/collaboration/shareapp/models.py` | 1 | CREATE |
| `services/collaboration/shareapp/serializers.py` | 1 | CREATE |
| `services/collaboration/shareapp/views.py` | 1 | CREATE |
| `services/collaboration/shareapp/urls.py` | 1 | CREATE |
| `services/collaboration/shareapp/migrations/__init__.py` | 1 | CREATE |
| `services/collaboration/shareapp/migrations/0001_initial.py` | 1 | CREATE |
| `services/collaboration/core/settings.py` | 1 | MODIFY (add shareapp) |
| `services/collaboration/core/urls.py` | 1 | MODIFY (add share urls) |
| `services/core/searchapp/models.py` | 2 | OVERWRITE |
| `services/core/searchapp/serializers.py` | 2 | OVERWRITE |
| `services/core/searchapp/views.py` | 2 | OVERWRITE |
| `services/core/searchapp/urls.py` | 2 | MODIFY (add artist/album routes) |
| `services/core/searchapp/migrations/0001_initial.py` | 2 | REPLACE |
| `services/core/playlistapp/models.py` | 2 | MODIFY |
| `services/core/playlistapp/serializers.py` | 2 | MODIFY |
| `services/core/playlistapp/views.py` | 2 | MODIFY |
| `services/core/playlistapp/migrations/0001_initial.py` | 2 | REPLACE |
| `services/core/trackapp/models.py` | 2 | OVERWRITE |
| `services/core/trackapp/serializers.py` | 2 | OVERWRITE |
| `services/core/trackapp/views.py` | 2 | OVERWRITE |
| `services/core/trackapp/migrations/0001_initial.py` | 2 | REPLACE |
| `services/collaboration/collabapp/models.py` | 2 | MODIFY |
| `services/collaboration/collabapp/serializers.py` | 2 | MODIFY |
| `services/collaboration/collabapp/views.py` | 2 | MODIFY |
| `services/collaboration/collabapp/urls.py` | 2 | MODIFY |
| `services/collaboration/collabapp/migrations/0001_initial.py` | 2 | REPLACE |
| `services/collaboration/collabapp/models.py` | 3 | MODIFY (expires_at default, is_valid simplified) |
| `services/collaboration/collabapp/views.py` | 3 | MODIFY (remove DeactivateInviteView; add TODO on delete auth) |
| `services/collaboration/collabapp/urls.py` | 3 | MODIFY (remove deactivate route) |
| `services/collaboration/collabapp/migrations/0001_initial.py` | 3 | REGENERATED |
| `services/collaboration/shareapp/models.py` | 3 | MODIFY (expires_at default, is_valid simplified) |
| `services/collaboration/shareapp/views.py` | 3 | MODIFY (remove DeactivateShareLinkView) |
| `services/collaboration/shareapp/urls.py` | 3 | MODIFY (remove deactivate route) |
| `services/collaboration/shareapp/migrations/0001_initial.py` | 3 | REGENERATED |
| `services/core/playlistapp/models.py` | 3 | MODIFY (description blank=True; max_songs PositiveIntegerField) |
| `services/core/playlistapp/migrations/0001_initial.py` | 3 | REGENERATED |
| `services/core/trackapp/models.py` | 3 | MODIFY (Meta comment) |
| `services/core/trackapp/views.py` | 3 | MODIFY (transaction.atomic + TrackReorderRemoveView) |
| `services/core/trackapp/urls.py` | 3 | MODIFY (import rename) |
| `services/core/trackapp/migrations/0001_initial.py` | 3 | REGENERATED |
| `services/core/searchapp/migrations/0001_initial.py` | 3 | REGENERATED |
| `services/core/historyapp/migrations/0001_initial.py` | 3 | REGENERATED |
| `docs/AGENT-GUIDE.md` | 3 | MODIFY |
| `docs/MIGRATION-WORKFLOW.md` | 3 | MODIFY |
| `docs/CONTRIBUTING.md` | 3 | MODIFY |

---

## 7. Key Technical Notes and Constraints

### Migration Order Within Core Service

When running makemigrations inside the core service, the dependency order is:

```
searchapp  (Artist → Album → Song)
    ↓                 ↓
playlistapp (
Playlist — no FK to searchapp, can run in parallel)
    ↓
trackapp (Track — FKs to BOTH Playlist and Song, must run after both)
    ↓
historyapp (Play — FK to Song, must run after searchapp)
```

Exact commands (in order):
```bash
docker-compose exec core uv run python manage.py makemigrations searchapp
docker-compose exec core uv run python manage.py makemigrations playlistapp
docker-compose exec core uv run python manage.py makemigrations trackapp
docker-compose exec core uv run python manage.py makemigrations historyapp
docker-compose exec core uv run python manage.py migrate
```

### Database Reset Before Commit 2

The trackapp Track model and searchapp Song model are being fundamentally
restructured. Django cannot auto-generate migrations from incompatible changes
cleanly. The safest approach is a fresh database before applying Commit 2.

Steps (Mesbah runs these, not the assistant):
```bash
docker-compose down -v      # removes volumes including all DB data
docker-compose up -d        # fresh DB, entrypoints auto-run all migrations
```

After `docker-compose up -d` on a fresh DB, all migrations run automatically
via the entrypoint scripts (RUN_MIGRATIONS=true in development).

### Valid Cross-App Imports Within Core Service

These imports are VALID — all apps share one Django project:
```python
# trackapp/models.py
from playlistapp.models import Playlist
from searchapp.models import Song

# historyapp/models.py
from searchapp.models import Song

# historyapp/serializers.py
from searchapp.serializers import SongSerializer

# trackapp/serializers.py
from searchapp.serializers import SongSerializer
```

### Invalid Cross-Service Imports (NEVER write these)

```python
# WRONG — collaboration service cannot import from core service
from playlistapp.models import Playlist

# WRONG — core service cannot import from auth service
from django.contrib.auth.models import User   # (as a ForeignKey target)
```

### The is_valid Property Pattern

Both `InviteLink.is_valid` and `ShareLink.is_valid` use identical logic:

```python
@property
def is_valid(self):
    if not self.is_active:
        return False
    if self.expires_at and timezone.now() > self.expires_at:
        return False  # Commit 2 of Mesbah — null guard present; expires_at was optional
    return True       # Commit 3 of Mesbah — simplified: null guard removed, expires_at always set
```

Expose in serializer via SerializerMethodField:
```python
is_valid = serializers.SerializerMethodField()
def get_is_valid(self, obj):
    return obj.is_valid
```

### Null Album Handling in SongSerializer

Song.album is nullable. The serializer must handle this:
```python
class SongSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer(read_only=True)
    album  = AlbumSerializer(read_only=True, allow_null=True)

    class Meta:
        model  = Song
        fields = ['id', 'title', 'artist', 'album', 'genre',
                  'release_year', 'duration_seconds',
                  'cover_url', 'audio_url', 'storage_path']
```

JSON output when album is None: `"album": null`
JSON output when album exists: `"album": { "id": 1, "name": "After Hours", ... }`

### max_songs Enforcement (Playlist only, not Album)

Album has NO max_songs field. Only Playlist has it.
Enforcement happens in `trackapp/views.py` add-track endpoint only.
A value of 0 means unlimited (no enforcement).

### Track Model — Naming Reminder

The model class is `Track`. The table is `trackapp_track`.
Do not use `PlaylistTrack` anywhere in code, migrations, comments, or docs.
The semantic distinction is captured by the field names (playlist FK, song FK).

---

## 8. Out of Scope for This Work

The following items are NOT part of this plan:

- Spotify API integration (no external API calls)
- Real-time monthly_listeners aggregation (seeded static values)
- Frontend changes
- WebSocket / real-time updates
- Email verification or password reset
- Rate limiting or caching
- File upload endpoints (audio managed directly via Supabase)
- Django admin panel customisation

---

## 9. Session Workflow for Future Prompts

Every future coding session MUST follow this order:

1. Read this file (MESBAH_PROGRESS_PLAN.md)
2. Read docs/SCHEMA.md once it exists (after Commit 1 Part A)
3. Identify which commit number is being implemented
4. Read the specific service files being modified BEFORE editing
5. Make changes following the plan exactly
6. Report which files were changed and what to commit
7. NEVER issue git commands

---

**Last updated:** 2026-03-27
**Status:** ALL COMMITS DONE — schema overhaul complete