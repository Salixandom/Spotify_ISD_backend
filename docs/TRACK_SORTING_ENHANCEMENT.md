# Track Sorting & Collaborator Access Enhancement

**Implemented:** 2026-03-30
**Developer:** Taskeen Towfique (2105122)
**Affected Apps:** playlistapp, trackapp

---

## 📋 Summary

Added persistent track sorting functionality and collaborator access control for playlist track management. This fills the gap between display-only sorting (GET) and persistent sorting (PUT) with proper authorization for both owners and collaborators.

---

## ✅ What Was Implemented

### 1. Track Sorting Endpoint (Persistent)
**File:** `trackapp/views.py` — Added `TrackSortView`

**Endpoint:** `PUT /api/tracks/{playlist_id}/sort/`

**Features:**
- Sorts tracks by any field and **persists** the order
- Updates `position` field for all tracks
- Uses bulk_update for efficiency
- Transaction.atomic() for data integrity

**Request Body:**
```json
{
  "sort_by": "title|artist|album|genre|duration|year|added_at|custom",
  "order": "asc|desc"
}
```

**Response:**
```json
{
  "message": "Playlist sorted by title (asc)",
  "sort_by": "title",
  "order": "asc",
  "tracks_updated": 50,
  "tracks": [...]
}
```

### 2. Collaborator Authorization
**File:** `trackapp/views.py` — Added `_can_edit_playlist()` helper

**Features:**
- Checks if user is owner OR collaborator
- Integrates with collabapp.Collaborator model
- Used in TrackSortView and TrackReorderRemoveView

**Authorization Logic:**
```python
def _can_edit_playlist(playlist_id, user_id):
    # Check if owner
    if playlist.owner_id == user_id:
        return playlist, None

    # Check if collaborator
    from collaboration.collabapp.models import Collaborator
    try:
        Collaborator.objects.get(playlist_id=playlist_id, user_id=user_id)
        return playlist, None
    except Collaborator.DoesNotExist:
        return None, Response({'error': 'Not authorized'}, 403)
```

### 3. Updated TrackReorderRemoveView
**File:** `trackapp/views.py` — Updated authorization

**Changes:**
- Now allows collaborators (not just owners)
- Uses `_can_edit_playlist()` instead of `_require_playlist_owner()`
- Maintains existing reorder-remove functionality

### 4. Integrated Collaborator Count
**File:** `playlistapp/views.py` — Updated `PlaylistStatsView`

**Changes:**
- Now queries `collabapp.Collaborator` for real count
- Removed TODO placeholder
- Falls back to 0 if collabapp not available

---

## 🔄 Sorting System Architecture

### Display-Only Sorting (Already Existed)
**Endpoint:** `GET /api/tracks/{playlist_id}/?sort=title&order=asc`

**Behavior:**
- Sorts tracks for display
- Does NOT persist the order
- Next request returns to original order
- Used for temporary viewing

### Persistent Sorting (New)
**Endpoint:** `PUT /api/tracks/{playlist_id}/sort/`

**Behavior:**
- Sorts tracks by field
- **Updates position** field in database
- Order persists across requests
- Changes the default/custom order

**Use Cases:**
- User wants to alphabetize tracks
- User wants to sort by duration (shortest to longest)
- User wants to sort by artist name
- User wants to sort by recently added

### Manual Reordering (Already Existed)
**Endpoint:** `PUT /api/tracks/{playlist_id}/reorder/`

**Behavior:**
- Drag-and-drop reordering
- Full control over track order
- Persists new positions
- Can also remove tracks

---

## 📊 Available Sort Fields

| Field | Description | Example |
|-------|-------------|---------|
| `custom` | Current manual order (position) | Default |
| `title` | Song title | A-Z, Z-A |
| `artist` | Artist name | A-Z, Z-A |
| `album` | Album name | A-Z, Z-A |
| `genre` | Music genre | Pop, Rock, Jazz... |
| `duration` | Song length (seconds) | Shortest to longest |
| `year` | Release year | Oldest to newest |
| `added_at` | When added to playlist | First added to last |

---

## 🔐 Authorization Model

### Who Can Sort/Reorder Tracks?

| User Type | Can View | Can Add Tracks | Can Sort | Can Reorder | Can Remove |
|-----------|----------|---------------|----------|-------------|------------|
| **Owner** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Collaborator** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Follower** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Public (other)** | ✅ (if public) | ❌ | ❌ | ❌ | ❌ |

### Collaborator Model

**From:** `collaboration.collabapp.models.Collaborator`

```python
class Collaborator(models.Model):
    playlist_id = models.IntegerField()
    user_id     = models.IntegerField()
    joined_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('playlist_id', 'user_id')
```

