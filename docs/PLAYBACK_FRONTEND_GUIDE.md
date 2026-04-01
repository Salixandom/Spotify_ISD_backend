# Playback Frontend Guide

## API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/playback/upload/` | JWT required | Upload an audio file (multipart/form-data) |
| `GET` | `/api/playback/files/` | JWT required | List all uploaded audio files |
| `GET` | `/api/playback/stream/<id>/` | None | Stream an audio file |
| `GET` | `/api/playback/health/` | None | Health check |

### Upload Request

```
POST /api/playback/upload/
Content-Type: multipart/form-data
Authorization: Bearer <jwt_token>

Fields:
  - title (string, required): Song title
  - artist (string, optional): Artist name
  - file (file, required): Audio file (.mp3, .wav, .ogg, .m4a)
  - duration_seconds (integer, optional): Duration in seconds
```

### Upload Response

```json
{
  "success": true,
  "message": "Audio file uploaded successfully",
  "data": {
    "id": 1,
    "title": "My Song",
    "artist": "Artist Name",
    "file": "/api/playback/media/audio/my_song.mp3",
    "duration_seconds": 180,
    "uploaded_by_id": 1,
    "created_at": "2026-04-01T12:00:00Z"
  }
}
```

### List Response

```json
{
  "success": true,
  "message": "Retrieved 2 audio files",
  "data": [
    {
      "id": 1,
      "title": "My Song",
      "artist": "Artist Name",
      "file": "/api/playback/media/audio/my_song.mp3",
      "duration_seconds": 180,
      "uploaded_by_id": 1,
      "created_at": "2026-04-01T12:00:00Z"
    }
  ]
}
```

### Stream Endpoint

`GET /api/playback/stream/<id>/` returns the raw audio file with the appropriate `Content-Type` header (e.g., `audio/mpeg` for MP3). No authentication required — this allows the browser's `<audio>` element to fetch the file directly.

The server sends the **entire file** in one response. The browser buffers it fully, which means **seeking (jumping to any position) works out of the box** — forward, backward, anywhere. No special backend support is needed for this.

---

## Playing Audio in React

The browser has a built-in audio engine via the HTML5 `<audio>` element and the `Audio` Web API. No external libraries are needed.

### Option 1: Simple `<audio>` Element

The simplest approach — the browser renders its own play/pause/seek controls:

```jsx
function Player({ trackId }) {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  return (
    <audio controls src={`${baseUrl}/api/playback/stream/${trackId}/`} />
  );
}
```

### Option 2: Custom Controls with useRef

For a custom UI with play, pause, and seek:

```jsx
import { useRef, useState, useEffect } from 'react';

function AudioPlayer({ trackId }) {
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const baseUrl = import.meta.env.VITE_API_URL || '';

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const updateTime = () => setCurrentTime(audio.currentTime);
    const updateDuration = () => setDuration(audio.duration);
    const onEnded = () => setIsPlaying(false);

    audio.addEventListener('timeupdate', updateTime);
    audio.addEventListener('loadedmetadata', updateDuration);
    audio.addEventListener('ended', onEnded);

    return () => {
      audio.removeEventListener('timeupdate', updateTime);
      audio.removeEventListener('loadedmetadata', updateDuration);
      audio.removeEventListener('ended', onEnded);
    };
  }, [trackId]);

  const togglePlay = () => {
    const audio = audioRef.current;
    if (isPlaying) {
      audio.pause();
    } else {
      audio.play();
    }
    setIsPlaying(!isPlaying);
  };

  const handleSeek = (e) => {
    const audio = audioRef.current;
    audio.currentTime = Number(e.target.value);
  };

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div>
      <audio ref={audioRef} src={`${baseUrl}/api/playback/stream/${trackId}/`} />

      <button onClick={togglePlay}>
        {isPlaying ? 'Pause' : 'Play'}
      </button>

      <span>{formatTime(currentTime)}</span>

      <input
        type="range"
        min={0}
        max={duration || 0}
        value={currentTime}
        onChange={handleSeek}
      />

      <span>{formatTime(duration)}</span>
    </div>
  );
}
```

### Option 3: Upload and Play

