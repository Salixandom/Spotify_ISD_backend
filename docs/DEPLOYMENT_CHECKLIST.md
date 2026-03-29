# Deployment Checklist — Playlist App

**Project:** Spotify ISD Backend — Playlist App
**Version:** 1.0
**Last Updated:** 2026-03-30

---

## Pre-Deployment Checklist

### Code Review
- [ ] All code reviewed by at least one other developer
- [ ] No TODO/FIXME comments left in production code
- [ ] Debug statements removed (`print()`, `console.log()`)
- [ ] Sensitive data not hardcoded (use environment variables)
- [ ] API documentation complete and accurate
- [ ] Edge cases handled properly

### Testing
- [ ] Unit tests written for critical paths
- [ ] Integration tests pass
- [ ] Manual testing completed
- [ ] Load testing performed (1000 concurrent users)
- [ ] Security testing completed (SQL injection, XSS, etc.)
- [ ] Test coverage > 70%

### Database
- [ ] All migrations created and tested
- [ ] Database indexes created
- [ ] Foreign key constraints verified
- [ ] Connection pooling configured
- [ ] Backup strategy in place
- [ ] Migration rollback plan documented

### Configuration
- [ ] Environment variables set in production
- [ ] DEBUG=False in production
- [ ] ALLOWED_HOSTS configured correctly
- [ ] SECRET_KEY set to strong random value
- [ ] CORS settings configured
- [ ] Logging configured for production

---

## Deployment Steps

### 1. Database Migration

```bash
# Backup database first
docker exec spotify_isd_backend-db-1 pg_dump -U postgres spotify_db > backup.sql

# Run migrations
docker exec spotify_isd_backend-core-1 uv run python manage.py migrate

# Verify migrations
docker exec spotify_isd_backend-core-1 uv run python manage.py showmigrations
```

### 2. Collect Static Files

```bash
docker exec spotify_isd_backend-core-1 uv run python manage.py collectstatic --noinput
```

### 3. Create Superuser

```bash
docker exec -it spotify_isd_backend-core-1 uv run python manage.py createsuperuser
```

### 4. Verify Services

```bash
# Check all services running
docker-compose ps

# Check health endpoints
curl https://api.spotify.com/api/playlists/health/
curl https://api.spotify.com/api/auth/health/
curl https://api.spotify.com/api/songs/health/
curl https://api.spotify.com/api/artists/health/
```

### 5. Run Smoke Tests

```bash
# Test basic CRUD
curl -X POST https://api.spotify.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "test", "password": "test"}'

# Test playlist creation (with token)
curl -X POST https://api.spotify.com/api/playlists/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Playlist"}'
```

---

## Production Configuration

### Environment Variables

```bash
# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=spotify_db
DB_USER=postgres
DB_PASSWORD=secure_password

# Django
SECRET_KEY=<generate with: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=api.spotify.com,localhost

# Redis/Cache
REDIS_HOST=redis
REDIS_PORT=6379
CACHE_BACKEND=django_redis.cache.RedisCache

# JWT
JWT_SECRET_KEY=<different from SECRET_KEY>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Storage
SUPABASE_URL=https://*.supabase.co
SUPABASE_KEY=<your_key>
```

### Docker Compose Production

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: spotify_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    restart: always

  core:
    build: ./services/core
    command: gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
    environment:
      - DEBUG=False
      - DB_HOST=db
      - REDIS_HOST=redis
    depends_on:
      - db
      - redis
    restart: always

  traefik:
    image: traefik:v2.10
    # ... traefik config
    restart: always
```

---

## Post-Deployment Verification

### 1. Health Checks

```bash
# All services should return 200 OK
curl https://api.spotify.com/api/playlists/health/
# Expected: {"status": "healthy", "service": "playlist", "database": "connected"}
```

### 2. Database Connectivity

```bash
# Verify connection counts
docker exec spotify_isd_backend-db-1 psql -U postgres -d spotify_db -c "
  SELECT count(*) FROM pg_stat_activity WHERE datname = 'spotify_db';
"

# Check table counts
docker exec spotify_isd_backend-db-1 psql -U postgres -d spotify_db -c "
  SELECT schemaname, tablename, n_live_tup
  FROM pg_stat_user_tables
  ORDER BY n_live_tup DESC;
