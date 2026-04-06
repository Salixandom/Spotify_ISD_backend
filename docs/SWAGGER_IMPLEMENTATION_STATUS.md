# Swagger/OpenAPI Implementation Status

## ✅ Completed Setup

All 4 microservices have been configured with **drf-spectacular** for OpenAPI 3.0 documentation.

### Services Configured

| Service | Status | Documentation URL | Port |
|---------|--------|-------------------|------|
| **Auth** | ✅ Complete | http://localhost:8001/api/docs/ | 8001 |
| **Collaboration** | ✅ Configured | http://localhost:8002/api/docs/ | 8002 |
| **Core** | ✅ Configured | http://localhost:8003/api/docs/ | 8003 |
| **Playback** | ✅ Configured | http://localhost:8004/api/docs/ | 8004 |

### Configuration Details

#### 1. Dependencies Added
- ✅ `drf-spectacular>=0.27.0` added to all `pyproject.toml` files

#### 2. Django Settings Updated
- ✅ `drf_spectacular` added to `INSTALLED_APPS` in all services
- ✅ `DEFAULT_SCHEMA_CLASS` configured in `REST_FRAMEWORK` settings
- ✅ Custom `SPECTACULAR_SETTINGS` for each service with appropriate tags

#### 3. URL Configuration
- ✅ Schema endpoint: `/api/schema/`
- ✅ Swagger UI: `/api/docs/`
- ✅ ReDoc: `/api/redoc/`

#### 4. Auth Service (Most Complete)
- ✅ Full schema decorators added to all views in `authapp/views.py`
- ✅ Comprehensive documentation with tags, parameters, and response schemas
- ✅ JWT authentication documented
- ✅ Privacy settings and social features documented

## 🚀 Next Steps

### 1. Install Dependencies
For each service, run:
```bash
cd services/<service-name>
uv sync
```

### 2. Add Schema Decorators (Remaining Services)

While the Auth service has complete schema decorators, the other services need decorators added to their views. Here's the pattern:

#### For Collaboration Service (`collabapp/`, `shareapp/`)
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter

@extend_schema(
    tags=["Collaboration"],
    summary="Brief description",
    description="Detailed description",
    parameters=[...],
    responses={200: {...}, 400: {...}}
)
def method_name(self, request):
    # Your implementation
    pass
```

#### For Core Service (`playlistapp/`, `trackapp/`, `searchapp/`, `historyapp/`)
```python
from drf_spectacular.utils import extend_schema

@extend_schema(
    tags=["Playlists"],  # or "Tracks", "Search", "History"
    summary="Brief description",
    description="Detailed description",
    request=YourSerializer,
    responses={200: {...}}
)
def method_name(self, request):
    # Your implementation
    pass
```

#### For Playback Service (`playbackapp/`)
```python
from drf_spectacular.utils import extend_schema

@extend_schema(
    tags=["Playback"],
    summary="Brief description",
    description="Detailed description",
    responses={200: {...}}
)
def method_name(self, request):
    # Your implementation
    pass
```

### 3. Test the Documentation

1. **Start your services**:
   ```bash
   # Using docker-compose
   docker-compose up -d
   
   # Or individually
   cd services/auth && uv run uvicorn core.asgi:application --host 0.0.0.0 --port 8001 --reload
   ```

2. **Access the documentation**:
   - Auth: http://localhost:8001/api/docs/
   - Collaboration: http://localhost:8002/api/docs/
   - Core: http://localhost:8003/api/docs/
   - Playback: http://localhost:8004/api/docs/

3. **Test authentication**:
   - Use `/api/auth/login/` to get a token
   - Click "Authorize" button (🔓)
   - Enter: `Bearer YOUR_ACCESS_TOKEN`
   - Test authenticated endpoints

## 📝 Documentation Features Available

### 1. Interactive Testing
- Try out endpoints directly from the browser
- Automatic authentication handling
- Request/response validation

### 2. Schema Export
```bash
# Export OpenAPI schema
curl http://localhost:8001/api/schema/ > auth-schema.json

# Generate client SDKs
openapi-generator-cli generate -i auth-schema.json -g python -o ./client-sdk/
```

### 3. Multiple Formats
- **Swagger UI**: Interactive testing (`/api/docs/`)
- **ReDoc**: Reference documentation (`/api/redoc/`)
- **JSON Schema**: Machine-readable (`/api/schema/`)

## 🎯 Best Practices

### 1. Schema Decorators
Always add `@extend_schema` decorators to:
- Custom APIView classes
- Function-based views (`@api_view`)
- Views with complex request/response handling

### 2. Tags
Use meaningful tags for grouping:
- **Auth Service**: `Authentication`, `Profile`, `Social`, `Health`
- **Collaboration**: `Collaboration`, `Sharing`, `Health`
- **Core**: `Playlists`, `Tracks`, `Search`, `History`, `Health`
- **Playback**: `Playback`, `Media`, `Health`

### 3. Parameters
Document all parameters explicitly:
```python
@extend_schema(
    parameters=[
        OpenApiParameter(
            name='playlist_id',
            type=OpenApiTypes.INT,
            location=OpenApiParameter.PATH,
            description='Playlist ID',
            required=True
        )
    ]
)
```

### 4. Responses
Document all response codes:
- 200: Success
- 201: Created
- 400: Validation Error
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 500: Server Error

## 🔧 Troubleshooting

### Schema not loading
```bash
# Check service is running
curl http://localhost:8001/api/health/

# Check logs
docker-compose logs auth
```

### Authentication not working
- Verify token format: `Bearer YOUR_TOKEN`
- Check token hasn't expired (default 5 minutes)
- Verify JWT configuration in settings

### Import errors
```bash
# Reinstall dependencies
cd services/<service>
uv sync --reinstall
```

## 📚 Additional Resources

- [drf-spectacular documentation](https://drf-spectacular.readthedocs.io/)
- [OpenAPI Specification](https://swagger.io/specification/)
- [Swagger UI Documentation](https://swagger.io/tools/swagger-ui/)

---

**Status**: Ready for testing! All services configured with basic Swagger documentation.
