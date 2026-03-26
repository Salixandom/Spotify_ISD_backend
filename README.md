# Spotify Collab - Microservices Backend

A Spotify-like collaborative playlist application built with Django REST Framework, deployed as microservices with Docker Compose, uv, and Traefik.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Traefik Gateway                          │
│                    (Automatic Service Discovery)                │
└──────────┬────────────┬──────────────┬──────────────────────────┘
           │            │              │
           ▼            ▼              ▼
    ┌──────────┐ ┌──────────┐ ┌──────────────┐
    │   Auth   │ │   Core   │ │ Collaboration│
    │  :8001   │ │  :8002   │ │    :8003     │
    └─────┬────┘ └─────┬────┘ └──────┬───────┘
          │            │               │
          │            │               │
          │      ┌─────┴─────┐         │
          │      │playlistapp│         │
          │      │ trackapp  │         │
          │      │searchapp  │         │
          │      └───────────┘         │
          └────────────┴───────────────┘
                     │
                     ▼
              ┌───────────┐
              │ PostgreSQL │
              │   :5432   │
              └───────────┘
```

**Services:**
- **Auth Service** (8001): User authentication, JWT tokens
- **Core Service** (8002): Playlists, Tracks, and Search (merged into one Django project)
- **Collaboration Service** (8003): Playlist collaboration features

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Git

### Setup (5 minutes)
```bash
# 1. Clone repository
git clone <repo-url>
cd spotify-collab

# 2. Copy environment files
cp .env.example .env
cp services/auth/.env.example services/auth/.env
cp services/core/.env.example services/core/.env
cp services/collaboration/.env.example services/collaboration/.env

# 3. Start services
docker-compose up -d

# 4. Run migrations (first time only)
docker exec spotify-collab_auth_1 uv run python manage.py migrate
docker exec spotify-collab_core_1 uv run python manage.py migrate
docker exec spotify-collab_collaboration_1 uv run python manage.py migrate

# 5. Test
curl http://localhost/api/auth/health/
curl http://localhost/api/core/health/
```

---

## 📍 Service URLs

| Service | Gateway URL | Direct URL | Port | Apps |
|---------|-------------|------------|------|------|
| Auth | http://localhost/api/auth/* | http://localhost:8001 | 8001 | Authentication |
| Core | http://localhost/api/{playlists,tracks,search}/* | http://localhost:8002 | 8002 | Playlist, Track, Search |
| Collaboration | http://localhost/api/collab/* | http://localhost:8003 | 8003 | Collaboration features |

**All API endpoints remain unchanged** - the frontend doesn't need any updates!

**Dashboards & Tools:**
- Traefik Dashboard: http://localhost:8080
- Database: localhost:5432
- Health Checks: http://localhost/api/{auth,core,collab}/health/

---

## 🛠️ Management Tools

### Interactive CLI
```bash
./manage.sh
```

Features:
- Start/Stop/Restart services
- View logs
- Health checks
- Run migrations
- Database operations
- And more!

### Common Commands
```bash
# View all services
docker-compose ps

# View logs
docker-compose logs -f

# Restart service
docker-compose restart auth

# Access service shell
docker-compose exec auth bash

# Run management command
docker-compose exec auth uv run python manage.py createsuperuser