```jsx
async function uploadSong(file, title, artist, token) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('title', title);
  if (artist) formData.append('artist', artist);

  const res = await fetch('/api/playback/upload/', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });

  const json = await res.json();
  return json.data; // { id, title, artist, file, ... }
}

// Usage in a component:
function UploadAndPlay({ token }) {
  const [trackId, setTrackId] = useState(null);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const data = await uploadSong(file, file.name, '', token);
    setTrackId(data.id);
  };

  return (
    <div>
      <input type="file" accept="audio/*" onChange={handleUpload} />
      {trackId && (
        <audio controls src={`/api/playback/stream/${trackId}/`} autoPlay />
      )}
    </div>
  );
}
```

### Option 4: Fetch All Songs and Build a Playlist

```jsx
function Playlist({ token }) {
  const [songs, setSongs] = useState([]);
  const [currentId, setCurrentId] = useState(null);

  useEffect(() => {
    fetch('/api/playback/files/', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(res => res.json())
      .then(json => setSongs(json.data));
  }, [token]);

  return (
    <div>
      <ul>
        {songs.map(song => (
          <li key={song.id} onClick={() => setCurrentId(song.id)}>
            {song.title} — {song.artist || 'Unknown'}
          </li>
        ))}
      </ul>

      {currentId && (
        <audio controls autoPlay src={`/api/playback/stream/${currentId}/`} />
      )}
    </div>
  );
}
```

## Seeking

Seeking (jumping to any position in the track) works easily from the frontend. Because the backend sends the **entire audio file** in one response, the browser has the full file buffered — so it can seek to any timestamp instantly without making a new request to the server.

### How to Seek

Set `audio.currentTime` to any value between `0` and `audio.duration`:

```js
// Jump to 30 seconds
audio.currentTime = 30;

// Jump to halfway through the track
audio.currentTime = audio.duration / 2;

// Rewind 10 seconds
audio.currentTime = Math.max(0, audio.currentTime - 10);

// Skip forward 10 seconds
audio.currentTime = Math.min(audio.duration, audio.currentTime + 10);
```

### Seek Bar with an `<input type="range">`

The standard approach is a range slider that maps to the audio duration. This is already shown in **Option 2** above, but here it is in isolation:

```jsx
// Render the seek bar
<input
  type="range"
  min={0}
  max={duration}        // audio.duration in seconds
  value={currentTime}   // audio.currentTime in seconds
  onChange={(e) => {
    audioRef.current.currentTime = Number(e.target.value);
  }}
  step={0.1}            // optional: finer granularity
/>
```

The `timeupdate` event fires as the audio plays, keeping `currentTime` in sync with the slider position automatically.

### Skip Buttons

```jsx
const skip = (seconds) => {
  const audio = audioRef.current;
  audio.currentTime = Math.min(Math.max(0, audio.currentTime + seconds), audio.duration);
};

<button onClick={() => skip(-10)}>-10s</button>
<button onClick={() => skip(10)}>+10s</button>
```

## Key Browser Audio API Methods

| Method/Property | Description |
|----------------|-------------|
| `audio.play()` | Start playback |
| `audio.pause()` | Pause playback |
| `audio.currentTime` | Get/set current position (seconds) |
| `audio.duration` | Total duration (seconds, read-only) |
| `audio.volume` | Get/set volume (0.0 to 1.0) |
| `audio.muted` | Get/set muted state |
| `audio.ended` | Whether playback has finished |
| `audio.playbackRate` | Get/set speed (1.0 = normal) |

## Events to Listen For

| Event | Fires When |
|-------|-----------|
| `play` | Playback starts |
| `pause` | Playback pauses |
| `ended` | Playback finishes |
| `timeupdate` | Current time changes (fires frequently) |
| `loadedmetadata` | Duration and other metadata is available |
| `error` | An error occurs loading/playing |

## Notes

- The stream endpoint (`/api/playback/stream/<id>/`) requires no authentication, so `<audio src="...">` works directly without custom headers.
- Supported audio formats: `.mp3`, `.wav`, `.ogg`, `.m4a`. MP3 has the widest browser support.
- Seeking works out of the box — the server returns the full file, so the browser can jump to any position freely.
- Maximum upload size is 20MB.
