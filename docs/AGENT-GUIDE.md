# AI Agent Guide: Spotify ISD Backend

**Purpose**: Quick reference for AI agents working on this codebase
**Last Updated**: March 26, 2026
**Project Stack**: Django 4.2, Docker, PostgreSQL/Supabase, microservices architecture

---

## 🚀 Quick Start for Agents

### First Steps When Starting Work

1. **Read session documentation first** - Always check the most recent session docs:
   ```bash
   ls -lt docs/SESSION-*.md | head -5
   # Read the latest 2-3 session files to understand recent context
   ```

2. **Check current service architecture**:
   ```bash
   # 3 microservices (consolidated from 5)
   ls -d services/*/
   # Output: auth/ core/ collaboration/
   ```

3. **Understand the environment setup**:
   - Development: Docker PostgreSQL with individual env vars
   - Production: Supabase-ready (uses DATABASE_URL)
   - Package manager: `uv` (not pip/poetry)
   - Migration system: Automatic via entrypoint scripts

---

## 📋 Command Patterns

### Running Commands Inside Services

**Pattern 1: Django Management Commands**
```bash
# General pattern
docker-compose exec -T <service> uv run python manage.py <command>

# Examples:
docker-compose exec -T auth uv run python manage.py migrate
docker-compose exec -T auth uv run python manage.py createsuperuser
docker-compose exec -T auth uv run python manage.py makemigrations
docker-compose exec -T auth uv run python manage.py showmigrations
docker-compose exec -T core uv run python manage.py shell
```

**Pattern 2: One-off Commands (Non-interactive)**
```bash
# Use -T flag to disable TTY allocation
docker-compose exec -T <service> uv run python -c "print('hello')"
```

**Pattern 3: Interactive Shell Access**
```bash
# Get a shell inside a running service
docker-compose exec auth bash
# or
docker-compose exec core sh

# Then run commands directly inside
uv run python manage.py check
```

**Pattern 4: Service Management**
```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d auth

# View logs
docker-compose logs -f auth

# Restart service
docker-compose restart auth

# Rebuild and restart
docker-compose build auth && docker-compose up -d auth
```

---

## 🎯 Service Architecture

### Current Structure (3-Service Architecture)

```
spotify-collab/
├── services/
│   ├── auth/          # Port 8001
│   │   ├── Dockerfile
│   │   ├── docker-entrypoint.sh    # Auto-runs migrations
│   │   ├── core/
│   │   │   ├── settings.py          # Dj-database-url support
│   │   │   ├── urls.py
│   │   │   └── wsgi.py / asgi.py
│   │   ├── authapp/                  # Django app
│   │   ├── manage.py
│   │   ├── pyproject.toml            # uv dependencies
│   │   └── .env / .env.example
│   │
│   ├── core/          # Port 8002
│   │   ├── Dockerfile
│   │   ├── docker-entrypoint.sh
│   │   ├── core/
│   │   │   ├── settings.py
│   │   │   └── ...
│   │   ├── playlistapp/              # Django app
│   │   ├── trackapp/                 # Django app
│   │   ├── searchapp/                # Django app
│   │   ├── manage.py
│   │   ├── pyproject.toml
│   │   └── .env / .env.example
│   │
│   └── collaboration/ # Port 8003
│       ├── Dockerfile
│       ├── docker-entrypoint.sh
│       ├── core/
│       │   ├── settings.py
│       │   └── ...
│       ├── collabapp/                # Django app
│       ├── manage.py
│       ├── pyproject.toml
│       └── .env / .env.example
│
├── docker-compose.yml                 # Development config
├── docker-compose.prod.yml            # Production overrides
├── render.yaml                        # Render deployment (Supabase)
├── manage.sh                           # Interactive management CLI
└── docs/
    ├── SESSION-2026-03-26 4.md        # Latest session (this work)
    ├── MIGRATION-WORKFLOW.md          # Migration guide
    └── SUPABASE-MIGRATION.md          # Supabase guide
```

### Key Points

- **Entryport scripts**: All services have `docker-entrypoint.sh` that:
  - Waits for database to be ready
  - Runs migrations automatically (unless `RUN_MIGRATIONS=false`)
  - Then starts the application

- **Package manager**: Uses `uv` (not pip)
  - Install dependencies: `uv sync` (local) or handled automatically in Docker
  - Add dependency: Edit `pyproject.toml`, then `uv sync`

