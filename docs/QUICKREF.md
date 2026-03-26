# Quick Reference: Environment Setup

## 🚀 For New Developers

### Step 1: Clone Repository
```bash
# Clone the repository
git clone https://github.com/Salixandom/Spotify_ISD_backend.git
cd spotify-collab

# Always work on a member branch (never on main!)
git checkout -b "member/your-name"
```

### Step 2: Environment Setup
```bash
# Copy env templates (uses safe defaults for local development)
cp .env.example .env
cp services/auth/.env.example services/auth/.env
cp services/core/.env.example services/core/.env
cp services/collaboration/.env.example services/collaboration/.env

./manage.sh
```

### Step 3: Start Services
```bash
# Start all services
docker-compose up -d

# Run migrations (first time only)
docker exec spotify-collab_auth_1 uv run python manage.py migrate
docker exec spotify-collab_core_1 uv run python manage.py migrate
docker exec spotify-collab_collaboration_1 uv run python manage.py migrate
```

### Step 4: Start Coding
```bash
# Edit files, hot-reload works automatically!
# Changes reflect in ~2 seconds
```

## 🔄 Quick Commands

| Command | Description |
|---------|-------------|
| `docker-compose up -d` | Start all services |
| `docker-compose down` | Stop all services |
| `docker-compose logs -f` | View all logs |
| `docker-compose restart auth` | Restart auth service |
| `docker-compose ps` | Check service status |
| `docker exec -it spotify-collab_auth_1 bash` | Shell into auth service |

## 🔗 Service URLs

- **Auth**: http://localhost/api/auth/
- **Playlist**: http://localhost/api/playlists/
- **Track**: http://localhost/api/tracks/
- **Search**: http://localhost/api/search/
- **Collaboration**: http://localhost/api/collab/
- **Traefik Dashboard**: http://localhost:8080

---

## 🔄 Git Workflow (Complete)

### Standard Feature Development Cycle

```bash
# 1. Make sure you're on main and it's up to date
git checkout main
git fetch origin
git pull origin main

# 2. Create a new feature branch
git checkout -b feature/your-feature-name

# 3. Make your changes and commit
# Edit files...
git add .
git commit -m "feat: add user authentication"

# 4. Keep your branch updated with main
git fetch origin
git merge origin/main

# 5. Push your branch
git push -u origin feature/your-feature-name

# 6. Create Pull Request
# Go to GitHub/GitLab/Bitbucket and create a PR
```

### Branch Naming Conventions

| Type | Format | Example |
|------|--------|---------|
| Feature | `feature/what-it-does` | `feature/user-authentication` |
| Bug fix | `fix/what-it-fixes` | `fix/login-validation-error` |
| Hotfix | `hotfix/critical-issue` | `hotfix/security-patch` |
| Refactor | `refactor/what-you-refactored` | `refactor/user-model-structure` |
| Documentation | `docs/what-it-documents` | `docs/api-endpoint-guide` |
| Test | `test/what-it-tests` | `test/user-service-tests` |
| Chore | `chore/what-it-does` | `chore/update-dependencies` |

### Commit Message Conventions

```bash
# Format: <type>: <description>

feat: add playlist sharing feature
fix: resolve token expiration bug
docs: update deployment guide
refactor: simplify user model
test: add integration tests for auth service
chore: upgrade Django to 4.2.17
perf: optimize database queries
style: format code with black
```

### Common Git Commands

| Command | Description |
|---------|-------------|
| `git status` | See what files changed |
| `git add .` | Stage all changes |
| `git add <file>` | Stage specific file |
| `git commit -m "message"` | Commit staged changes |
| `git log --oneline` | See commit history |
| `git diff` | See unstaged changes |
| `git diff --staged` | See staged changes |
| `git branch` | List all branches |
| `git branch -a` | List all branches (including remote) |
| `git checkout -b <branch>` | Create and switch to new branch |
| `git checkout <branch>` | Switch to existing branch |
| `git merge <branch>` | Merge branch into current branch |
| `git fetch` | Fetch updates from remote |
| `git pull` | Fetch and merge updates |
| `git push` | Push commits to remote |
| `git push -u origin <branch>` | Push and set upstream |

### Resolving Merge Conflicts

```bash
# 1. When merging, if conflicts occur:
git merge origin/main

# 2. Open conflicted files and look for:
<<<<<<< HEAD
Your changes
=======
Their changes
>>>>>>> origin/main

# 3. Edit to keep what you want, remove markers

# 4. Mark as resolved
git add <resolved-file>

# 5. Complete the merge
git commit

# 6. Push
git push
```

### Undo Mistakes

```bash
# Unstage a file
git restore --staged <file>

# Discard changes to a file
git restore <file>

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes)
git reset --hard HEAD~1

# Undo multiple commits
git reset --hard HEAD~3

# See commit that was before
git reflog
git reset --hard <commit-hash>
```

### Team Collaboration Workflow

```bash
# Before starting work each day
git checkout main
git pull origin main
git checkout -b feature/new-feature

# While working
git add .
git commit -m "progress: add authentication logic"

# After finishing for the day
git push origin feature/new-feature

# When ready for review
git push origin feature/new-feature
# Create PR on GitHub/GitLab

# After PR is approved and merged
git checkout main
git pull origin main
git branch -d feature/new-feature  # Delete local branch
git push origin --delete feature/new-feature  # Delete remote branch
```

## 📝 Adding New Environment Variables

1. Add to `services/<service>/.env.example`
2. Add to service's actual `.env` file
3. Use in code: `os.environ.get('VAR_NAME')`
4. No restart needed for code changes!

**Important:** Never commit `.env` files to git!

```bash
# Make sure .gitignore includes:
.env
services/*/.env
```

## 🚢 Quick Deploy to Render

```bash
# 1. Update render.yaml with your values
# 2. Commit and push
git add render.yaml
git commit -m "Add Render config"
git push

# 3. Go to render.com → New Blueprint → Connect repo
# Done! ✅
```

## 🔐 Production Secrets

```bash
# Generate secure secrets
./scripts/generate-secrets.sh

# Update each service's .env with:
# - DB_HOST (production database)
# - ALLOWED_HOSTS (your domain)
# - CORS_ALLOWED_ORIGINS (your frontend)
# - SECRET_KEY (from script output)
```

---

**Need help?** Check `DEPLOYMENT.md` for detailed deployment guide.
