#!/bin/bash
# Stop all Plytix-Webflow integration services

set -e

echo "🛑 Stopping Plytix-Webflow Integration Services"
echo "============================================="

# Function to stop service with status check
stop_service() {
    local service=$1
    echo "🔧 Stopping $service..."
    
    if systemctl --user is-active --quiet $service; then
        systemctl --user stop $service
        sleep 2
        
        if systemctl --user is-active --quiet $service; then
            echo "❌ Failed to stop $service"
            return 1
        else
            echo "✅ $service stopped successfully"
        fi
    else
        echo "ℹ️  $service is not running"
    fi
}

# Stop core services
echo "🔧 Stopping core services..."

stop_service "plytix-scheduler"
stop_service "plytix-api"

# Stop optional Celery services if they exist
if systemctl --user list-unit-files plytix-worker.service &>/dev/null; then
    echo ""
    echo "🔧 Stopping optional Celery services..."
    stop_service "plytix-beat"
    stop_service "plytix-worker"
fi

# Stop Docker services (optional)
if [ -f docker-compose.yml ]; then
    echo ""
    echo "🐳 Stopping Docker services..."
    
    if [ "$1" = "--with-docker" ]; then
        docker-compose down
        echo "✅ Docker services stopped"
    else
        echo "ℹ️  Use --with-docker flag to also stop Docker services"
    fi
fi

echo ""
echo "📊 Final Service Status:"
echo "======================="

# Check final status
if systemctl --user is-active --quiet plytix-api; then
    echo "⚠️  plytix-api is still running"
else
    echo "✅ plytix-api is stopped"
fi

if systemctl --user is-active --quiet plytix-scheduler; then
    echo "⚠️  plytix-scheduler is still running"
else
    echo "✅ plytix-scheduler is stopped"
fi

if systemctl --user list-unit-files plytix-worker.service &>/dev/null; then
    if systemctl --user is-active --quiet plytix-worker; then
        echo "⚠️  plytix-worker is still running"
    else
        echo "✅ plytix-worker is stopped"
    fi
    
    if systemctl --user is-active --quiet plytix-beat; then
        echo "⚠️  plytix-beat is still running"
    else
        echo "✅ plytix-beat is stopped"
    fi
fi

echo ""
echo "🎉 All services stopped successfully!"

# Show any remaining processes
echo ""
echo "🔍 Checking for remaining processes..."
if pgrep -f "plytix" > /dev/null; then
    echo "⚠️  Some Plytix processes are still running:"
    pgrep -f "plytix" -l || true
    echo ""
    echo "💡 To force kill all processes:"
    echo "   pkill -f plytix"
else
    echo "✅ No Plytix processes found"
fi