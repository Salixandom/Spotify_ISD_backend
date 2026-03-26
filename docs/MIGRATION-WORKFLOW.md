# Migration Workflow Guide

## Overview

This project now uses **automatic migrations via entrypoint scripts** for development convenience, with manual control for production safety.

---

## Developer Workflow

### Making Database Changes

**1. Modify your models**
```python
# services/core/trackapp/models.py
class Track(models.Model):
    # ... add new field
    is_featured = models.BooleanField(default=False)
```

**2. Create migration files**
```bash
# Option A: Use manage.sh (RECOMMENDED)
./manage.sh
# Select: 9) Make migrations (create migration files)
# Select the service (e.g., core)

# Option B: Direct command
docker-compose exec core uv run python manage.py makemigrations
```

**3. Review the generated migration**
```bash
# Check the created migration file
cat services/core/trackapp/migrations/000X_add_is_featured.py
```

**4. Commit and push**
```bash
git add services/core/trackapp/migrations/000X_add_is_featured.py
git commit -m "Add is_featured field to Track model"
git push
```

**5. Migrations run automatically**
- **Development**: Migrations apply automatically when containers start
- **Production**: Migrations need to be run manually (see below)

---

## Automatic Migration Behavior

### Development (docker-compose.yml)
```yaml
environment:
  - RUN_MIGRATIONS=true  # Default
```

When you start services:
```bash
docker-compose up -d
```

Each service's entrypoint script:
1. Waits for PostgreSQL to be ready
2. Runs migrations automatically
3. Starts the application

**Benefits:**
- No need to remember to run migrations
- Database is always up-to-date
- Faster onboarding for new developers

### Production (docker-compose.prod.yml)
```yaml
environment:
  - RUN_MIGRATIONS=false  # Disabled for safety
```

**Why disabled in production?**
- Run migrations at a controlled time
- Review migrations before applying
- Rollback capability if something goes wrong
- Zero-downtime deployment strategy

---

## Production Deployment

### Option 1: Via manage.sh
```bash
./manage.sh
# Select: 10) Run migrations (apply to database)
```

### Option 2: Direct commands
```bash
# After deploying new code
docker-compose exec auth uv run python manage.py migrate
docker-compose exec core uv run python manage.py migrate
docker-compose exec collaboration uv run python manage.py migrate
```

### Option 3: CI/CD Integration
```yaml
# .github/workflows/deploy.yml
- name: Run migrations
  run: |
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T auth uv run python manage.py migrate
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T core uv run python manage.py migrate
    docker-compose -f docker-compose.yml -f docker-compose.prod.yml exec -T collaboration uv run python manage.py migrate
```

---

## Troubleshooting

### Migrations fail to apply
```bash
# Check what migrations exist
docker-compose exec core uv run python manage.py showmigrations

# Check if there are conflicts
docker-compose exec core uv run python manage.py makemigrations --merge

# Fake a migration if needed (e.g., for initial data)
docker-compose exec core uv run python manage.py migrate --fake
```

### Need to rollback
```bash
# List migrations to find the target
docker-compose exec core uv run python manage.py showmigrations

# Rollback to specific migration
docker-compose exec core uv run python manage.py migrate app_name migration_number
```

### Database out of sync
```bash
# Reset database (WARNING: deletes all data)
./manage.sh
# Select: 16) Database operations
# Select: 4) Reset database
# Then run migrations
```

---

## Best Practices

1. **Always review migrations** before committing
2. **Make migrations atomic** - one change per migration
3. **Add descriptive names** to migrations: `makemigrations --name add_is_featured_field`
4. **Test migrations** in development before production
5. **Never modify existing migrations** - always create new ones
6. **Keep migrations in git** - they're part of your codebase

---

## Environment Variable Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `RUN_MIGRATIONS` | `true` (dev) / `false` (prod) | Enable/disable automatic migrations on startup |
| `DB_HOST` | `db` | Database hostname |
| `DB_PORT` | `5432` | Database port |
| `DB_NAME` | `spotifydb` | Database name |
| `DB_USER` | `spotifyuser` | Database user |
| `DB_PASSWORD` | `spotifypass` | Database password |

---

## Quick Reference

```bash
# Development - migrations are automatic
docker-compose up -d

# Create new migrations
./manage.sh → Option 9

# Run migrations manually (if needed)
./manage.sh → Option 10

# Production - run migrations manually
./manage.sh → Option 10

# Check migration status
docker-compose exec <service> uv run python manage.py showmigrations
```
