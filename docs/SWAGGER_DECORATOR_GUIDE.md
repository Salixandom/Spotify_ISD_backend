# Swagger/OpenAPI Schema Decorator Guide

This guide provides patterns and examples for adding `@extend_schema` decorators to your Django REST Framework views using **drf-spectacular**.

## Quick Reference

### Import Statement
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes
from drf_spectacular.types import OpenApiTypes
```

### Basic Pattern
```python
@extend_schema(
    tags=["YourTag"],
    summary="Brief one-line description",
    description="Detailed description of what this endpoint does",
    parameters=[...],  # For path/query parameters
    request=YourSerializer,  # For request body
    responses={
        200: {...},  # Success response
        400: {...},  # Client error
        401: {...},  # Unauthorized
        403: {...},  # Forbidden
        404: {...},  # Not found
        500: {...},  # Server error
    }
)
def method_name(self, request, ...):
    # Your implementation
    pass
```

## Common Patterns

### 1. APIView with GET Request

```python
class MyListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["MyResource"],
        summary="List all resources",
        description="Returns a paginated list of resources with optional filtering",
        parameters=[
            OpenApiParameter(
                name='limit',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results to return (default: 20)',
                required=False
            ),
            OpenApiParameter(
                name='offset',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.QUERY,
                description='Number of results to skip (default: 0)',
                required=False
            ),
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'array',
                        'items': YourSerializer
                    }
                }
            }
        }
    )
    def get(self, request):
        # Your implementation
        pass
```

### 2. APIView with POST Request (Create)

```python
class CreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["MyResource"],
        summary="Create a new resource",
        description="Creates a new resource with the provided data",
        request=YourSerializer,
        responses={
            201: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': YourSerializer
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            }
        }
    )
    def post(self, request):
        # Your implementation
        pass
```

### 3. APIView with Path Parameters

```python
class DetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["MyResource"],
        summary="Get resource details",
        description="Returns detailed information about a specific resource",
        parameters=[
            OpenApiParameter(
                name='resource_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Resource ID',
                required=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': YourSerializer
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def get(self, request, resource_id):
        # Your implementation
        pass
```

### 4. APIView with PUT/PATCH (Update)

```python
class UpdateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["MyResource"],
        summary="Update a resource",
        description="Updates a resource with the provided data. All fields are optional for PATCH.",
        parameters=[
            OpenApiParameter(
                name='resource_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Resource ID',
                required=True
            )
        ],
        request=YourSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': YourSerializer
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def put(self, request, resource_id):
        # Your implementation
        pass

    @extend_schema(
        tags=["MyResource"],
        summary="Partially update a resource",
        description="Updates specific fields of a resource. All fields are optional.",
        parameters=[
            OpenApiParameter(
                name='resource_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Resource ID',
                required=True
            )
        ],
        request=YourSerializer,
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': YourSerializer
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def patch(self, request, resource_id):
        # Your implementation
        pass
```

### 5. APIView with DELETE

```python
class DeleteView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["MyResource"],
        summary="Delete a resource",
        description="Permanently deletes a resource",
        parameters=[
            OpenApiParameter(
                name='resource_id',
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description='Resource ID',
                required=True
            )
        ],
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            403: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            },
            404: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'}
                }
            }
        }
    )
    def delete(self, request, resource_id):
        # Your implementation
        pass
```

### 6. Function-Based Views

```python
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@extend_schema(
    tags=["Health"],
    summary="Health check endpoint",
    description="Check if the service is healthy",
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'data': {
                    'type': 'object',
                    'properties': {
                        'status': {'type': 'string'},
                        'service': {'type': 'string'},
                        'database': {'type': 'string'}
                    }
                }
            }
        },
        503: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'}
            }
        }
    }
)
def health_check(request):
    # Your implementation
    pass
```

### 7. Custom Request Body (Not a Serializer)

```python
@extend_schema(
    tags=["MyResource"],
    summary="Custom action",
    description="Perform a custom action with specific request format",
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'field1': {'type': 'string', 'description': 'Description of field1'},
                'field2': {'type': 'integer', 'description': 'Description of field2'},
                'field3': {'type': 'boolean', 'description': 'Description of field3'}
            },
            'required': ['field1', 'field2']
        }
    },
    responses={
        200: {
            'type': 'object',
            'properties': {
                'success': {'type': 'boolean'},
                'message': {'type': 'string'},
                'data': {
                    'type': 'object',
                    'properties': {
                        'result': {'type': 'string'}
                    }
                }
            }
        }
    }
)
def post(self, request):
    # Your implementation
    pass
