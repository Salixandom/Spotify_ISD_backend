#!/bin/bash

# Generate production secrets for all services
# Usage: ./scripts/generate-secrets.sh

set -e

echo "🔐 Generating production secrets..."

# Generate secrets
SECRET_KEY=$(openssl rand -hex 32)
DB_PASSWORD=$(openssl rand -hex 16)
JWT_SECRET=$(openssl rand -hex 32)

echo "✅ Secrets generated!"
echo ""
echo "⚠️  Save these values securely. You'll need them for production deployment."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "DJANGO_SECRET_KEY=$SECRET_KEY"
echo "DB_PASSWORD=$DB_PASSWORD"
echo "JWT_SECRET=$JWT_SECRET"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create production env files if they don't exist
create_env_file() {
  local service=$1
  local env_file="services/${service}/.env"

  if [ ! -f "$env_file" ]; then
    echo "📝 Creating $env_file..."
    cat > "$env_file" << EOF
# Production environment variables
# Generated: $(date)

SECRET_KEY=$SECRET_KEY
DEBUG=False
ALLOWED_HOSTS=your-domain.com,.onrender.com,localhost

# Database
DB_HOST=your-db-host
DB_PORT=5432
DB_NAME=spotifydb
DB_USER=spotifyuser
DB_PASSWORD=$DB_PASSWORD

# CORS
CORS_ALLOWED_ORIGINS=https://your-frontend.com

# JWT (Auth service only)
EOF

    if [ "$service" == "auth" ]; then
      cat >> "$env_file" << EOF
JWT_ACCESS_TOKEN_LIFETIME=60
JWT_REFRESH_TOKEN_LIFETIME=1440
EOF
    fi

    echo "✅ Created $env_file"
  else
    echo "⏭  Skipping $env_file (already exists)"
  fi
}

# Create env files for all services
for service in auth playlist track search collaboration; do
  create_env_file "$service"
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next Steps:"
echo ""
echo "1. Update DB_HOST in each .env file with your production database host"
echo "2. Update ALLOWED_HOSTS with your actual domain"
echo "3. Update CORS_ALLOWED_ORIGINS with your frontend URL"
echo "4. For Render.com: Update render.yaml with your service names"
echo "5. Commit .env files (if using secret management) or set manually in deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