- **Database configuration**: Supports BOTH:
  - Individual env vars: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
  - Single DATABASE_URL: For Supabase or external databases
  - Code auto-detects which to use

---

## 🔧 Common Tasks for Agents

### Task 1: Running Migrations

```bash
# Option A: Automatic (via entrypoint)
docker-compose up -d auth core collaboration
# Migrations run automatically on startup

# Option B: Manual (via manage.sh)
./manage.sh
# Select: 10) Run migrations

# Option C: Direct command
docker-compose exec -T auth uv run python manage.py migrate
docker-compose exec -T core uv run python manage.py migrate
docker-compose exec -T collaboration uv run python manage.py migrate
```

### Task 2: Creating New Migrations

```bash
# After modifying models
./manage.sh
# Select: 9) Make migrations
# Select service (auth/core/collaboration)

# Or directly:
docker-compose exec -T core uv run python manage.py makemigrations
```

### Task 3: Checking Service Health

```bash
# Check if services are running
docker-compose ps

# Check health endpoints
curl http://localhost/api/auth/health/
curl http://localhost/api/core/health/
curl http://localhost/api/collab/health/
```

### Task 4: Accessing Django Shell

```bash
# Open Python shell with Django context loaded
docker-compose exec -T core uv run python manage.py shell

# Example usage:
# >>> from playlistapp.models import Playlist
# >>> Playlist.objects.all()
```

### Task 5: Viewing Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f auth

# Last 100 lines
docker-compose logs --tail=100 auth
```

### Task 6: Rebuilding Services

```bash
# After code changes
docker-compose build auth
docker-compose up -d auth

# Or rebuild all
docker-compose build
docker-compose up -d
```

---

## 📚 Context Sources (Always Check These!)

### 1. Session Documentation (Most Important)
```bash
# Latest session has the most recent context
ls -lt docs/SESSION-*.md

# Read the most recent 2-3 sessions
# They contain: what was done, decisions made, files changed
```

**Why**: Session docs capture:
- What features were implemented
- Why certain architectural decisions were made
- Migration history and breaking changes
- Known issues and workarounds
- Team conventions and patterns

### 2. Service-Specific Docs
```
docs/DEPLOYMENT.md          # Deployment procedures
docs/MIGRATION-WORKFLOW.md  # How migrations work
docs/SUPABASE-MIGRATION.md   # Supabase setup guide
docs/TROUBLESHOOTING.md     # Common issues
docs/QUICKREF.md            # Quick reference
```

### 3. Environment Files
```bash
# Check .env.example files to understand configuration
services/auth/.env.example
services/core/.env.example
services/collaboration/.env.example
```

### 4. Root Level Documentation
```bash
# Main project README
README.md

# Contribution guidelines
CONTRIBUTING.md

# CI/CD setup
CI-CD-SUMMARY.md
CICD-SETUP.md
```

---

## ⚠️ Critical Gotchas for Agents

### Database Configuration

**Gotcha**: Services support TWO database configuration methods

```python
# In settings.py - checks DATABASE_URL first
if os.environ.get('DATABASE_URL'):
    # Supabase or external database
    DATABASES = { 'default': dj_database_url.config(...) }
else:
    # Docker PostgreSQL with individual vars
    DATABASES = { 'default': { 'HOST': ..., 'PORT': ... } }
```

**What to remember**:
- Development uses individual env vars (`DB_HOST`, `DB_PORT`, etc.)
- Production uses `DATABASE_URL` (Supabase)
- Don't assume one or the other - check the environment
- Both work transparently, code handles both

### Package Manager: uv NOT pip

**Gotcha**: This project uses `uv` package manager

```bash
# ❌ WRONG
pip install django
python manage.py migrate

# ✅ RIGHT
uv sync  # Installs from pyproject.toml
uv run python manage.py migrate
```

**Why**: `uv` is faster and manages dependencies differently than pip

### Entrypoint Scripts

**Gotcha**: All services have entrypoint scripts that run migrations

```bash
# When you start services, migrations run AUTOMATICALLY
docker-compose up -d

