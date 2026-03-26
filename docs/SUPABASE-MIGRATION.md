# Supabase Migration Guide

## Overview

This guide covers migrating from PostgreSQL (Docker/Render) to **Supabase** for the Spotify ISD backend project.

**Good News:** Supabase is built on PostgreSQL, so your existing **Django migrations will work without modification**!

---

## 🎯 What Changes vs What Stays The Same

### ✅ What Stays The Same (No Changes Needed)

- **Django ORM**: All models work as-is
- **Migrations**: All existing migration files work without changes
- **Queries**: Django ORM queries unchanged
- **Business Logic**: Application code unaffected
- **Entry Point Scripts**: Minimal changes (connection check only)

### 🔄 What Changes

| Component | Current (PostgreSQL) | Supabase |
|-----------|---------------------|----------|
| **Database Host** | `db` (Docker) or Render URL | `your-project.supabase.co` |
| **Connection String** | `postgresql://user:pass@host:5432/db` | `postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres` |
| **Authentication** | Django auth (local) | Optional: Supabase Auth |
| **Realtime** | Not available | Optional: Supabase Realtime |
| **Row Level Security** | Django model permissions | Optional: Supabase RLS |
| **Database Client** | `psql` | Supabase Dashboard or `psql` |
| **Environment Variable** | `DB_HOST`, `DB_PORT`, etc. | `DATABASE_URL` (single variable) |

---

## 📋 Migration Strategy

### Phase 1: Set Up Supabase Project

```bash
# 1. Create Supabase project at https://supabase.com
# 2. Note down:
#    - Project URL: https://your-project.supabase.co
#    - anon key: eyJhbGc...
#    - service_role key: eyJhbGc...
#    - Database password: (from Settings → Database)
```

### Phase 2: Update Environment Variables

**Development (.env files):**
```bash
# Old way (Docker PostgreSQL)
DB_HOST=db
DB_PORT=5432
DB_NAME=spotifydb
DB_USER=spotifyuser
DB_PASSWORD=spotifypass

# New way (Supabase)
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGc...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGc...
```

**Production (.env files):**
```bash
# Use Supabase connection pooler for better performance
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:6543/postgres
```

### Phase 3: Update Django Settings

**services/auth/core/settings.py:**
```python
# Old way
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': os.environ.get('DB_HOST', 'db'),
        'PORT': os.environ.get('DB_PORT', '5432'),
        'NAME': os.environ.get('DB_NAME', 'spotifydb'),
        'USER': os.environ.get('DB_USER', 'spotifyuser'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'spotifypass'),
    }
}

# New way (supports both DATABASE_URL and individual vars)
import dj_database_url

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

**Install dj-database-url:**
```bash
# Add to all pyproject.toml files
uv add dj-database-url
```

### Phase 4: Update Entrypoint Scripts

**Current entrypoint database check:**
```bash
until PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -U "$DB_USER" -d "$DB_NAME" -c '\q' 2>/dev/null; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 1
done
```

**Updated for Supabase (using python instead):**
```bash
# Wait for database using Django's connection
echo "Waiting for database to be ready..."
until uv run python -c "from django.db import connection; connection.ensure_connection()"; do
    echo "Database is unavailable - sleeping"
    sleep 1
done
echo "Database is up!"
```

**Why this change?**
- No need for `psql` client in Docker image
- Works with any database backend (PostgreSQL, Supabase, etc.)
- Simpler and more portable

---

## 🚀 Migration Steps

### Option A: Manual Migration (Recommended for First Time)

```bash
# 1. Create Supabase project
# Get connection details from Supabase Dashboard → Settings → Database

# 2. Update environment variables
cp services/auth/.env.example services/auth/.env
# Edit with Supabase DATABASE_URL

# 3. Run migrations against Supabase
docker-compose run --rm auth uv run python manage.py migrate
docker-compose run --rm core uv run python manage.py migrate
docker-compose run --rm collaboration uv run python manage.py migrate

# 4. Verify in Supabase Dashboard
# Tables → Check all tables created
```

### Option B: Automated via Docker Compose

**Update docker-compose.yml:**
```yaml
services:
  auth:
    environment:
      # Use Supabase DATABASE_URL instead of individual vars
      - DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres

  # Remove the db service (no longer needed)
  # db:
  #   image: postgres:15
  #   ...
