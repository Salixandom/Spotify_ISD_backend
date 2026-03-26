# Deployment Guide

## 🚀 Quick Start

### Local Development
```bash
# Copy example env files
cp .env.example .env
cp services/auth/.env.example services/auth/.env
cp services/core/.env.example services/core/.env
cp services/collaboration/.env.example services/collaboration/.env

# Start services (migrations run automatically via entrypoint)
docker-compose up -d

# Migrations are now automatic! But you can still run manually if needed:
./manage.sh  # Option 9: Run migrations
```

---

## 📦 Production Deployment

### Option 1: Self-Hosted (Docker Compose)

**Step 1: Prepare Production Environment**
```bash
# Generate secure secrets
export SECRET_KEY=$(openssl rand -hex 32)
export DB_PASSWORD=$(openssl rand -hex 16)

# Create production env files
cat > services/auth/.env << EOF
SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=your-domain.com,.onrender.com
DB_HOST=your-db-host
DB_NAME=spotifydb
DB_USER=spotifyuser
DB_PASSWORD=$DB_PASSWORD
CORS_ALLOWED_ORIGINS=https://your-frontend.com
EOF
```

**Step 2: Deploy**
```bash
# Use production config
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Run migrations (auto-migrations are DISABLED in production for safety)
docker-compose exec auth uv run python manage.py migrate
docker-compose exec core uv run python manage.py migrate
docker-compose exec collaboration uv run python manage.py migrate

# Or use the management script:
./manage.sh  # Option 9: Run migrations
```

**Step 3: Configure SSL (Automatic)**
```bash
# Set your email for Let's Encrypt
export ACME_EMAIL=your@email.com

# Traefik will auto-generate SSL certificates
# Ensure ports 80 and 443 are open
```

---

### Option 2: Render.com

**Step 1: Prepare Repository**
```bash
# Add render.yaml to git root
git add render.yaml
git commit -m "Add Render deployment config"
git push
```

