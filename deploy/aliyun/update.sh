#!/bin/bash
set -e

echo "Starting deployment update..."

# 1. Pull latest code from GitHub
echo "Pulling latest code from GitHub..."
git pull origin main

# 2. Rebuild and restart services
# We use --build to ensure code changes in backend/worker (which are copied in Dockerfile) are applied
echo "Rebuilding and restarting services..."
docker compose -f docker-compose.prod.yml up -d --build --remove-orphans

# 3. Run database migrations explicitly
echo "Running database migrations..."
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 4. Clean up unused images
echo "Cleaning up old images..."
docker image prune -f

echo "Deployment completed successfully!"
