#!/bin/bash

# Database migration script

echo "Running database migrations..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL environment variable is not set"
    echo "Please set it or ensure .env file is properly configured"
    exit 1
fi

# Run migrations
alembic upgrade head

echo "Migrations completed successfully!"