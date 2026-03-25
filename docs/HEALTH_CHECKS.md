# Health Check Endpoints - Complete Guide

## Overview

All 5 microservices include a `/health/` endpoint for monitoring, orchestration, and health checks. These endpoints verify both service availability and database connectivity.

---

## Endpoints

| Service | Health Check URL | Purpose |
|---------|-------------------|---------|
| Auth | `http://localhost/api/auth/health/` | Verify auth service is up |
| Playlist | `http://localhost/api/playlists/health/` | Verify playlist service is up |
| Track | `http://localhost/api/tracks/health/` | Verify track service is up |
| Search | `http://localhost/api/search/health/` | Verify search service is up |
| Collaboration | `http://localhost/api/collab/health/` | Verify collaboration service is up |

---

## Healthy Response

**Status Code:** `200 OK`

**Response Body:**
```json
{
    "status": "healthy",
    "service": "auth",
    "database": "connected"
}
```

**What it means:**
- Service is running and accepting requests
- Database connection is working
- Service can handle normal traffic

---

## Unhealthy Response

**Status Code:** `503 Service Unavailable`

**Response Body:**
```json
{
    "status": "unhealthy",
    "service": "auth",
    "database": "disconnected",
    "error": "server closed the connection unexpectedly"
}
```

**What it means:**
- Service may be running but database is down
- Or service has a critical error
- Or service is overloaded

---

## Usage Examples

### Test All Services
```bash
# Quick check
curl http://localhost/api/auth/health/
curl http://localhost/api/playlists/health/
curl http://localhost/api/tracks/health/
curl http://localhost/api/search/health/
curl http://localhost/api/collab/health/
```

### Check with jq
```bash
curl -s http://localhost/api/auth/health/ | jq '.'
```

### Automated Health Check Script
```bash
#!/bin/bash
for service in auth playlist track search collaboration; do
    echo -n "$service: "
    response=$(curl -s "http://localhost/api/${service}/health/")
    status=$(echo "$response" | jq -r '.status // "error"')
    echo "$status"
done
```

### Kubernetes Liveness Probe
```yaml
livenessProbe:
  httpGet:
    path: /api/auth/health/
    port: 8001
  initialDelaySeconds: 10
  periodSeconds: 30
```

### Kubernetes Readiness Probe
```yaml
readinessProbe:
  httpGet:
    path: /api/auth/health/
    port: 8001
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Load Balancer Health Check
```yaml
healthCheck:
  path: /api/auth/health/
  interval: 30s
  timeout: 5s
  unhealthyThreshold: 3
  healthyThreshold: 2
```

---

## Implementation Details

### Code Pattern
```python
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    """
    Health check endpoint for monitoring and orchestration
    Returns 200 if service and database are healthy
    """
    try:
        # Check database connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()

        return Response({
            'status': 'healthy',
            'service': 'service-name',
            'database': 'connected'
        }, status=200)
    except Exception as e:
        return Response({
            'status': 'unhealthy',
            'service': 'service-name',
            'database': 'disconnected',
            'error': str(e)
        }, status=503)
```

### Location in Each Service
- `services/auth/authapp/views.py`
- `services/playlist/playlistapp/views.py`
- `services/track/trackapp/views.py`
- `services/search/searchapp/views.py`
- `services/collaboration/collaborationapp/views.py`

### URL Configuration
```python
# In each service's urls.py
from django.urls import path
from .views import health_check

urlpatterns = [
    path('health/', health_check),
    # ... other URLs
]
```

---

## Monitoring Integration

### Prometheus Metrics (Future)
```python
from prometheus_client import Counter

health_check_total = Counter('health_check_requests_total', 'Total health checks')

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    health_check_total.inc()
    # ... rest of implementation
```

### Logging (Future)
```python
import logging

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    logger.info("Health check requested")
    # ... rest of implementation
```

---

## Troubleshooting

### Service Returns 404
**Issue:** URL not found

**Solutions:**
1. Check service is running: `docker-compose ps`
2. Check URL is correct: `/api/{service}/health/`
3. Check service logs: `docker-compose logs {service}`
4. Verify URL configuration in `urls.py`

### Service Returns 500
**Issue:** Internal server error

**Solutions:**
1. Check service logs for stack trace: `docker-compose logs {service}`
2. Check database connection: `docker-compose exec db pg_isready`
3. Restart service: `docker-compose restart {service}`

### Database Connection Refused
**Issue:** Can't connect to database

**Solutions:**
1. Check database is running: `docker-compose ps db`
2. Check database logs: `docker-compose logs db`
3. Verify environment variables: `docker-compose exec auth env | grep DB`
4. Check network connectivity: `docker-compose exec auth ping db`

### Traefik Routing Not Working
**Issue:** Requests through port 80 fail

**Solutions:**
1. Check Traefik is running: `docker-compose ps traefik`
2. Check Traefik logs: `docker-compose logs traefik`
3. Access Traefik dashboard: http://localhost:8080
4. Verify service labels in `docker-compose.yml`
5. Test direct access: `curl http://localhost:8001/api/auth/health/`

---

## Best Practices

### For Monitoring Systems
1. **Poll every 30 seconds** - Don't overload services
2. **Timeout after 5 seconds** - Fail fast if service is slow
3. **Retry 3 times** - Handle temporary failures
4. **Alert on 3 consecutive failures** - Avoid alert fatigue

### For Load Balancers
1. **Use health checks for graceful degradation**
2. **Remove unhealthy instances from rotation**
3. **Add instances back when healthy**
4. **Monitor health check latency**

### For Development
1. **Test health checks after every code change**
2. **Use health checks to verify services started**
3. **Include health checks in pre-commit hooks**
4. **Document any custom health check logic**

---

## Advanced Usage

### Custom Health Checks
Add custom checks based on service-specific needs:

```python
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    checks = {
        'database': check_database(),
        'redis': check_redis(),
        'external_api': check_external_api(),
    }

    all_healthy = all(checks.values())

    return Response({
        'status': 'healthy' if all_healthy else 'degraded',
        'service': 'auth',
        'checks': checks
    }, status=200 if all_healthy else 503)
```

### Deep Health Check
Add `?deep=true` parameter for detailed diagnostics:

```python
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def health_check(request):
    if request.GET.get('deep') == 'true':
        # Return detailed diagnostics
        return Response({
            'status': 'healthy',
            'service': 'auth',
            'database': {
                'connected': True,
                'latency_ms': 5,
                'pool_size': 10,
            },
            'memory': {
                'used_mb': 150,
                'available_mb': 850,
            },
        })
    else:
        # Simple health check
        return Response({'status': 'healthy'})
```

---

## Status

**All Services:** ✅ Healthy

| Service | Endpoint | Status | Last Checked |
|---------|----------|--------|--------------|
| Auth | `/api/auth/health/` | ✅ Healthy | 2026-03-26 02:45 |
| Playlist | `/api/playlists/health/` | ✅ Healthy | 2026-03-26 02:45 |
| Track | `/api/tracks/health/` | ✅ Healthy | 2026-03-26 02:45 |
| Search | `/api/search/health/` | ✅ Healthy | 2026-03-26 02:45 |
| Collaboration | `/api/collab/health/` | ✅ Healthy | 2026-03-26 02:45 |

---

**Last Updated:** March 26, 2026
**Maintained By:** Development Team