"
```

### 3. API Endpoints

```bash
# Test core endpoints
curl https://api.spotify.com/api/playlists/
curl https://api.spotify.com/api/playlists/featured/
curl https://api.spotify.com/api/playlists/recommended/
```

### 4. Monitoring

- [ ] Application logs show no errors
- [ ] Database queries completing < 100ms (p95)
- [ ] API response times within SLA
- [ ] Memory usage stable
- [ ] CPU usage < 70%
- [ ] No connection pool exhaustion

---

## Rollback Plan

### If Deployment Fails

1. **Stop new deployment**
   ```bash
   docker-compose stop core
   ```

2. **Revert to previous version**
   ```bash
   git checkout <previous-commit>
   docker-compose up -d --build core
   ```

3. **Verify rollback**
   ```bash
   curl https://api.spotify.com/api/playlists/health/
   ```

### If Database Migration Fails

1. **Identify failed migration**
   ```bash
   docker exec spotify_isd_backend-core-1 uv run python manage.py showmigrations
   ```

2. **Rollback migration**
   ```bash
   docker exec spotify_isd_backend-core-1 uv run python manage.py migrate <app> <previous_migration>
   ```

3. **Restore database backup** (if needed)
   ```bash
   cat backup.sql | docker exec -i spotify_isd_backend-db-1 psql -U postgres spotify_db
   ```

---

## Performance Baseline

### Target Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| API Response Time (p95) | < 200ms | > 500ms |
| API Response Time (p99) | < 500ms | > 1000ms |
| Error Rate | < 0.1% | > 1% |
| Database Query Time (p95) | < 50ms | > 100ms |
| Cache Hit Rate | > 80% | < 50% |
| Memory Usage | < 2GB | > 4GB |
| CPU Usage | < 50% | > 80% |

### Load Testing Results

- [ ] Tested with 1000 concurrent users
- [ ] Sustained 10,000 requests/minute
- [ ] Error rate < 0.1%
- [ ] No memory leaks detected
- [ ] Response times stable over 1 hour

---

## Security Checklist

### Authentication & Authorization
- [ ] JWT tokens expire after 30 minutes
- [ ] Refresh tokens rotate properly
- [ ] Password hashing uses bcrypt/argon2
- [ ] Rate limiting on auth endpoints
- [ ] Failed login attempts monitored

### API Security
- [ ] All endpoints require authentication
- [ ] Authorization checks on all endpoints
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (ORM used)
- [ ] XSS prevention (template escaping)
- [ ] CORS configured properly
- [ ] HTTPS enforced in production

### Data Security
- [ ] Environment variables not in git
- [ ] Secrets managed properly (Vault/K8s secrets)
- [ ] Database backups encrypted
- [ ] PII data access logged
- [ ] GDPR compliance (if applicable)

---

## Monitoring & Alerting

### Metrics to Monitor

1. **Application Metrics**
   - Request rate
   - Response times (p50, p95, p99)
   - Error rate
   - Active users

2. **Database Metrics**
   - Connection pool usage
   - Query performance
   - Table sizes
   - Index usage

3. **Infrastructure Metrics**
   - CPU usage
   - Memory usage
   - Disk I/O
   - Network I/O

### Alerting Rules

```yaml
alerts:
  - name: HighErrorRate
    condition: error_rate > 1%
    duration: 5m
    severity: critical

  - name: SlowAPIResponse
    condition: p95_response_time > 500ms
    duration: 10m
    severity: warning

  - name: DatabaseConnectionPoolExhausted
    condition: db_connections > 90%
    duration: 2m
    severity: critical

  - name: HighMemoryUsage
    condition: memory > 4GB
    duration: 5m
    severity: warning
```

---

## Maintenance Tasks

### Daily
- [ ] Check error logs
- [ ] Verify backup completion
- [ ] Monitor key metrics

### Weekly
- [ ] Review performance trends
- [ ] Check database growth
- [ ] Clean up old snapshots (if needed)
- [ ] Review security logs

### Monthly
- [ ] Database vacuum and analyze
- [ ] Review and update indexes
- [ ] Load testing (if changes made)
- [ ] Security audit
- [ ] Dependency updates

---

## Documentation

- [ ] API documentation up to date
- [ ] Deployment runbook created
- [ ] Runbook tested
- [ ] Onboarding documentation complete
- [ ] Architecture diagrams updated
- [ ] Troubleshooting guide created

---

## Communication

### Pre-Deployment
- [ ] Stakeholders notified 24h in advance
- [ ] Maintenance window scheduled
- [ ] Rollback plan communicated
- [ ] On-call engineer assigned

### Post-Deployment
- [ ] Deployment announcement sent
- [ ] Success metrics shared
- [ ] Issues documented (if any)
- [ ] Post-mortem scheduled (if needed)

---

## Sign-Off

**Developer:** ________________ Date: ________

**Code Reviewer:** ________________ Date: ________

**QA Engineer:** ________________ Date: ________

**DevOps Engineer:** ________________ Date: ________

**Project Manager:** ________________ Date: ________

---

## Deployment History

| Date | Version | Deployed By | Status | Notes |
|------|---------|-------------|--------|-------|
| 2026-03-30 | 1.0.0 | Taskeen Towfique | ✅ Success | Initial release with all 6 phases |

---

## Emergency Contacts

| Role | Name | Contact |
|------|------|---------|
| Lead Developer | Taskeen Towfique | taskeen@example.com |
| DevOps Engineer | - | devops@example.com |
| DBA | - | dba@example.com |
| On-Call | - | +1234567890 |

---

**Deployment completed successfully!** 🎉

**Next steps:**
1. Monitor metrics for first 24 hours
2. Address any issues immediately
3. Plan Phase 2 enhancements based on feedback
