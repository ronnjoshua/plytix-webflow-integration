#\!/bin/bash
set -e

echo "🔄 Rebuilding Docker Production Environment..."

# Stop and remove everything
echo "📦 Stopping and removing containers..."
docker-compose -f docker-compose.prod.yml down --volumes --remove-orphans

# Clean build cache
echo "🧹 Cleaning Docker cache..."
docker system prune -f

# Rebuild everything
echo "🏗️ Building containers..."
docker-compose -f docker-compose.prod.yml build --no-cache

# Start services
echo "🚀 Starting services..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 30

# Run migrations
echo "🗄️ Running database migrations..."
docker-compose -f docker-compose.prod.yml exec -T api alembic upgrade head

# Show status
echo "✅ Production environment rebuilt successfully\!"
echo "📊 Container status:"
docker-compose -f docker-compose.prod.yml ps

echo "🌐 Services available at:"
echo "  - API: http://localhost:8000"
echo "  - Flower: http://localhost:5555"
echo "  - Health: http://localhost:8000/health/"

echo "📝 To view logs:"
echo "  docker-compose -f docker-compose.prod.yml logs -f api"
echo "  docker-compose -f docker-compose.prod.yml logs -f celery-worker"