```

**Run migrations:**
```bash
docker-compose up auth core collaboration
# Migrations run automatically via entrypoint!
```

---

## 🔐 Authentication Integration (Optional)

Supabase provides its own authentication system. You have **two options**:

### Option 1: Keep Django Auth (Recommended - Minimal Changes)

**Why:**
- No application code changes
- Migrations unaffected
- Full control over user model
- Already working

**How:**
- Continue using Django's built-in auth
- Keep current auth service as-is
- Supabase only used for database

### Option 2: Migrate to Supabase Auth (Advanced)

**Benefits:**
- Managed authentication
- Social logins (Google, GitHub, etc.)
- Row Level Security (RLS)
- Built-in user management

**Changes Required:**
```python
# Install Supabase Python client
uv add supabase

# Update auth service
from supabase import create_client, Client

supabase: Client = create_client(
    os.environ.get('SUPABASE_URL'),
    os.environ.get('SUPABASE_ANON_KEY')
)

# Replace Django auth with Supabase auth
# (Significant refactoring required)
```

**Recommendation**: Start with Option 1, migrate to Option 2 later if needed.

---

## 📊 Realtime Features (Optional)

Supabase Realtime provides PostgreSQL change notifications.

**Use Cases:**
- Live collaboration updates
- Real-time playlist changes
- Track progress updates

**Integration:**
```python
# Install Realtime client
uv add realtime-python

# Connect to Realtime
from realtime import Socket

socket = Socket(os.environ.get('SUPABASE_URL'))
socket.connect()

# Subscribe to table changes
channel = socket.set_channel('tracks')
channel.on('postgres_changes', callback=your_handler)
channel.subscribe()
```

**Note**: Not required for MVP - can add later.

---

## 🔧 Row Level Security (Optional)

Supabase RLS provides database-level access control.

**Current:** Django model permissions
**Supabase:** RLS policies at database level

**Example RLS Policy:**
```sql
-- Enable RLS
ALTER TABLE tracks ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own tracks
CREATE POLICY "Users can view own tracks"
ON tracks
FOR SELECT
USING (user_id = auth.uid());

-- Policy: Users can only update their own tracks
CREATE POLICY "Users can update own tracks"
ON tracks
FOR UPDATE
USING (user_id = auth.uid());
```

**Recommendation**: Keep Django permissions for now, RLS is optional enhancement.

---

## ✅ Migration Checklist

### Pre-Migration
- [ ] Create Supabase project
- [ ] Get connection credentials (DATABASE_URL)
- [ ] Backup existing PostgreSQL data (if any)
- [ ] Test DATABASE_URL connection locally

### Migration
- [ ] Update `.env` files with DATABASE_URL
- [ ] Install `dj-database-url` in all services
- [ ] Update Django settings to use DATABASE_URL
- [ ] Update entrypoint scripts
- [ ] Run migrations against Supabase
- [ ] Verify tables in Supabase Dashboard

### Post-Migration
- [ ] Test all API endpoints
- [ ] Verify authentication works
- [ ] Check database connections stable
- [ ] Update documentation
- [ ] Remove old PostgreSQL container (if using Docker)

---

## 🎯 Dev/Staging/Prod Strategy

### Development: Keep Docker PostgreSQL
```bash
# Use Docker for local development
docker-compose up  # Uses local PostgreSQL
```

### Staging: Supabase (Free Tier)
```bash
# Test Supabase integration
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
docker-compose up  # Connects to Supabase
```

### Production: Supabase (Pro Tier)
```bash
# Use Supabase for production
# Better performance, backups, scaling
```

---

## 📝 Minimal Change Path (Recommended)

**Step 1: Update Django Settings**
```python
# Add to all services' settings.py
import dj_database_url
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}
```

**Step 2: Add Environment Variable**
```bash
# In .env files
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres
```

**Step 3: Update Entrypoint**
```bash
# Change from psql check to Django check
until uv run python -c "from django.db import connection; connection.ensure_connection()"; do
    sleep 1
done
```

**Step 4: Run Migrations**
```bash
docker-compose run --rm auth uv run python manage.py migrate
```

**That's it!** Everything else works as before.

---

## 🆘 Troubleshooting

### Connection Issues
```bash
# Test DATABASE_URL
psql $DATABASE_URL

# Check Django can connect
uv run python manage.py check --database default
```

### Migration Conflicts
```bash
# If migrations fail, show current status
uv run python manage.py showmigrations

# Fake migrations if needed
uv run python manage.py migrate --fake
```

### Performance Issues
```bash
# Use Supabase connection pooler (port 6543)
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:6543/postgres
```

---

## 📚 Resources

- [Supabase Django Guide](https://supabase.com/docs/guides/with-django)
- [Supabase Migration Guide](https://supabase.com/docs/guides/migrations/pg-django-migration)
- [dj-database-url Documentation](https://github.com/jazzband/dj-database-url)

---

**Migration Complexity**: ⭐⭐☆☆☆ (Low)
**Breaking Changes**: None (migrations are compatible)
**Rollback**: Easy (just switch DATABASE_URL back)