# Entry script flow:
# 1. Wait for database
# 2. Run migrations (if RUN_MIGRATIONS=true)
# 3. Start application
```

**What to remember**:
- Don't manually run migrations in development (already automatic)
- Production has `RUN_MIGRATIONS=false` for safety
- To skip migrations: `RUN_MIGRATIONS=false docker-compose up -d`

### Service Ports

**Gotcha**: Services use specific ports

```
auth: 8001
core: 8002
collaboration: 8003
```

**Why it matters**:
- Docker Compose forwards these ports to host
- Changing ports requires updating docker-compose.yml
- Traefik routing rules use these ports

### Microservices Communication

**Gotcha**: Services communicate via HTTP, not direct function calls

```python
# In core service, calling auth service:
AUTH_SERVICE_URL = os.environ.get('AUTH_SERVICE_URL', 'http://auth:8001')
response = requests.get(f'{AUTH_SERVICE_URL}/api/auth/me/')
```

**What to remember**:
- Services are loosely coupled via HTTP APIs
- Use service names (`auth`, `core`) as hostnames in Docker
- Service URLs are configurable via environment variables

---

## 🎨 Code Patterns to Follow

### Adding New Dependencies

1. Edit `pyproject.toml`:
   ```toml
   [project]
   dependencies = [
       # ... existing deps ...
       "new-package>=1.0.0",
   ]
   ```

2. Run `uv sync` to install

3. Rebuild Docker image:
   ```bash
   docker-compose build <service>
   ```

### Creating New Django Apps

```bash
# Inside the service directory
docker-compose exec -T core uv run python startapp mynewapp
```

### Environment Variable Patterns

**Service-specific**: Add to `services/<service>/.env`
```bash
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=postgresql://...
```

**Shared across services**: Add to `docker-compose.yml` under `environment:`

### Testing Changes

```bash
# 1. Make code changes

# 2. Rebuild service
docker-compose build auth

# 3. Restart service
docker-compose up -d auth

# 4. Check logs for errors
docker-compose logs -f auth

# 5. Test endpoints
curl http://localhost/api/auth/health/
```

---

## 🔍 Debugging Guide for Agents

### When Commands Fail

**Step 1: Check if service is running**
```bash
docker-compose ps
# Look for "Up" status
```

**Step 2: Check service logs**
```bash
docker-compose logs auth
# Look for errors, traceback, startup issues
```

**Step 3: Verify environment variables**
```bash
docker-compose exec auth env | grep -E 'DB_|SECRET_KEY'
# Ensure required vars are set
```

**Step 4: Test database connection**
```bash
docker-compose exec auth uv run python manage.py check
# Django will report database connection issues
```

**Step 5: Common Issues**

| Symptom | Likely Cause | Fix |
|---------|---------------|-----|
| Service won't start | Missing env var | Check `.env` file exists and is configured |
| Migration fails | Database not ready | Wait a few seconds, retry (entrypoint handles this) |
| Import errors | Missing dependency | Run `uv sync` and rebuild |
| Port already in use | Old container running | `docker-compose down` then `docker-compose up -d` |
| Permission errors | Wrong user on files | Check file ownership in `.venv` or mounted volumes |

---

## 📝 Making Changes: Best Practices

### Before Making Changes

1. **Read recent session docs** - Understand what's been done
2. **Check the affected files** - Use `Read` tool, don't guess
3. **Understand the pattern** - Look at similar existing code

### When Editing Code

1. **Follow existing patterns** - Don't introduce new patterns without reason
2. **Keep changes minimal** - Only change what's necessary
3. **Test after changes** - Rebuild and verify service starts

### When Working with Migrations

1. **Always create migrations before asking user to push** - Don't leave uncommitted migrations
2. **Use manage.sh Option 9** - Not manual commands
3. **Review generated migrations** - Check they look correct
4. **Test migrations in dev** - Ensure they apply cleanly

**⚠️ GIT POLICY**: After creating migrations, **ASK USER** to commit and push. Never run git commands yourself.

### When Adding Features

1. **Check if feature spans services** - May need API design
2. **Consider service boundaries** - Keep logic in appropriate service
3. **Update documentation** - Document new features in session docs
4. **Test end-to-end** - Verify full flow works

---

## 🔄 CI/CD Pre-Commit Checklist (CRITICAL!)

**BEFORE pushing or creating PRs, ALWAYS run these checks locally to avoid CI failures:**

### ✅ Mandatory Pre-Push Checks

#### 1. Linting with Flake8 (Syntax Errors Only)

**Why**: CI runs flake8 to catch actual syntax errors and undefined names

```bash
# Install flake8 (one-time setup)
python3 -m pip install --break-system-packages --user flake8 -q

