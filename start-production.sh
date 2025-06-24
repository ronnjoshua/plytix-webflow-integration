#!/bin/bash

# Load production environment variables and start Docker Compose
export $(grep -v '^#' .env.production | grep -v '^$' | sed 's/\*/#/g' | xargs)

# Start production environment
echo "anil" | sudo -E -S docker-compose -f docker-compose.prod.yml up -d

echo "Production environment started!"
echo "API: http://localhost:8000"
echo "Flower: http://localhost:5555"
echo "Health: http://localhost:8000/health/"