**How Users Become Collaborators:**
1. Owner generates invite link (collabapp)
2. User joins via invite token
3. Added to Collaborator table
4. Gains edit access to playlist

---

## 🎯 Use Cases

### 1. Alphabetize Playlist
```http
PUT /api/tracks/{playlist_id}/sort/
Content-Type: application/json

{
  "sort_by": "title",
  "order": "asc"
}
```

### 2. Sort by Duration (Workout Mix)
```http
PUT /api/tracks/{playlist_id}/sort/
Content-Type: application/json

{
  "sort_by": "duration",
  "order": "asc"
}
```

### 3. Reverse Chronological (Recently Added)
```http
PUT /api/tracks/{playlist_id}/sort/
Content-Type: application/json

{
  "sort_by": "added_at",
  "order": "desc"
}
```

### 4. Collaborator Reorders Tracks
```http
PUT /api/tracks/{playlist_id}/reorder/
Content-Type: application/json

{
  "track_ids": [5, 2, 8, 1, 3]
}
```

---

## 📈 Performance Considerations

### TrackSortView Optimization

**Efficient Updates:**
```python
# Uses bulk_update instead of individual saves
Track.objects.bulk_update(track_updates, ['position'])

# Reduces N database queries to 1 query
```

**Transaction Safety:**
```python
with transaction.atomic():
    # All or nothing - no partial updates
    # Prevents race conditions
```

**Memory Efficient:**
```python
# Uses select_related to avoid N+1 queries
tracks = Track.objects.filter(playlist=playlist).select_related(
    'song', 'song__artist', 'song__album'
)
```

---

## ✅ Testing & Validation

### Django System Check
```bash
docker exec spotify_isd_backend-core-1 uv run python manage.py check playlistapp trackapp
```
**Result:** ✅ No issues found

### Manual Testing Steps

1. **Create collaborative playlist**
2. **Add collaborator via invite link**
3. **Add tracks to playlist**
4. **Test sorting as owner**
5. **Test sorting as collaborator**
6. **Verify order persists across requests**
7. **Test reordering via drag-drop**

---

## 🔄 Consistency Check: trackapp vs playlistapp

### ✅ No Redundancy Found

**playlistapp responsibilities:**
- Playlist CRUD operations
- Playlist metadata (name, description, visibility)
- Playlist-level features (follow, like, duplicate)
- Playlist statistics
- Snapshots/versioning of playlists

**trackapp responsibilities:**
- Track CRUD operations
- Add tracks to playlists
- Remove tracks from playlists
- **Sort tracks** (display-only)
- **Reorder tracks** (manual drag-drop)
- **Sort and persist tracks** (NEW)
- Track hiding (per-user)

**collabapp responsibilities:**
- Collaborator management
- Invite links
- Collaboration state

**Clear separation of concerns!** ✅

---

## 📝 Files Modified

### trackapp
- `views.py` — Added `_can_edit_playlist()`, added `TrackSortView`, updated `TrackReorderRemoveView`
- `urls.py` — Registered `/sort/` endpoint

### playlistapp
- `views.py` — Integrated with collabapp for collaborator_count
- No model changes (uses existing Collaborator from collabapp)

---

## 🚀 Git Commit

```bash
git add services/core/trackapp/
git add services/core/playlistapp/views.py
git commit -m "feat(track, playlist): Add persistent track sorting and collaborator access

- Add TrackSortView for persistent track sorting
- Add _can_edit_playlist() helper for collaborator authorization
- Update TrackReorderRemoveView to allow collaborators
- Integrate playlistapp with collabapp for collaborator count
- Register /sort/ endpoint in trackapp URLs
- Enable both owner and collaborators to sort/reorder tracks
- Support 8 sort fields: custom, title, artist, album, genre, duration, year, added_at
- Use bulk_update for efficient position updates
- Transaction.atomic() for data integrity
"
```

---

## 📊 API Endpoints Summary

### Track Sorting & Reordering

| Method | Endpoint | Description | Access |
|--------|----------|-------------|--------|
| GET | `/api/tracks/{id}/?sort=field&order=dir` | Display sort (temporary) | All users |
| PUT | `/api/tracks/{id}/sort/` | Sort and persist (permanent) | Owner + Collab |
| PUT | `/api/tracks/{id}/reorder/` | Manual reorder (drag-drop) | Owner + Collab |
| DELETE | `/api/tracks/{id}/remove/` | Batch remove tracks | Owner |
| DELETE | `/api/tracks/{id}/{track_id}/` | Remove single track | Owner |

---

**Status:** ✅ Complete and Ready for Testing
**Next Steps:** Test with frontend drag-drop interface