# Check each service for syntax errors
flake8 services/auth/ --exclude=".venv,.git,__pycache__,.uv,migrations,dist,build,*.egg-info" --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 services/core/ --exclude=".venv,.git,__pycache__,.uv,migrations,dist,build,*.egg-info" --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 services/collaboration/ --exclude=".venv,.git,__pycache__,.uv,migrations,dist,build,*.egg-info" --count --select=E9,F63,F7,F82 --show-source --statistics
```

**What this catches** (actual errors, not style):
- Syntax errors (E9)
- Undefined names (F63, F82)
- Missing imports (F7)

**Note**: Flake8 in CI only checks syntax errors, not code style or formatting

#### 2. Verify UV Lockfiles are Committed

**Why**: Docker builds FAIL in CI if `uv.lock` files are missing

```bash
# Check if uv.lock files are tracked by git
git status services/*/uv.lock
```

**If uv.lock files show as "untracked"**:
→ **ASK USER** to add them:
```
"⚠️ The uv.lock files are not committed to git. This will cause Docker build failures in CI.
Please add them:
git add services/auth/uv.lock services/core/uv.lock services/collaboration/uv.lock"
```

**Critical**: `.gitignore` has `uv.lock` commented out - these files MUST be committed for reproducible Docker builds

#### 3. Test Docker Builds Locally

**Why**: CI builds Docker images - catch issues locally before pushing

```bash
# Build each service (from project root)
docker build -f services/auth/Dockerfile -t test-auth:latest ./services/auth
docker build -f services/core/Dockerfile -t test-core:latest ./services/core
docker build -f services/collaboration/Dockerfile -t test-collab:latest ./services/collaboration
```

**Common failures**:
- Missing `uv.lock` → Add and commit the lockfile
- Copy errors → Check file paths in Dockerfile
- Dependency install fails → Check `pyproject.toml` syntax

---

### 🚀 Quick Pre-Push Command (Run This Before Every Push)

```bash
# One command to check everything
echo "🔍 Running pre-push CI checks..."

# 1. Check for syntax errors
echo "▶ Checking syntax errors..."
flake8 services/auth/ --exclude=".venv,.git,__pycache__,.uv,migrations,dist,build,*.egg-info" --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 services/core/ --exclude=".venv,.git,__pycache__,.uv,migrations,dist,build,*.egg-info" --count --select=E9,F63,F7,F82 --show-source --statistics
flake8 services/collaboration/ --exclude=".venv,.git,__pycache__,.uv,migrations,dist,build,*.egg-info" --count --select=E9,F63,F7,F82 --show-source --statistics

# 2. Verify uv.lock files
echo "▶ Checking uv.lock files..."
if ! git ls-files services/*/uv.lock | grep -q .; then
    echo "❌ uv.lock files not tracked! Add them:"
    echo "   git add services/auth/uv.lock services/core/uv.lock services/collaboration/uv.lock"
    exit 1
fi

# 3. Check git status
echo "▶ Checking what changed..."
git status --short

echo "✅ All pre-push checks passed! Ready to commit/push."
```

---

### 📋 CI Job Reference

When CI fails, check which job failed:

| CI Job | What It Checks | Quick Fix |
|--------|---------------|-----------|
| **Docker Build** | Can build Docker images | Ensure `uv.lock` files are committed |
| **Lint Python Code** | Flake8 syntax errors only | Run flake8 locally, fix actual syntax errors |
| **Merge Conflict** | Can merge to main | `git fetch origin main && git merge origin/main` |

---

### 🎯 Agent Workflow: Before Making Changes

1. **Read session docs** (as always)
2. **Make your changes**
3. **Run pre-push checks** (see above)
4. **Ask user to commit and push**

**NEVER skip step 3** - CI failures waste time and block PRs!

---

## 🚨 Safety Checks

### Before Running Destructive Commands

❌ **DON'T** run these without confirmation:
- `docker-compose down -v` (deletes all data)
- `docker-compose exec <service> uv run python manage.py flush`
- `DROP DATABASE` commands
- Deleting migration files

✅ **DO** ask user first if any of these seem necessary

### Before Making Database Changes

1. **Check if migrations exist** for the models you're modifying
2. **Create new migration** after model changes
3. **Test migration** in development before production
4. **Document breaking changes** in session docs

---

## 🎯 Quick Reference Commands

```bash
# Service Status
docker-compose ps                    # Show all services
docker-compose logs -f               # Stream all logs
./manage.sh                         # Interactive CLI

