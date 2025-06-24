#!/bin/bash

# Start script for development environment

echo "Starting Plytix-Webflow Integration..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env file with your actual credentials before running again."
    exit 1
fi

# Start infrastructure services
echo "Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Wait for services to be ready
echo "Waiting for services to be ready..."
sleep 10

# Run database migrations
echo "Running database migrations..."
alembic upgrade head

# Start the application
echo "Starting application services..."
docker-compose up -d

echo "Application started successfully!"
echo "API available at: http://localhost:8000"
echo "Flower (Celery monitoring) available at: http://localhost:5555"
echo "API documentation available at: http://localhost:8000/docs"