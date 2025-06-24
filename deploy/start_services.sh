#!/bin/bash
# Start all Plytix-Webflow integration services

set -e

echo "🚀 Starting Plytix-Webflow Integration Services"
echo "=============================================="

# Function to check service status
check_service() {
    local service=$1
    if systemctl --user is-active --quiet $service; then
        echo "✅ $service is running"
        return 0
    else
        echo "❌ $service is not running"
        return 1
    fi
}

# Function to start service with status check
start_service() {
    local service=$1
    echo "🔧 Starting $service..."
    
    if systemctl --user is-active --quiet $service; then
        echo "ℹ️  $service is already running"
    else
        systemctl --user start $service
        sleep 2
        
        if check_service $service; then
            echo "✅ $service started successfully"
        else
            echo "❌ Failed to start $service"
            echo "📋 Checking logs..."
            journalctl --user -u $service --no-pager -n 10
            return 1
        fi
    fi
}

# Start Docker services first (if using Docker for Redis/PostgreSQL)
if [ -f docker-compose.yml ]; then
    echo "🐳 Starting Docker services..."
    docker-compose up -d redis postgres
    sleep 5
    echo "✅ Docker services started"
fi

# Start core services
echo ""
echo "🔧 Starting core services..."

# Start API server
start_service "plytix-api"

# Start scheduler
start_service "plytix-scheduler"

# Optional: Start Celery services if they exist
if systemctl --user list-unit-files plytix-worker.service &>/dev/null; then
    echo ""
    echo "🔧 Starting optional Celery services..."
    
    if [ -f docker-compose.yml ] && docker-compose ps redis | grep -q "Up"; then
        start_service "plytix-worker"
        start_service "plytix-beat"
    else
        echo "⚠️  Redis not available, skipping Celery services"
    fi
fi

echo ""
echo "📊 Service Status Summary:"
echo "========================="

check_service "plytix-api" || true
check_service "plytix-scheduler" || true

if systemctl --user list-unit-files plytix-worker.service &>/dev/null; then
    check_service "plytix-worker" || true
    check_service "plytix-beat" || true
fi

echo ""
echo "🌐 Service URLs:"
echo "==============="
echo "API Server: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Health Check: http://localhost:8000/health/"

if systemctl --user is-active --quiet plytix-worker; then
    echo "Flower (Celery Monitor): http://localhost:5555"
fi

echo ""
echo "📋 Useful Commands:"
echo "=================="
echo "Check status: ./plytix-cli status"
echo "View logs: journalctl --user -u plytix-scheduler -f"
echo "Stop services: ./deploy/stop_services.sh"
echo "Monitor system: plytix-monitor"

echo ""
echo "🎉 All services started successfully!"

# Test basic connectivity
echo ""
echo "🧪 Testing connectivity..."

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ | grep -q "200"; then
    echo "✅ API server is responding"
else
    echo "❌ API server is not responding"
    echo "📋 Checking API logs..."
    journalctl --user -u plytix-api --no-pager -n 5
fi