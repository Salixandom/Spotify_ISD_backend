# Test Suite for Spotify ISD Backend

This directory contains comprehensive tests for the Spotify ISD backend core service.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures and configuration
├── unit/                    # Unit tests
│   ├── test_playlist_models.py
│   ├── test_track_models.py
│   ├── test_search_models.py
│   └── test_history_models.py
├── integration/             # Integration tests
│   ├── test_playlist_api.py
│   ├── test_track_api.py
│   ├── test_search_api.py
│   ├── test_history_api.py
│   └── test_authorization.py
├── performance/             # Performance tests
│   └── test_query_performance.py
└── fixtures/                # Test fixtures and factories
    └── __init__.py
```

## Running Tests

### Run all tests (via Docker):
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/
```

### Run specific test file:
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/unit/test_playlist_models.py
```

### Run with coverage:
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/ --cov=. --cov-report=html
```

### Run only unit tests:
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/unit/ -v
```

### Run only integration tests:
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/integration/ -v
```

### Run only performance tests:
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/performance/ -v
```

### Run with verbose output:
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/ -v -s
```

### Run specific test:
```bash
docker exec spotify_isd_backend-core-1 uv run pytest tests/integration/test_playlist_api.py::TestPlaylistViewSet::test_list_playlists_authenticated
```

## Test Categories

### Unit Tests
Test individual components in isolation:
- Model methods and properties
- Model validations and constraints
- Business logic in services
- Serializer validations

### Integration Tests
Test API endpoints and component interactions:
- HTTP request/response handling
- Authentication and authorization
- CRUD operations
- Filtering, searching, sorting
- Batch operations

### Authorization Tests
Verify security and permissions:
- Authentication requirements
- Ownership checks
- Permission enforcement
- Public vs private access

### Performance Tests
Verify query optimizations:
- N+1 query prevention
- select_related usage
- Efficient filtering
- Database index usage

## Test Coverage

The test suite covers:

**Models (100% coverage target):**
- Playlist, Track, Song, Artist, Album, Genre
- UserAction, Play, UndoRedoConfiguration
- UserPlaylistFollow, UserPlaylistLike, PlaylistSnapshot
- UserTrackHide, PlaylistComment

**API Endpoints:**
- All CRUD operations
- Search and discovery
- Undo/redo functionality
- Follow/like operations
- Batch operations
- Statistics and recommendations

**Security:**
- Authentication on all endpoints
- Authorization for write operations
- Public/private access control
- Owner-only operations

## Writing New Tests

1. **Unit Tests**: Place in `tests/unit/`
   - Test one component at a time
   - Mock external dependencies
   - Fast and isolated

2. **Integration Tests**: Place in `tests/integration/`
   - Test full request/response cycle
   - Use APIClient
   - Test real database operations

3. **Performance Tests**: Place in `tests/performance/`
   - Use CaptureQueriesContext to count queries
   - Verify select_related/prefetch_related usage
   - Check for N+1 queries

## Fixtures

Common fixtures are defined in `conftest.py`:
- `api_client`: Authenticated API client
- `authenticated_user`: Test user with JWT token
- `test_playlist`: Test playlist owned by authenticated user
- `test_artist`: Test artist
- `test_album`: Test album
- `test_song`: Test song with artist and album

## Continuous Integration

These tests should run in CI/CD pipeline:
```bash
# Run all tests with coverage
docker exec spotify_isd_backend-core-1 uv run pytest tests/ --cov=. --cov-report=xml --junitxml=test-results.xml
```

## Troubleshooting

### Tests failing with database errors:
- Ensure database migrations are applied
- Check that test database is properly configured

### Import errors:
- Verify DJANGO_SETTINGS_MODULE is set correctly
- Check that all required apps are in INSTALLED_APPS

### Authentication errors:
- Ensure JWT tokens are being generated correctly
- Check that user exists in database

## Best Practices

1. **Keep tests fast**: Unit tests should run in milliseconds
2. **Test one thing**: Each test should verify one behavior
3. **Use descriptive names**: `test_create_playlist_with_max_songs_limit`
4. **Clean up**: Use fixtures to manage test data lifecycle
5. **Avoid brittle tests**: Don't rely on specific IDs or ordering unless testing that feature
