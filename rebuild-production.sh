#!/bin/bash
set -e

echo "🔄 Rebuilding Plytix-Webflow Integration (Production Mode)..."

# Check if .env file exists
if [ ! -f .env.production ] && [ ! -f .env ]; then
    echo "❌ Error: Neither .env.production nor .env file found!"
    echo "Please create one from .env.example and configure your credentials."
    exit 1
fi

# Use .env.production if it exists, otherwise fallback to .env
ENV_FILE=".env"
if [ -f .env.production ]; then
    ENV_FILE=".env.production"
    echo "📝 Using production environment file: .env.production"
else
    echo "⚠️  Warning: .env.production not found, using .env"
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Error: Docker is not running. Please start Docker first."
    exit 1
fi

# Create required directories
echo "📂 Creating required directories..."
mkdir -p logs data

# Check if field_mappings.json exists
if [ ! -f field_mappings.json ]; then
    echo "⚠️  Warning: field_mappings.json not found. Creating empty configuration..."
    echo '{}' > field_mappings.json
fi

# Stop and remove everything
echo "🛑 Stopping and removing containers..."
docker-compose -f docker-compose.prod.yml down --volumes --remove-orphans

# Remove existing images (optional, but ensures clean rebuild)
echo "🗑️  Removing existing application images..."
docker images | grep -E "plytix|webflow" | awk '{print $3}' | xargs -r docker rmi -f || true

# Clean build cache
echo "🧹 Cleaning Docker cache..."
docker system prune -f

# Pull latest base images
echo "📥 Pulling latest base images..."
docker-compose -f docker-compose.prod.yml pull postgres redis

# Rebuild everything
echo "🏗️ Building containers from scratch..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Start core services first (database and redis)
echo "🚀 Starting core services..."
docker-compose -f docker-compose.prod.yml up -d postgres redis

# Wait for core services to be ready
echo "⏳ Waiting for core services to be ready..."
sleep 20

# Start application services
echo "🚀 Starting application services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for application services to start
echo "⏳ Waiting for application services to start..."
sleep 30

# Run migrations
echo "🗄️ Running database migrations..."
docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head || {
    echo "⚠️  Migration failed, retrying in 10 seconds..."
    sleep 10
    docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head
}

# Health check
echo "🏥 Performing health check..."
sleep 5
HEALTH_CHECK=$(docker-compose -f docker-compose.prod.yml exec -T api curl -s http://localhost:8000/health/ || echo "FAILED")
if [[ "$HEALTH_CHECK" == *"FAILED"* ]]; then
    echo "⚠️  Health check failed, but services may still be starting..."
else
    echo "✅ Health check passed!"
fi

# Show status
echo "📊 Container status:"
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "✅ Production environment rebuilt successfully!"
echo ""
echo "🌐 Services available at:"
echo "  - API: http://localhost:${API_PORT:-8000}"
echo "  - API Documentation: http://localhost:${API_PORT:-8000}/docs"
echo "  - Health Check: http://localhost:${API_PORT:-8000}/health/"
echo "  - Flower (Celery Monitor): http://localhost:${FLOWER_PORT:-5555}"
if [ -f docker-compose.prod.yml ] && grep -q "nginx:" docker-compose.prod.yml; then
    echo "  - Nginx Proxy: http://localhost:80"
fi

echo ""
echo "📝 Useful commands:"
echo "  - View API logs: docker-compose -f docker-compose.prod.yml logs -f api"
echo "  - View worker logs: docker-compose -f docker-compose.prod.yml logs -f celery-worker"
echo "  - View all logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "  - Stop services: docker-compose -f docker-compose.prod.yml down"
echo "  - Restart services: docker-compose -f docker-compose.prod.yml restart"

echo ""
echo "🔍 To monitor sync tasks, visit Flower at http://localhost:${FLOWER_PORT:-5555}"
echo "   Default credentials: admin/admin (configurable via FLOWER_USER/FLOWER_PASS)"

echo ""
echo "⚠️  Note: If services are not responding immediately, wait a few minutes for full startup."