# Interactive menu
./manage.sh
```

---

## 📚 Documentation

- **[QUICKREF.md](../QUICKREF.md)** - Developer cheat sheet
- **[DEPLOYMENT.md](../DEPLOYMENT.md)** - Deployment guide
- **[docs/SESSION-2026-03-26.md](SESSION-2026-03-26.md)** - Session documentation
- **[docs/HEALTH_CHECKS.md](HEALTH_CHECKS.md)** - Health endpoint guide

---

## 🔧 Technology Stack

### Backend
- **Framework:** Django 4.2.17
- **API:** Django REST Framework 3.15.2
- **Authentication:** JWT (djangorestframework-simplejwt)
- **Database:** PostgreSQL 15
- **ASGI Server:** Uvicorn 0.34.0

### Package Management
- **Tool:** uv (fast Python package manager)
- **Lockfiles:** uv.lock (reproducible builds)

### Deployment
- **Orchestration:** Docker Compose
- **Gateway:** Traefik (automatic service discovery)
- **Hot-Reload:** Enabled (code changes auto-apply)

---

## 🔄 Development Workflow

### Making Changes
1. Edit code in `services/{service}/`
2. Hot-reload applies changes automatically (~2-5 seconds)
3. Test at http://localhost/api/{service}/

### Adding New Features
1. Create feature branch: `git checkout -b feature/new-feature`
2. Make changes
3. Test locally
4. Commit: `git commit -m "feat: add new feature"`
5. Push: `git push`
6. Create pull request

### Database Changes
```bash
# Make model changes
# Then run migrations
docker-compose exec auth uv run python manage.py makemigrations
docker-compose exec auth uv run python manage.py migrate
```

---

## 🚢 Deployment

### Local Development
```bash
docker-compose up -d
```

### Production (Render.com)
1. Update `render.yaml` with your domains
2. Push to GitHub
3. Render → New Blueprint → Connect repo

### Production (Self-Hosted)
```bash
# Generate secrets
./scripts/generate-secrets.sh

# Deploy
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for detailed instructions.

---

## 🧪 Testing

### Health Checks
```bash
# All services
curl http://localhost/api/auth/health/
curl http://localhost/api/playlists/health/
curl http://localhost/api/tracks/health/
curl http://localhost/api/search/health/
curl http://localhost/api/collab/health/

# Or use the management CLI
./manage.sh
# Select option 7 (Health check all)
```

### Test Endpoints
```bash
# Auth service
curl -X POST http://localhost/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","email":"test@example.com","password":"pass123"}'

# Login
curl -X POST http://localhost/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"test","password":"pass123"}'
```

---

## 📊 Service Status

Check all services:
```bash
docker-compose ps
```

Expected output:
```
NAME                           STATUS    PORTS
spotify-collab_auth_1         Up       0.0.0.0:8001->8001/tcp
spotify-collab_playlist_1     Up       0.0.0.0:8002->8002/tcp
spotify-collab_track_1        Up       0.0.0.0:8003->8003/tcp
spotify-collab_search_1       Up       0.0.0.0:8004->8004/tcp
spotify-collab_collaboration_1 Up       0.0.0.0:8003->8003/tcp
spotify-collab_db_1           Up       0.0.0.0:5432->5432/tcp
spotify-collab_traefik_1      Up       0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp, 0.0.0.0:8080->8080/tcp
```

---

## 🐛 Troubleshooting

### Services Not Starting
```bash
# Check logs
docker-compose logs -f

# Restart services
docker-compose restart

# Clean restart (removes volumes)
docker-compose down -v
docker-compose up -d
```

### Database Connection Errors
```bash
# Check database is running
docker-compose ps db

# Restart database
docker-compose restart db

# Check database logs
docker-compose logs db
```

### Routing Issues
```bash
# Check Traefik logs
docker-compose logs traefik

# Access Traefik dashboard
open http://localhost:8080

# Test direct access
curl http://localhost:8001/api/auth/health/
```

See [docs/HEALTH_CHECKS.md](HEALTH_CHECKS.md) for more troubleshooting.

---

## 🤝 Contributing

### Git Workflow
1. Create branch: `git checkout -b feature/your-feature`
2. Make changes
3. Test thoroughly
4. Commit: `git commit -m "feat: add your feature"`
5. Push: `git push`
6. Create pull request

### Code Style
- Follow PEP 8
- Use descriptive commit messages
- Add docstrings to functions
- Write tests for new features

---

## 📝 License

[Your License Here]

---

## 👥 Team

- **Developer:** Sakib + Taskeen + Raiyan + Mesbah + Arian + Mehedi
- **Architecture:** Microservices with Django REST Framework
- **Deployment:** Docker Compose + Traefik

---

**Last Updated:** March 26, 2026
**Version:** 1.0.0
