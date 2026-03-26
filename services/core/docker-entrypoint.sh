#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}→ Core Service Entrypoint${NC}"
echo "Waiting for database to be ready..."

# Wait for database using Django's connection check
# This works with both Docker PostgreSQL and Supabase (DATABASE_URL)
until uv run python -c "from django.db import connection; connection.ensure_connection()" 2>/dev/null; do
  echo -e "${YELLOW}Database is unavailable - sleeping${NC}"
  sleep 1
done

echo -e "${GREEN}✓ Database is up!${NC}"

# Check if we should run migrations (default: true)
if [ "$RUN_MIGRATIONS" != "false" ]; then
    echo -e "${GREEN}→ Running database migrations...${NC}"
    uv run python manage.py migrate --noinput

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Migrations completed successfully${NC}"
    else
        echo -e "${RED}✗ Migrations failed!${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⊗ Migrations skipped (RUN_MIGRATIONS=false)${NC}"
fi

# Execute the main command
echo -e "${GREEN}→ Starting Core service...${NC}"
exec "$@"