**Step 2: Deploy on Render**
1. Go to [render.com](https://render.com)
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. Render will detect `render.yaml` and deploy all services

**Step 3: Update Environment**
After deployment:
1. Go to Render Dashboard
2. Update `CORS_ALLOWED_ORIGINS` with your frontend URL
3. Update `ALLOWED_HOSTS` with your domain
4. Add custom domains in each service's Settings

---

### Option 3: AWS ECS / Kubernetes

**For ECS:** Use `docker-compose.prod.yml` with ECS CLI:
```bash
ecs-cli compose --file docker-compose.yml --file docker-compose.prod.yml up
```

**For Kubernetes:** Convert to Kubernetes manifests:
```bash
kompose convert -f docker-compose.yml -f docker-compose.prod.yml
kubectl apply -f kube-manifests/
```

---

## 🔧 Environment Variables

### Required Variables (All Services)

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `SECRET_KEY` | Django secret key | `openssl rand -hex 32` | ✅ Yes |
| `DEBUG` | Debug mode | `False` (prod) / `True` (dev) | ✅ Yes |
| `ALLOWED_HOSTS` | Allowed hosts | `*.onrender.com,api.example.com` | ✅ Yes |
| `DB_HOST` | Database host | `db` (local) / `postgres.prod.com` | ✅ Yes |
| `DB_PORT` | Database port | `5432` | ✅ Yes |
| `DB_NAME` | Database name | `spotifydb` | ✅ Yes |
| `DB_USER` | Database user | `spotifyuser` | ✅ Yes |
| `DB_PASSWORD` | Database password | Secure password | ✅ Yes |
| `CORS_ALLOWED_ORIGINS` | CORS origins | `https://example.com` | ✅ Yes |

### Service-Specific Variables

**Auth Service:**
- `JWT_ACCESS_TOKEN_LIFETIME`: Token lifetime in minutes (default: 60)
- `JWT_REFRESH_TOKEN_LIFETIME`: Refresh token lifetime (default: 1440)

**Core Service:**
- `AUTH_SERVICE_URL`: Auth service URL for token validation (default: `http://auth:8001`)
- `COLLAB_SERVICE_URL`: Collaboration service URL (default: `http://collaboration:8003`)

**Collaboration Service:**
- `AUTH_SERVICE_URL`: Auth service URL for token validation

**Migration Control (All Services):**
- `RUN_MIGRATIONS`: Enable/disable automatic migrations on container startup (default: `true` in dev, `false` in production)
  - Development: Migrations run automatically for convenience
  - Production: Set to `false` for manual control, then run migrations via `./manage.sh` or CI/CD

---

## 🔒 Security Checklist

Before deploying to production:

- [ ] Change all `SECRET_KEY` values to secure random strings
- [ ] Set `DEBUG=False` in all services
- [ ] Set `ALLOWED_HOSTS` to your actual domain
- [ ] Set `CORS_ALLOWED_ORIGINS` to your frontend URL only
- [ ] Enable SSL/TLS (automatic with Traefik or Render)
- [ ] Set strong database passwords
- [ ] Restrict database port (5432) from public access
- [ ] Enable `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`
- [ ] Configure health checks
- [ ] Set up monitoring and logging
- [ ] Configure backup strategy for database

---

## 📊 Monitoring

### Check Service Health
```bash
# Local
docker-compose ps

# Production with health checks
docker-compose exec auth curl -f http://localhost:8001/api/auth/ || echo "Auth service down"

# Render
curl https://auth-yourdomain.onrender.com/api/auth/
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f auth

# Render
# Use Render Dashboard → Logs
```

---

## 🔄 Updates & Migrations

### Automatic vs Manual Migrations

**Development (Automatic):**
- Migrations run automatically on container startup via entrypoint script
- The entrypoint waits for PostgreSQL to be ready before running migrations
- Set `RUN_MIGRATIONS=false` in service `.env` to disable if needed

**Production (Manual):**
- Auto-migrations are disabled by default for safety
- Run migrations manually before or after deployment:
  ```bash
  # Option 1: Via management script
  ./manage.sh  # Select "Run migrations"

  # Option 2: Direct execution
  docker-compose exec auth uv run python manage.py migrate
  docker-compose exec core uv run python manage.py migrate
  docker-compose exec collaboration uv run python manage.py migrate
  ```

### Deploying Updates
```bash
# Pull latest code
git pull

# Rebuild services
docker-compose build auth core collaboration

# Restart with no downtime (auto-migrations run in dev)
docker-compose up -d --no-deps --build auth
docker-compose up -d --no-deps --build core
docker-compose up -d --no-deps --build collaboration

# Production: Run migrations manually after services are up
./manage.sh  # Select "Run migrations"
```

---

## 🆘 Troubleshooting

### Services can't connect to database
```bash
# Check database is running
docker-compose ps db

# Check network
docker network inspect spotify-collab_default

# Test connection from service
docker-compose exec auth nc -zv db 5432
```

### Traefik not routing
```bash
# Check Traefik logs
docker-compose logs traefik

# Check Traefik dashboard
open http://localhost:8080

# Verify service labels
docker inspect spotify-collab_auth_1 | grep -A 10 Labels
```

### CORS errors
1. Check `CORS_ALLOWED_ORIGINS` includes your frontend URL
2. Verify `ALLOWED_HOSTS` includes the calling domain
3. Check Traefik is passing `X-Forwarded-Proto` header

### Migration issues
```bash
# Run makemigrations inside container
docker-compose exec auth uv run python manage.py makemigrations

# Check migration status
docker-compose exec auth uv run python manage.py showmigrations
```

---

## 📞 Support

For issues:
1. Check logs: `docker-compose logs -f [service-name]`
2. Check health: `docker-compose ps`
3. Review this guide's troubleshooting section
4. Check service-specific `.env.example` files