# Migrations
./manage.sh → Option 9              # Create migrations
./manage.sh → Option 10             # Run migrations

# Development
docker-compose up -d                # Start all services
docker-compose down                 # Stop all services
docker-compose restart <service>    # Restart specific service

# Building
docker-compose build <service>      # Rebuild service image
docker-compose up -d --build <service>  # Rebuild and restart

# Database
docker-compose exec -T <service> uv run python manage.py shell
docker-compose exec -T <service> uv run python manage.py dbshell

# Testing
curl http://localhost/api/auth/health/
curl http://localhost/api/core/health/
curl http://localhost/api/collab/health/
```

---

## 📖 Recommended Reading Order for New Agents

1. **Latest session doc** - `docs/SESSION-2026-03-26 4.md`
2. **This file** - Get familiar with command patterns
3. **Migration workflow** - `docs/MIGRATION-WORKFLOW.md`
4. **Supabase guide** - `docs/SUPABASE-MIGRATION.md` (if working on database)
5. **Previous sessions** - Check 2-3 most recent for context

---

## ⚠️ AGENT GIT POLICY (IMPORTANT!)

### ❌ NEVER Run These Commands

**Agents MUST NOT execute git operations:**
- `git add`
- `git commit`
- `git push`
- `git pull` (without explicit user request)
- `git rebase`
- `git reset`
- `git clean`

### ✅ ALWAYS Ask the User

**Instead, inform the user what to commit:**

```bash
# ❌ WRONG - Agent runs git commands
git add services/auth/uv.lock
git commit -m "Add uv.lock"
git push

# ✅ RIGHT - Agent instructs user
"Please commit the following changes:
git add services/auth/uv.lock services/core/uv.lock services/collaboration/uv.lock
git add .gitignore .github/workflows/ci.yml
git add services/auth/pyproject.toml services/core/pyproject.toml services/collaboration/pyproject.toml
git add services/  (formatted code)

Commit message:
fix(ci): resolve all CI failures - Docker builds, linting, and formatting

Then push with: git push"
```

### Why This Policy?

1. **User control** - Git operations change history, user should review first
2. **Avoid mistakes** - Agents might commit wrong files or make bad commit messages
3. **Code review** - User should see what's being committed before it's pushed
4. **Accidental pushes** - Prevents pushing incomplete or broken work

### Exception: Read-Only Git Commands

**These ARE allowed** (they don't modify state):
- `git status`
- `git diff`
- `git log`
- `git show`
- `git branch`
- `git ls-files`

---

## 💡 Agent Best Practices

### DO ✅

- **Read session docs first** - They contain crucial context
- **Use `Read` tool** - Don't guess file contents
- **Check existing patterns** - Follow established conventions
- **Test changes** - Verify services start after modifications
- **Ask for clarification** - If unsure, ask user before proceeding
- **Document what you do** - Update session docs when implementing features
- **Run pre-push CI checks** - Format with black, check with flake8, verify uv.lock
- **Ask user to commit** - After making changes, provide clear git commands for user to run

### DON'T ❌

- **Skip reading docs** - Always check session docs first
- **Make assumptions** - Verify file contents before editing
- **Run destructive commands** - Ask before deleting data/volumes
- **Change working patterns** - Follow established conventions
- **Ignore error messages** - Read logs and tracebacks carefully
- **Skip testing** - Always verify changes work
- **Run git commands** - NEVER use `git add`, `git commit`, `git push`, `git pull`

---

## 🆘 Getting Unstuck

### If You're Confused

1. **Read the session docs** - Answer is likely there
2. **Check service logs** - `docker-compose logs -f <service>`
3. **Verify service is running** - `docker-compose ps`
4. **Review similar code** - Find patterns in existing codebase
5. **Ask user for clarification** - Better to ask than break something

### Common Error Messages

| Error | Meaning | Fix |
|-------|---------|-----|
| "Module not found" | Missing dependency | Check `pyproject.toml`, run `uv sync` |
| "Connection refused" | Service not running | `docker-compose ps`, start service |
| "Authentication failed" | Wrong/missing SECRET_KEY | Check `.env` file |
| "Table doesn't exist" | Migrations not run | Run migrations |
| "Port already in use" | Old container running | `docker-compose restart` |

---

**Remember**: This codebase has a history. The session docs are your friend. When in doubt, read the docs first! 📚
