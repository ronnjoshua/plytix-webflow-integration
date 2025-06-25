#!/bin/bash
set -e

echo "🚀 Starting Plytix-Webflow Integration (Production Mode)..."

# Check if .env file exists (fallback to .env if .env.production doesn't exist)
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

# Check if required directories exist
echo "📂 Creating required directories..."
mkdir -p logs data

# Check if field_mappings.json exists
if [ ! -f field_mappings.json ]; then
    echo "⚠️  Warning: field_mappings.json not found. Creating empty configuration..."
    echo '{}' > field_mappings.json
fi

# Stop any existing containers
echo "🛑 Stopping any existing containers..."
docker-compose -f docker-compose.prod.yml down --remove-orphans || true

# Pull latest images
echo "📥 Pulling latest base images..."
docker-compose -f docker-compose.prod.yml pull postgres redis

# Start production environment
echo "🚀 Starting production services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for core services to be ready
echo "⏳ Waiting for core services to start..."
sleep 15

# Check if database needs migration
echo "🗄️  Running database migrations..."
docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head || {
    echo "⚠️  Migration failed, database may not be ready yet. Retrying in 10 seconds..."
    sleep 10
    docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head
}

# Show container status
echo "📊 Container status:"
docker-compose -f docker-compose.prod.yml ps

# Show service URLs
echo ""
echo "✅ Production environment started successfully!"
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
echo "  - View logs: docker-compose -f docker-compose.prod.yml logs -f"
echo "  - Stop services: docker-compose -f docker-compose.prod.yml down"
echo "  - Restart services: docker-compose -f docker-compose.prod.yml restart"
echo ""
echo "🔍 To monitor sync tasks, visit Flower at http://localhost:${FLOWER_PORT:-5555}"
echo "   Default credentials: admin/admin (configurable via FLOWER_USER/FLOWER_PASS)"