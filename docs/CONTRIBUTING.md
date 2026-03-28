# Contributing to Spotify ISD Backend

## Welcome! 👋

We're excited to have you contribute to the Spotify ISD backend services. This document will help you get started and understand our workflow.

## Team Size: 6 Developers

With multiple developers working simultaneously, we use strict CI/CD processes to prevent broken builds, merge conflicts, and deployment issues.

## Architecture

We have **3 services** running in Docker:

1. **Auth Service** (port 8001) - Authentication & authorization
2. **Core Service** (port 8002) - Playlists, tracks, search
3. **Collaboration Service** (port 8003) - Collaborative playlists

All services share a PostgreSQL database.

## Branch Strategy

We use a simplified Git flow:

- **`main`** = Production branch (protected)
- **`develop`** = Integration branch (optional)
- **`feature/*`** = New features
- **`bugfix/*`** = Bug fixes
- **`hotfix/*`** = Urgent production fixes

## Workflow

### 1. Start a New Feature

```bash
# Always start from the latest main
git checkout main
git pull origin main

# Create your feature branch
git checkout -b feature/your-feature-name
```

### 2. Make Changes

```bash
# Make your changes to a service
cd services/auth  # or core, or collaboration

# Test locally with Docker
docker-compose up auth-service

# When done, commit
git add .
git commit -m "feat: add your descriptive message"
```

**Commit message format:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `test:` - Adding tests
- `chore:` - Maintenance tasks

**Which service?** Include service name in commit:
```
feat(auth): add OAuth login
fix(core): resolve playlist search bug
fix(collab): handle concurrent edits
```

### 3. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub.

### 4. CI Checks

Your PR will automatically run these checks:
- ✅ Docker build test (all 3 services)
- ✅ Python linting (flake8, black)
- ✅ Merge conflict detection
- ✅ Branch up-to-date check

**All checks must pass before merge.**

### 5. Code Review

- At least **1 team member** must approve your PR
- Address all review comments
- Update PR as needed

### 6. Merge

Once approved and all checks pass:
- Click "Merge pull request"
- Use "Squash and merge" to keep history clean
- Delete your branch after merging
- **Auto-deploys to Render production**

## Required CI Checks

### What Gets Checked

1. **Docker Build**
   - Verifies all 3 services build successfully
   - Catches Dockerfile errors
   - Tests dependency installation

2. **Python Linting** (flake8)
   - Code style and syntax errors
   - Catches common Python mistakes

3. **Code Formatting** (black)
   - Enforces consistent code style
   - Must pass before merge

4. **Merge Conflicts**
   - Automatically detects conflicts with `main`
   - Comments on PR if conflicts found

5. **Branch Up-to-Date**
   - Ensures your branch has latest `main` changes
   - Prompts you to merge if behind

## Local Development

### Starting Services

```bash
# Start all services
docker-compose up

# Start specific service
docker-compose up auth-service
docker-compose up core-service
docker-compose up collab-service

# Start in detached mode
docker-compose up -d
```

### Testing Health Endpoints

```bash
# Auth Service
curl http://localhost:8001/health

# Core Service
curl http://localhost:8002/health

# Collaboration Service
curl http://localhost:8003/health
```

### Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f auth-service
```

## Automatic Deployments

### Render Deployment

Merging to `main` automatically deploys all services to **Render production**.

### Health Checks

After deployment, CI automatically verifies all services are healthy:
- Auth service health check
- Core service health check
- Collaboration service health check

**If health checks fail:** CI creates a GitHub issue automatically.

## Setup Secrets

For CI/CD to work, add these secrets in GitHub repo settings (`Settings → Secrets and variables → Actions`):

### Required for Backend

```
RENDER_API_KEY=your_render_api_key
RENDER_SERVICE_ID=your_service_id
AUTH_SERVICE_URL=https://auth-service.onrender.com
CORE_SERVICE_URL=https://core-service.onrender.com
COLLAB_SERVICE_URL=https://collab-service.onrender.com
```

**How to get Render API key:**
1. Go to https://dashboard.render.com
2. Click Settings → API Keys
3. Create new API key
4. Add to GitHub Secrets

**How to get Service ID:**
1. Go to your service on Render dashboard
2. Copy the service ID from URL
3. Format: `srv-xxxxxxxxxxxxxxxx`

## Merge Conflict Prevention

Our CI automatically detects merge conflicts. If found:

1. **Don't panic!** This is normal with 6 developers
2. Update your branch:
   ```bash
   git fetch origin main
   git merge origin/main
   ```
3. Resolve conflicts manually
4. Commit and push
5. CI will re-run automatically

## Testing Locally Before Push

Always test locally before pushing:

```bash
# Build Docker images
docker-compose build

# Start services
docker-compose up

# Test health endpoints
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health

# Run linting
cd services/auth
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
black --check .
```

## Service-Specific Guidelines

### Auth Service
- Handles JWT tokens and user registration
- **Never commit secret keys** — use environment variables for secrets
- The Django built-in `User` model is used directly; do not add a custom model

### Core Service — 4 Django apps

| App | Responsibility |
|-----|----------------|
| `searchapp` | Global music catalog: `Artist`, `Album`, `Song` with full FK relationships |
| `playlistapp` | User playlists with `cover_url`, `max_songs`, sort support |
| `trackapp` | Junction table linking Playlist ↔ Song; enforces `max_songs` and `unique_together` |
| `historyapp` | Per-user play events; drives "recently played" endpoint |

- Cross-service user references (`owner_id`, `added_by_id`, `user_id`) are plain `IntegerField` — **never add ForeignKey to auth_user from core**
- `Track` (model class) and `trackapp_track` (table) — do not rename to `PlaylistTrack`
- `Song` (catalog entry) vs `Track` (playlist junction) — these are different things; keep the naming consistent

### Collaboration Service — 2 Django apps

| App | Responsibility |
|-----|----------------|
| `collabapp` | `Collaborator` records and `InviteLink` tokens; joining via invite grants edit access |
| `shareapp` | `ShareLink` tokens; accessing via share link grants view-only access (no Collaborator record created) |

- Invite and share links auto-expire after **30 days** — there is no manual deactivation endpoint
- `is_valid` property on both `InviteLink` and `ShareLink` checks both `is_active` AND `expires_at` — always use `is_valid` in view logic, never `is_active` alone
- `playlist_id` and `created_by_id` are plain `IntegerField` — cross-service references, no FK possible

## Common Issues

### "Docker build failed"

```bash
# Test locally
docker-compose build auth-service

# Check Dockerfile syntax
docker build -f services/auth/Dockerfile ./services/auth
```

### "Branch is behind main"

```bash
git fetch origin main
git merge origin/main
# Resolve any conflicts
git push
```

### "flake8 linting errors"

```bash
cd services/auth

# Auto-fix some issues
black .

# Run flake8 to see errors
flake8 .
```

### "Health check failed after deployment"

1. Check Render dashboard for service logs
2. Verify environment variables are set
3. Check database connectivity
4. Review recent code changes

## Deployment Safety

### Pre-Deployment Checklist

Before merging to `main`:

- [ ] All CI checks pass
- [ ] Code reviewed by 1+ team member
- [ ] Tested locally with Docker
- [ ] Health endpoints respond correctly
- [ ] No console errors in logs
- [ ] Database migrations tested (if applicable)

### Rollback Procedure

If deployment breaks production:

```bash
# Go to Render dashboard
# Find previous deployment
# Click "Rollback" to revert

# Or rollback via CLI (if configured)
render rollback <service-id>
```

## Questions?

- Check the [GitHub Issues](https://github.com/your-org/spotify-collab/issues)
- Ask in team chat/Slack
- Check Render dashboard for deployment logs
- Review service logs: `docker-compose logs -f <service>`

## Happy Contributing! 🎉