```

### 8. Batch Operations

```python
class BatchOperationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["MyResource"],
        summary="Batch delete resources",
        description="Delete multiple resources at once",
        request={
            'application/json': {
                'type': 'object',
                'properties': {
                    'resource_ids': {
                        'type': 'array',
                        'items': {'type': 'integer'},
                        'description': 'List of resource IDs to delete'
                    }
                },
                'required': ['resource_ids']
            }
        },
        responses={
            200: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'data': {
                        'type': 'object',
                        'properties': {
                            'deleted': {'type': 'integer'},
                            'not_found': {'type': 'integer'},
                            'not_authorized': {'type': 'integer'}
                        }
                    }
                }
            },
            400: {
                'type': 'object',
                'properties': {
                    'success': {'type': 'boolean'},
                    'message': {'type': 'string'},
                    'errors': {'type': 'object'}
                }
            }
        }
    )
    def delete(self, request):
        # Your implementation
        pass
```

## Service-Specific Tags

### Auth Service
- `Authentication` - Login, register, token management
- `Profile` - User profile management
- `Social` - Follow/unfollow functionality
- `Health` - Service health checks

### Collaboration Service
- `Collaboration` - Playlist collaboration features
- `Sharing` - Playlist sharing functionality
- `Health` - Service health checks

### Core Service
- `Playlists` - Playlist CRUD operations
- `Tracks` - Track management
- `Search` - Search functionality
- `History` - Listening history
- `Health` - Service health checks

### Playback Service
- `Playback` - Music playback controls
- `Media` - Audio file management
- `Health` - Service health checks

## Response Format Standards

### Success Response (200/201)
```python
{
    'type': 'object',
    'properties': {
        'success': {'type': 'boolean'},
        'message': {'type': 'string'},
        'data': YourSerializer  # or custom object
    }
}
```

### Error Response (400/401/403/404/500)
```python
{
    'type': 'object',
    'properties': {
        'success': {'type': 'boolean'},
        'message': {'type': 'string'},
        'errors': {'type': 'object'}  # For validation errors (400 only)
    }
}
```

## Common Parameter Types

```python
# Integer parameter
OpenApiParameter(
    name='id',
    type=OpenApiTypes.INT,
    location=OpenApiParameter.PATH,
    description='Resource ID',
    required=True
)

# String parameter
OpenApiParameter(
    name='query',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description='Search query',
    required=False
)

# Boolean parameter
OpenApiParameter(
    name='include_deleted',
    type=OpenApiTypes.BOOL,
    location=OpenApiParameter.QUERY,
    description='Include deleted items',
    required=False
)

# Enum parameter (with choices)
OpenApiParameter(
    name='sort',
    type=OpenApiTypes.STR,
    location=OpenApiParameter.QUERY,
    description='Sort field',
    enum=['name', 'created_at', 'updated_at'],
    required=False
)
```

## ViewSet Documentation

For `ModelViewSet` classes, add decorators to individual methods:

```python
class MyViewSet(viewsets.ModelViewSet):
    serializer_class = MySerializer
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        tags=["MyResource"],
        summary="List resources",
        description="Returns a list of resources",
        responses={200: {...}}
    )
    def list(self, request, *args, **kwargs):
        pass

    @extend_schema(
        tags=["MyResource"],
        summary="Create resource",
        description="Creates a new resource",
        request=MySerializer,
        responses={201: {...}}
    )
    def create(self, request, *args, **kwargs):
        pass

    @extend_schema(
        tags=["MyResource"],
        summary="Get resource details",
        description="Returns a single resource",
        responses={200: {...}}
    )
    def retrieve(self, request, *args, **kwargs):
        pass

    @extend_schema(
        tags=["MyResource"],
        summary="Update resource",
        description="Updates a resource",
        request=MySerializer,
        responses={200: {...}}
    )
    def update(self, request, *args, **kwargs):
        pass

    @extend_schema(
        tags=["MyResource"],
        summary="Delete resource",
        description="Deletes a resource",
        responses={204: {...}}
    )
    def destroy(self, request, *args, **kwargs):
        pass
```

## Tips for Better Documentation

1. **Use clear, descriptive summaries**: Keep it under 60 characters
2. **Provide detailed descriptions**: Explain edge cases and authorization requirements
3. **Document all parameters**: Even optional ones should be documented
4. **Use appropriate tags**: Group related endpoints together
5. **Include all response codes**: Document both success and error cases
6. **Use serializers when possible**: Automatically generates accurate schemas
7. **Document authentication**: Mention if JWT is required
8. **Include examples in descriptions**: Show expected input formats

## Testing Your Documentation

1. **Start your service**: `uv run uvicorn core.asgi:application --reload`
2. **Visit Swagger UI**: http://localhost:8003/api/docs/
3. **Test authentication**: Use the "Authorize" button
4. **Try out endpoints**: Use the "Try it out" feature
5. **Check generated schema**: http://localhost:8003/api/schema/

## Troubleshooting

### Schema not reflecting changes
```bash
# Restart the service
uv run uvicorn core.asgi:application --reload
```

### Import errors
```bash
# Reinstall dependencies
uv sync --reinstall
```

### Missing tags
- Make sure tags are defined in `SPECTACULAR_SETTINGS`
- Check for typos in tag names
- Restart the service

---

This guide provides everything you need to document your remaining views. Follow the patterns above and your API documentation will be comprehensive and professional!
