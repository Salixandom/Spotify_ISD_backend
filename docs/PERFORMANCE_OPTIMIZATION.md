# Performance Optimization Recommendations

**Playlist App — Spotify ISD Backend**
**Last Updated:** 2026-03-30

---

## Database Optimizations

### 1. Indexes Already Implemented ✅

**Playlist Model:**
- `owner_id` — Filters by user
- `name` — Search/sort
- `created_at`, `updated_at` — Date filtering
- `playlist_type` — Type filtering

**Social Models:**
- `user_id`, `playlist_id` — Join operations
- `followed_at`, `liked_at` — Temporal queries
- Unique constraints — Prevent duplicates

**Snapshot Model:**
- `playlist_id`, `created_at` — Snapshot queries
- `-created_at` — Recent-first ordering

### 2. Additional Recommended Indexes

```python
# Add to Playlist model
class Meta:
    indexes = [
        # Existing indexes...
        models.Index(fields=['visibility', 'updated_at']),  # Compound for featured
        models.Index(fields=['owner_id', '-updated_at']),  # User's recent playlists
    ]

# Add to UserPlaylistFollow and UserPlaylistLike
class Meta:
    indexes = [
        # Existing indexes...
        models.Index(fields=['-followed_at']),  # Recent activity
        models.Index(fields=['-liked_at']),
    ]
```

### 3. Query Optimization

**Current Best Practices:**
- ✅ `select_related()` for foreign keys
- ✅ `annotate()` with aggregations
- ✅ `values_list()` for ID filtering
- ✅ `bulk_create()` for batch inserts

**Recommended Additional:**

```python
# For large result sets, use iterator()
for playlist in Playlist.objects.all().iterator(chunk_size=100):
    # Process playlist
    pass

# Use only() to fetch only needed fields
playlists = Playlist.objects.only('id', 'name', 'owner_id')

# Use defer() to exclude heavy fields
playlists = Playlist.objects.defer('description')

# Count distinct efficiently
count = Playlist.objects.filter(owner_id=user_id).count()
```

---

## Caching Strategy

### 1. Cache Configuration

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        },
        'KEY_PREFIX': 'playlist',
        'TIMEOUT': 300,  # 5 minutes
    }
}

# Different timeouts for different data types
CACHE_TIMEOUTS = {
    'playlist_detail': 300,      # 5 minutes
    'playlist_list': 60,         # 1 minute
    'featured_playlists': 600,   # 10 minutes
    'recommendations': 300,      # 5 minutes
    'statistics': 180,           # 3 minutes
}
```

### 2. View-Level Caching

```python
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

@method_decorator(cache_page(60), name='dispatch')
class FeaturedPlaylistsView(APIView):
    # Cache for 1 minute
    pass

@method_decorator(cache_page(300), name='dispatch')
class PlaylistStatsView(APIView):
    # Cache for 5 minutes
    pass
```

### 3. Query Result Caching

```python
from django.core.cache import cache

def get_playlist_with_cache(playlist_id):
    cache_key = f'playlist:{playlist_id}'
    playlist = cache.get(cache_key)

    if playlist is None:
        playlist = Playlist.objects.get(id=playlist_id)
        cache.set(cache_key, playlist, timeout=300)

    return playlist

# Invalidate cache on updates
def update_playlist(playlist_id, data):
    playlist = Playlist.objects.get(id=playlist_id)
    # Update...
    cache.delete(f'playlist:{playlist_id}')
    return playlist
```

### 4. Cache Invalidation Strategy

```python
# Signal-based cache invalidation
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

@receiver(post_save, sender=Playlist)
def invalidate_playlist_cache(sender, instance, **kwargs):
    cache.delete(f'playlist:{instance.id}')
    cache.delete(f'playlist:{instance.id}:stats')
    cache.delete_pattern('playlist:list:*')  # If using django-redis

@receiver(post_save, sender=UserPlaylistFollow)
@receiver(post_delete, sender=UserPlaylistFollow)
def invalidate_follow_cache(sender, instance, **kwargs):
    cache.delete(f'user:{instance.user_id}:followed')
```

---

## API Optimization

### 1. Pagination

**Current:** Optional `limit`/`offset`
**Recommended:** Force pagination with page size limit

```python
# settings.py
REST_FRAMEWORK = {
    'PAGE_SIZE': 50,
    'MAX_PAGE_SIZE': 100,
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
}

# views.py
from rest_framework.pagination import PageNumberPagination

class StandardResultSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

class PlaylistViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultSetPagination
```

### 2. Response Optimization

```python
# Use sparse fieldsets
class PlaylistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Playlist
        fields = ['id', 'name', 'owner_id', 'updated_at']

# Use different serializers for different contexts
class PlaylistListSerializer(serializers.ModelSerializer):
    """Minimal fields for list views"""
    class Meta:
        model = Playlist
        fields = ['id', 'name', 'owner_id', 'track_count']

class PlaylistDetailSerializer(serializers.ModelSerializer):
    """Full fields for detail views"""
    class Meta:
        model = Playlist
        fields = '__all__'
