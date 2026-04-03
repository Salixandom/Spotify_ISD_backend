# Collaboration Invite Flow - Fixes Applied

## Issues Fixed

### Issue 1: Invite Modal Shows "Unknown Playlist"
**Root Cause:** The collaboration service was trying to fetch playlist details from the core service using the wrong port (8000 instead of 8002).

**Fixes Applied:**
1. **Updated default port** in `/services/collaboration/collabapp/views.py`:
   - Changed all occurrences of `os.getenv('CORE_SERVICE_URL', 'http://core:8000')` to `os.getenv('CORE_SERVICE_URL', 'http://core:8002')`
   - This affects 5 locations in the file:
     - Line 65: JoinView GET method
     - Line 185: Auto-follow playlist method
     - Line 208: Update playlist type method
     - Line 289: CollaboratorListView DELETE method
     - Line 336: MyRoleView GET method

2. **Added authentication header forwarding** in JoinView GET method (line 67-78):
   ```python
   auth_header = request.META.get('HTTP_AUTHORIZATION', '')
   headers = {}
   if auth_header:
       headers['Authorization'] = auth_header

   response = requests.get(
       f'{core_service_url}/api/playlists/{invite.playlist_id}/',
       headers=headers,
       timeout=5
   )
   ```

3. **Added comprehensive debug logging** to track API calls:
   - Added logging for core service response status
   - Added logging for response structure
   - Added logging for playlist name and type extraction

### Issue 2: Playlist Shows as "Solo" Instead of "Collaborative"
**Root Cause:** The `_update_playlist_type_to_collaborative` method was calling the core service without authentication headers, causing 401 errors and silent failures.

**Fixes Applied:**
1. **Modified method signature** to accept auth_header parameter (line 210):
   ```python
   def _update_playlist_type_to_collaborative(self, playlist_id, auth_header=''):
   ```

2. **Updated method call** in POST method to pass auth headers (line 168):
   ```python
   auth_header = request.headers.get('Authorization', '')
   self._update_playlist_type_to_collaborative(invite.playlist_id, auth_header)
   ```

3. **Added auth headers to both GET and PATCH requests** in the update method (lines 220-246):
   ```python
   headers = {}
   if auth_header:
       headers['Authorization'] = auth_header

   # GET request to check current type
   response = requests.get(
       f'{core_service_url}/api/playlists/{playlist_id}/',
       headers=headers,
       timeout=5
   )

   # PATCH request to update type
   update_response = requests.patch(
       f'{core_service_url}/api/playlists/{playlist_id}/',
       json={'playlist_type': 'collaborative'},
       headers=headers,
       timeout=5
   )
   ```

4. **Enhanced logging** to track the update process:
   - Log when update attempt starts
   - Log current playlist type
   - Log update response status and content
   - Log success or failure

## Environment Configuration

### Verified Correct Settings:
- **Core Service URL**: `http://core:8002` (confirmed in `/services/collaboration/.env`)
- **Collaboration Service Port**: `8003`
- **Auth Service Port**: `8001`
- **Playback Service Port**: `8004`

All services are properly configured in `docker-compose.yml` with the correct port mappings.

## Testing Recommendations

### To Verify Issue 1 is Fixed:
1. Access an invite link (e.g., `/invite/{token}`)
2. The modal should display the actual playlist name instead of "Unknown Playlist"
3. Check collaboration service logs for:
   - "Core service response status: 200"
   - "Playlist name: [actual name]"
   - "Playlist type: collaborative"

### To Verify Issue 2 is Fixed:
1. Accept a collaboration invite for a solo playlist
2. After accepting, check the playlist details
3. The playlist type should show as "collaborative"
4. Check collaboration service logs for:
   - "Attempting to update playlist {id} to collaborative type"
   - "Current playlist type: solo"
   - "Successfully updated playlist {id} type to collaborative"

## Files Modified

1. **`/services/collaboration/collabapp/views.py`**
   - Fixed port number from 8000 to 8002 (5 occurrences)
   - Added auth header forwarding in JoinView GET method
   - Modified `_update_playlist_type_to_collaborative` to accept and use auth headers
   - Enhanced logging throughout

## Service Status

All services are running correctly:
- ✅ Core service (port 8002)
- ✅ Collaboration service (port 8003)
- ✅ Auth service (port 8001)
- ✅ Playback service (port 8004)

## Next Steps

The collaboration service has been restarted with all fixes applied. The invite flow should now work correctly:

1. User clicks invite link
2. Frontend calls GET `/api/collab/join/{token}/` with auth headers
3. Collaboration service forwards request to core service with auth headers
4. Core service returns playlist details (including name and type)
5. Modal displays actual playlist name
6. User accepts invite
7. Collaboration service updates playlist type to "collaborative" in core service
8. Playlist now shows as collaborative

---

**Date:** 2026-04-04
**Fixed by:** Claude Code (General Purpose Agent)
