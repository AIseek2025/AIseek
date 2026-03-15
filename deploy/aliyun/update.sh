#!/bin/bash
set -e

echo "Starting deployment update..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 .env.prod 是否存在且包含必要变量
if [ ! -f .env.prod ]; then
  echo "ERROR: .env.prod not found. Copy .env.prod.example to .env.prod and configure REDIS_PASSWORD, WORKER_SECRET, etc."
  exit 1
fi
if ! grep -q '^REDIS_PASSWORD=.\+' .env.prod 2>/dev/null; then
  echo "ERROR: REDIS_PASSWORD must be set in .env.prod"
  exit 1
fi

# 1. Pull latest code from GitHub
echo "Pulling latest code from GitHub..."
cd ../..
git pull origin main
cd "$SCRIPT_DIR"

# 2. Rebuild and restart services（使用 .env.prod 加载环境变量）
echo "Rebuilding and restarting services..."
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build --remove-orphans

# 3. Run database migrations explicitly
echo "Running database migrations..."
docker compose --env-file .env.prod -f docker-compose.prod.yml exec backend alembic upgrade head

# 4. Clean up unused images
echo "Cleaning up old images..."
docker image prune -f

echo "Deployment completed successfully!"
