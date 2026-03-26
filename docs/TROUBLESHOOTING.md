# Troubleshooting Guide

## Common Issues and Solutions

---

## 🚨 Service Issues

### Services Won't Start

**Symptoms:**
```bash
docker-compose up -d
# Containers exit immediately
```

**Solutions:**

1. **Check for port conflicts**
```bash
# See what's using ports 8001, 8002, 8003
netstat -tuln | grep -E '8001|8002|8003'
# Or
lsof -i :8001
```

2. **Check Docker daemon**
```bash
docker info
# If error, restart Docker
```

3. **Check container logs**
```bash
docker-compose logs auth
```

4. **Rebuild images**
```bash
docker-compose build --no-cache auth
docker-compose up -d auth
```

---

### Service Keeps Restarting (Crash Loop)

**Symptoms:**
```bash
docker-compose ps
# Shows "Restarting" status
```

**Solutions:**

1. **Check logs for error**
```bash
docker-compose logs --tail=50 auth
```

2. **Common causes:**
   - Database not ready
   - Missing environment variable
   - Import error
   - Syntax error in code

3. **Fix database timing**
```yaml
# In docker-compose.yml
depends_on:
  db:
    condition: service_healthy
```

4. **Check environment variables**
```bash
docker-compose exec auth env | grep -E 'DB|SECRET'
```

---

### Hot-Reload Not Working

**Symptoms:**
- Code changes not reflecting
- Need manual restart

**Solutions:**

1. **Verify volume mount**
```bash
docker-compose inspect auth | grep -A 10 Mounts
# Should show: ./services/auth:/app
```

2. **Check uvicorn is running with --reload**
```bash
docker-compose logs auth | grep uvicorn
# Should show: uvicorn ... --reload
```

3. **Verify file permissions**
```bash
ls -la services/auth/
# Files should be readable
```

4. **Restart service**
```bash
docker-compose restart auth
```

---

## 🗄️ Database Issues

### Database Connection Refused

**Symptoms:**
```
psycopg2.OperationalError: could not connect to server
```

**Solutions:**

1. **Check database is running**
```bash
docker-compose ps db
```

2. **Check database logs**
```bash
docker-compose logs db
```

3. **Test connection from service**
```bash
docker-compose exec auth ping db
```

4. **Verify environment variables**
```bash
docker-compose exec auth env | grep DB_HOST
# Should show: DB_HOST=db
```

5. **Restart database**
```bash
docker-compose restart db
```

---

### Database Migrations Failed

**Symptoms:**
```
django.db.migrations.exceptions.InconsistentMigrationHistory
```

**Solutions:**

1. **Drop and recreate database**
```bash
docker-compose exec db psql -U spotifyuser -d spotifydb -c "DROP SCHEMA public CASCADE;"
docker-compose exec auth uv run python manage.py migrate
```

2. **Fake migrations**
```bash
docker-compose exec auth uv run python manage.py migrate --fake
```

3. **Reset migrations**
```bash
# Delete migration files
rm services/auth/authapp/migrations/*.py
touch services/auth/authapp/migrations/__init__.py
docker-compose exec auth uv run python manage.py makemigrations
docker-compose exec auth uv run python manage.py migrate
```

---

### Database Full

**Symptoms:**
```
ERROR: could not extend file
```

**Solutions:**

1. **Check disk space**
```bash
docker system df
```

2. **Clean up Docker**
```bash
docker system prune -a
```

3. **Vacuum database**
```bash
docker-compose exec db psql -U spotifyuser -d spotifydb -c "VACUUM FULL;"
```

---

## 🌐 Routing Issues

### Traefik Returns 404

**Symptoms:**
```bash
curl http://localhost/api/auth/health/
# Returns 404
```

**Solutions:**

1. **Check Traefik is running**
```bash
docker-compose ps traefik
```

2. **Check Traefik logs**
```bash
docker-compose logs traefik | grep -i error
```

3. **Verify service labels**
```yaml
# In docker-compose.yml
labels:
  - "traefik.enable=true"
  - "traefik.http.routers.auth.rule=PathPrefix(`/api/auth`)"
```

4. **Check Traefik dashboard**
```bash
open http://localhost:8080
# Navigate to HTTP -> Routers
```

5. **Test direct access**
```bash
curl http://localhost:8001/api/auth/health/
# If this works, service is fine, issue is Traefik
```

---

### Some Services Route, Others Don't

**Symptoms:**
- Auth works through Traefik
- Playlist returns 404

**Solutions:**

1. **Check service is in same network**
```bash
docker network inspect spotify-collab_default
```

2. **Verify service labels**
```bash
docker inspect spotify-collab_playlist_1 | grep -A 10 Labels
```

3. **Check service is running**
```bash
curl http://localhost:8002/api/playlists/health/
```

4. **Wait for hot-reload**
```bash
# Services may be reloading
sleep 10
curl http://localhost/api/playlists/health/
```

---

## 🔐 Authentication Issues

### JWT Token Not Working

**Symptoms:**
```
Authorization header required
```

**Solutions:**

1. **Check JWT configuration**
```python
# In settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
}
```

2. **Verify token format**
```bash
# Should include: "Bearer <token>"
curl -H "Authorization: Bearer <token>" http://localhost/api/auth/me/
```

3. **Check token expiration**
```python
import jwt
jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
```

---

### CORS Errors

**Symptoms:**
```
Access to fetch at 'http://localhost' from origin 'http://localhost:3000' has been blocked by CORS policy
```

**Solutions:**