```

### 3. Rate Limiting

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/hour',
        'batch': '10/minute',  # For batch operations
    }
}

# views.py
from rest_framework.throttling import UserRateThrottle

class BatchRateThrottle(UserRateThrottle):
    rate = '10/minute'
    scope = 'batch'

class BatchDeleteView(APIView):
    throttle_classes = [BatchRateThrottle]
```

---

## Background Tasks

### 1. Async Processing with Celery

```python
# tasks.py
from celery import shared_task
from .models import Playlist, PlaylistSnapshot

@shared_task
def create_snapshot_async(playlist_id, reason):
    """Create snapshot in background"""
    playlist = Playlist.objects.get(id=playlist_id)
    # Create snapshot...

@shared_task
def cleanup_old_snapshots():
    """Run nightly cleanup of old snapshots"""
    # Delete snapshots older than 30 days
    pass

@shared_task
def generate_recommendations_async(user_id):
    """Pre-generate recommendations"""
    # Generate and cache recommendations
    pass
```

### 2. Scheduled Tasks

```python
# celery.py
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-snapshots': {
        'task': 'playlistapp.tasks.cleanup_old_snapshots',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
    'generate-recommendations': {
        'task': 'playlistapp.tasks.generate_recommendations_for_users',
        'schedule': crontab(minute=0),  # Every hour
    },
}
```

---

## Database Connection Pooling

### Django Connection Pooling

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'spotify_db',
        'USER': 'postgres',
        'PASSWORD': 'password',
        'HOST': 'db',
        'PORT': '5432',
        'CONN_MAX_AGE': 600,  # Reuse connections for 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

---

## Monitoring & Profiling

### 1. Django Debug Toolbar (Dev Only)

```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

### 2. Query Logging

```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'handlers': ['console'],
        },
    }
}
```

### 3. Performance Monitoring

```python
# Middleware
import time
import logging

class PerformanceMonitoringMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()

        response = self.get_response(request)

        duration = time.time() - start_time
        if duration > 1.0:  # Log slow requests
            logging.warning(f'Slow request: {request.path} took {duration:.2f}s')

        response['X-Response-Time'] = f'{duration:.3f}s'
        return response
```

---

## Load Testing

### Recommended Tools

1. **Locust** — Python-based load testing
2. **Apache Bench (ab)** — Simple load testing
3. **k6** — Modern load testing tool

### Example Locust Test

```python
# locustfile.py
from locust import HttpUser, task, between

class PlaylistUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login
        response = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.token = response.json()['token']

    @task(3)
    def list_playlists(self):
        self.client.get('/api/playlists/', headers={
            'Authorization': f'Bearer {self.token}'
        })

    @task(1)
    def get_playlist_stats(self):
        self.client.get('/api/playlists/1/stats/', headers={
            'Authorization': f'Bearer {self.token}'
        })

    @task(1)
    def get_recommendations(self):
        self.client.get('/api/playlists/recommended/', headers={
            'Authorization': f'Bearer {self.token}'
        })
```

### Run Load Test

```bash
locust -f locustfile.py --host=https://api.spotify.com --users=100 --spawn-rate=10
```

---

## Optimization Priorities

### High Priority (Implement First)

1. **Add database indexes** for compound queries
2. **Implement pagination** with max page size
3. **Add caching** for featured playlists and statistics
4. **Use select_related()** consistently
5. **Add rate limiting** for expensive operations

### Medium Priority

1. **Implement cache invalidation** strategy
2. **Add background tasks** for async operations
3. **Optimize N+1 queries** with prefetch_related()
4. **Add sparse fieldsets** for list views
5. **Implement connection pooling**

### Low Priority (Optimize Later)

1. **Database read replicas** for scaling reads
2. **Materialized views** for complex aggregations
3. **Elasticsearch** for advanced search
4. **CDN caching** for static responses
5. **GraphQL** for flexible queries

---

## Performance Targets

### Response Times (p95)

- List playlists: < 200ms
- Get playlist detail: < 100ms
- Playlist statistics: < 300ms
- Recommendations: < 500ms
- Batch operations: < 2s

### Throughput

- 1000 concurrent users
- 10,000 requests/minute
- < 1% error rate

### Database

- Query duration: < 50ms (p95)
- Connection count: < 100
- Cache hit rate: > 80%

---

## Monitoring Checklist

- [ ] Set up application performance monitoring (APM)
- [ ] Configure database slow query logging
- [ ] Monitor cache hit/miss ratios
- [ ] Track API response times
- [ ] Monitor error rates
- [ ] Set up alerts for thresholds
- [ ] Regular load testing
- [ ] Database query analysis (EXPLAIN ANALYZE)

---

## Next Steps

1. **Implement caching layer** (Redis/Memcached)
2. **Add database indexes** for common queries
3. **Set up monitoring** and alerting
4. **Run load tests** to identify bottlenecks
5. **Optimize slow queries** identified in monitoring
6. **Implement rate limiting** for API protection
7. **Set up CDN** for static assets
8. **Regular performance reviews** (monthly)
