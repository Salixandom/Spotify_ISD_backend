# Swagger/OpenAPI Documentation Setup Guide

## Overview

This document explains how to access and use the Swagger/OpenAPI documentation for each microservice in the Spotify ISD backend.

## Accessing Documentation

Each service has three documentation endpoints available:

### Swagger UI (Interactive)
- **URL**: `http://localhost:<SERVICE_PORT>/api/docs/`
- **Features**: 
  - Interactive API testing
  - Request/response examples
  - Authentication input
  - Try-it-out functionality

### ReDoc (Reference)
- **URL**: `http://localhost:<SERVICE_PORT>/api/redoc/`
- **Features**:
  - Clean, reference-style documentation
  - Better for reading and sharing
  - Mobile-friendly layout

### OpenAPI Schema (JSON)
- **URL**: `http://localhost:<SERVICE_PORT>/api/schema/`
- **Features**:
  - Raw OpenAPI 3.0 schema
  - Used for code generation
  - Integration with API tools

## Service Ports

Based on your docker-compose configuration, services run on these ports:

| Service | Internal Port | External Port | Docs URL |
|---------|--------------|---------------|----------|
| Auth | 8001 | 8001 | http://localhost:8001/api/docs/ |
| Collaboration | 8002 | 8002 | http://localhost:8002/api/docs/ |
| Core | 8003 | 8003 | http://localhost:8003/api/docs/ |
| Playback | 8004 | 8004 | http://localhost:8004/api/docs/ |

## Testing Authenticated Endpoints

### 1. Get Your Token
1. Open Swagger UI: `http://localhost:8001/api/docs/`
2. Find the `/api/auth/login/` endpoint
3. Click "Try it out"
4. Enter your credentials
5. Execute the request
6. Copy the `access` token from the response

### 2. Configure Authentication
1. Click the "Authorize" button (lock icon) at the top of Swagger UI
2. In the popup, enter your token (without quotes): `Bearer YOUR_ACCESS_TOKEN`
3. Click "Authorize"
4. Close the popup

### 3. Test Authenticated Endpoints
Now you can test any authenticated endpoint!

## API Response Format

All endpoints return a standardized response format:

```json
{
  "success": true,
  "message": "Operation successful",
  "data": { ... }
}
```

Error responses follow a similar pattern:

```json
{
  "success": false,
  "message": "Error description",
  "errors": { ... }
}
```

## Authentication

This API uses JWT (JSON Web Tokens) for authentication:

1. **Login**: POST `/api/auth/login/` → Get access + refresh tokens
2. **Use Token**: Include `Authorization: Bearer <access_token>` header
3. **Refresh**: POST `/api/auth/token/refresh/` → Get new access token

## Next Steps

1. **Install dependencies**: Run `uv sync` in each service directory
2. **Start services**: Use `docker-compose up` or individual service startup
3. **Access docs**: Navigate to the documentation URLs above
4. **Test endpoints**: Use the interactive Swagger UI to test your APIs

## Downloading OpenAPI Schema

You can download the OpenAPI schema for each service:

```bash
# Download Auth service schema
curl http://localhost:8001/api/schema/ -o auth-openapi.json

# Download with pretty formatting
curl http://localhost:8001/api/schema/?format=openapi-json -o auth-openapi.json
```

This schema can be used with:
- **OpenAPI Generator**: Generate client SDKs
- **Postman**: Import collection
- **API Gateways**: Configure routing
- **Documentation Tools**: Generate custom docs

## Custom Tags

Endpoints are organized by tags in Swagger UI:

- **Authentication**: Login, register, token management
- **Profile**: User profile management
- **Social**: Follow/unfollow functionality  
- **Health**: Service health checks
- **Playlists**: Playlist CRUD operations (Core service)
- **Tracks**: Track management (Core service)
- **History**: Listening history (Core service)
- **Search**: Search functionality (Core service)
- **Collaboration**: Playlist sharing (Collaboration service)
- **Playback**: Playback controls (Playback service)

## Troubleshooting

### Schema not loading
- Ensure `drf-spectacular` is installed: `uv add drf-spectacular`
- Check that service is running
- Verify port configuration

### Authentication errors
- Make sure you're using the access token (not refresh token)
- Check token hasn't expired (default 5 minutes)
- Verify `Authorization` header format: `Bearer <token>`

### 404 on docs endpoints
- Check that drf-spectacular is in `INSTALLED_APPS`
- Verify URL configuration includes schema paths
- Restart the service after configuration changes