1. **Check CORS configuration**
```python
# In settings.py
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8000",
]
```

2. **Verify CORS middleware**
```python
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    # ... other middleware
]
```

3. **Check environment variable**
```bash
docker-compose exec auth env | grep CORS
```

---

## 🐛 Docker Issues

### Docker Out of Memory

**Symptoms:**
```
ERROR: failed to register layer: no space left on device
```

**Solutions:**

1. **Clean up Docker**
```bash
docker system prune -a --volumes
```

2. **Check disk usage**
```bash
df -h
```

3. **Increase Docker resources**
- Docker Desktop → Settings → Resources → Increase Memory/Disk

---

### Volume Mount Not Working

**Symptoms:**
- Code changes not reflecting in container
- Files created in container not on host

**Solutions:**

1. **Check volume mount in docker-compose.yml**
```yaml
volumes:
  - ./services/auth:/app
```

2. **Verify mount in container**
```bash
docker-compose exec auth ls -la /app
```

3. **Check file permissions**
```bash
ls -la services/auth/
```

4. **Recreate container**
```bash
docker-compose up -d --force-recreate auth
```

---

## 📊 Monitoring Issues

### Can't Access Logs

**Symptoms:**
```bash
docker-compose logs -f
# No output
```

**Solutions:**

1. **Check containers are running**
```bash
docker-compose ps
```

2. **View logs for specific service**
```bash
docker logs spotify-collab_auth_1
```

3. **Check log driver**
```bash
docker-compose config | grep logging
```

4. **View logs with tail**
```bash
docker-compose logs --tail=100 auth
```

---

### Metrics Not Available

**Symptoms:**
- Monitoring tools show no data
- Health checks not updating

**Solutions:**

1. **Verify health endpoints**
```bash
curl http://localhost/api/auth/health/
```

2. **Check monitoring configuration**
```bash
# Verify Prometheus/DataDog agents
```

3. **Test endpoint directly**
```bash
docker-compose exec auth curl http://localhost:8001/api/auth/health/
```

---

## 🚀 Performance Issues

### Slow Service Response

**Symptoms:**
- Requests taking > 1 second
- Timeouts

**Solutions:**

1. **Check resource usage**
```bash
docker stats
```

2. **Check database queries**
```bash
docker-compose exec auth uv run python manage.py showmigrations
```

3. **Add database indexes**
```python
# In models.py
class User(models.Model):
    email = models.EmailField(db_index=True)
```

4. **Enable query logging**
```python
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
    },
}
```

---

### High Memory Usage

**Symptoms:**
- Services using > 1GB RAM
- OOM kills

**Solutions:**

1. **Set memory limits**
```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      memory: 512M
```

2. **Restart services**
```bash
docker-compose restart
```

3. **Check for memory leaks**
```bash
docker-compose exec auth uv run python -m memory_profiler manage.py
```

---

## 🔧 Development Issues

### Code Changes Not Reflecting

**Symptoms:**
- Edit code, save, nothing happens

**Solutions:**

1. **Verify hot-reload is working**
```bash
docker-compose logs auth | grep "Reloading"
```

2. **Check file is in mounted directory**
```bash
ls services/auth/authapp/views.py
```

3. **Watch logs for reload**
```bash
docker-compose logs -f auth
# Make a code change
# Should see: "WatchFiles detected changes... Reloading"
```

---

### Import Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'xyz'
```

**Solutions:**

1. **Add to pyproject.toml**
```toml
dependencies = [
    "xyz==1.0.0",
]
```

2. **Rebuild container**
```bash
docker-compose build auth
docker-compose up -d auth
```

3. **Check lockfile**
```bash
uv lock
```

---

## 🆘 Emergency Procedures

### Complete System Reset

```bash
# Stop everything
docker-compose down -v

# Rebuild from scratch
docker-compose build --no-cache

# Start fresh
docker-compose up -d

# Run migrations
docker-compose exec auth uv run python manage.py migrate
# ... repeat for all services
```

### Restore from Backup

```bash
# Database backup
cat backup.sql | docker-compose exec -T db psql -U spotifyuser -d spotifydb

# Code backup
git reset --hard HEAD
git checkout -
```

### Rollback Deployment

```bash
# Git rollback
git log
git reset --hard <commit-hash>

# Docker rollback
docker-compose down
git pull <previous-branch>
docker-compose up -d
```

---

## 📞 Getting Help

### Information to Gather

Before asking for help, gather:

1. **Service status**
```bash
docker-compose ps
```

2. **Recent logs**
```bash
docker-compose logs --tail=50
```

3. **Error messages**
```bash
# Copy full error message
```

4. **What you changed**
```bash
git diff
git log --oneline -5
```

5. **Environment**
```bash
docker --version
docker-compose --version
uname -a
```

### Resources

- **Documentation:** `docs/` folder
- **Quick Reference:** `QUICKREF.md`
- **Deployment Guide:** `DEPLOYMENT.md`
- **Session Notes:** `docs/SESSION-2026-03-26.md`

---

## ✅ Prevention

### Best Practices

1. **Commit frequently** - Small, reversible changes
2. **Test after changes** - Catch issues early
3. **Use health checks** - Monitor service health
4. **Read logs** - First step in debugging
5. **Document decisions** - Future you will thank you

### Pre-Commit Checklist

- [ ] Services running: `docker-compose ps`
- [ ] Health checks passing: `./manage.sh` (option 7)
- [ ] No import errors in logs
- [ ] Database migrations applied
- [ ] Code tested manually

---

**Last Updated:** March 26, 2026
**Version:** 1.0.0
