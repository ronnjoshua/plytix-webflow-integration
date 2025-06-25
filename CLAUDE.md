# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a complete Python FastAPI application that synchronizes products and their variants from Plytix PIM to Webflow E-commerce in one direction (Plytix → Webflow). The system handles complex product variants, maintains data integrity, runs on a scheduled basis, and includes comprehensive field mapping capabilities with monitoring and management features.

## Development Commands

### Setup and Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment configuration
cp .env.example .env
# Edit .env with your actual API credentials

# Start development environment with Docker
chmod +x scripts/start.sh
./scripts/start.sh

# Manual setup (alternative)
docker-compose up -d postgres redis
alembic upgrade head
uvicorn app.main:app --reload
```

### Database Operations
```bash
# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Rollback migration
alembic downgrade -1

# Reset database (development only)
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head
```

### Background Tasks
```bash
# Start Celery worker
celery -A app.tasks.celery_app worker --loglevel=info

# Start Celery beat scheduler
celery -A app.tasks.celery_app beat --loglevel=info

# Monitor tasks with Flower (with authentication)
celery -A app.tasks.celery_app flower --port=5555
# Default credentials: admin/admin (configurable via FLOWER_USER/FLOWER_PASS)
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_filename.py -v
```

### Docker Operations
```bash
# Development environment
docker-compose up -d

# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# Local environment (alternative)
docker-compose -f docker-compose.local.yml up -d

# View logs
docker-compose logs -f api
docker-compose logs -f celery-worker
docker-compose logs -f celery-beat

# Rebuild containers
docker-compose build --no-cache

# Optional scheduler service (alternative to Celery Beat)
docker-compose --profile scheduler up -d
```

## Architecture Overview

### Core Components

1. **FastAPI Application** (`app/main.py`): Main web server with async endpoints and CORS middleware
2. **Database Models** (`app/models/`): SQLAlchemy models for database, Plytix, and Webflow data structures
3. **API Clients** (`app/clients/`): Async HTTP clients for Plytix and Webflow APIs with rate limiting
4. **Services** (`app/services/`): Business logic for sync, variants, field mapping, and transformations
5. **Celery Tasks** (`app/tasks/`): Background job processing and scheduling
6. **API Routes** (`app/api/routes/`): REST endpoints for management, monitoring, and control
7. **Utilities** (`app/utils/`): Helper functions for assets, rate limiting, and field processing

### Data Flow

1. Celery Beat triggers scheduled sync tasks
2. Plytix client fetches products with variants (with authentication)
3. Variant service processes complex variant matrices
4. Field mapping service applies custom field transformations
5. Transform service converts Plytix format to Webflow format
6. Webflow client creates/updates products with rate limiting
7. Database tracks all operations, errors, and statistics

### Key Features

- **Async Architecture**: Built with FastAPI and asyncio for high performance
- **Rate Limiting**: Intelligent rate limiting for both Plytix and Webflow APIs
- **Variant Processing**: Handles complex product variant matrices intelligently
- **Field Mapping**: Comprehensive custom field mapping with auto-discovery
- **Error Handling**: Comprehensive error tracking with retry logic and detailed reporting
- **Monitoring**: Built-in health checks, performance metrics, and activity tracking
- **Scheduling**: Configurable sync schedules via Celery Beat
- **Authentication**: Secure API authentication for all external services
- **Configuration Management**: Import/export field mappings and configurations
- **Collection Management**: Dynamic collection mapping and statistics
- **Update-Only Mode**: Configurable to only update existing products, not create new ones

## Environment Configuration

### Required Environment Variables

See `.env.example` for complete configuration. Key variables:

```env
# API Credentials (Required)
PLYTIX_API_KEY=your_plytix_api_key_here
PLYTIX_API_PASSWORD=your_plytix_api_password_here
WEBFLOW_TOKEN=your_webflow_api_token_here
WEBFLOW_SITE_ID=your_webflow_site_id_here
WEBFLOW_COLLECTION_ID=your_webflow_collection_id_here

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/integration_db

# Redis/Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Application Settings
DEBUG=false
LOG_LEVEL=INFO
ENVIRONMENT=production

# Sync Configuration
ENABLE_PRODUCT_CREATION=false
UPDATE_ONLY_MODE=true
SYNC_FREQUENCY_MINUTES=30
MAX_PRODUCTS_PER_SYNC=100
```

## API Endpoints

### Health & Monitoring
- `GET /health/` - Basic health check
- `GET /health/detailed` - Detailed health check with external API verification
- `GET /monitoring/stats` - Synchronization statistics (last N days)
- `GET /monitoring/recent-activity` - Recent sync activity timeline
- `GET /monitoring/health-metrics` - System health metrics

### Synchronization Control
- `POST /sync/trigger` - Manually trigger full product synchronization
- `POST /sync/trigger/product/{product_id}` - Trigger sync for single product
- `GET /sync/status/{task_id}` - Check status of running sync task
- `GET /sync/history` - Recent synchronization history
- `GET /sync/errors/{sync_id}` - Get errors for specific sync
- `GET /sync/auth-check` - Verify authentication for all APIs

### Field Mapping Management
- `GET /field-mappings/current` - Get current field mappings configuration
- `POST /field-mappings/update` - Update field mappings configuration
- `POST /field-mappings/discover-images` - Auto-discover image fields from sample data
- `POST /field-mappings/validate` - Validate current field mappings
- `GET /field-mappings/field-types` - Get available field types
- `POST /field-mappings/test-transform` - Test field transformation with sample data
- `POST /field-mappings/import-config` - Import field mappings from JSON file
- `GET /field-mappings/export-config` - Export current field mappings
- `GET /field-mappings/sample-mapping` - Get sample field mapping configuration
- `POST /field-mappings/auto-map` - Auto-generate mappings based on field similarity

### Collection Management
- `GET /collections/mapping-info` - Get collection mapping configuration
- `POST /collections/clear-cache` - Clear collection mapping cache
- `GET /collections/statistics` - Product statistics across collections
- `GET /collections/estimate-large-sync` - Estimate resources for large sync operations

### Documentation
- `GET /docs` - Interactive API documentation (Swagger UI)

## Important Files

### Core Application
- **Main Application**: `app/main.py` (FastAPI app with middleware and route registration)
- **Configuration**: `app/config/settings.py` (Pydantic settings with environment variables)
- **Database Config**: `app/config/database.py` (Database connection and session management)
- **Database Models**: `app/models/database.py` (SQLAlchemy models for sync tracking)
- **Data Models**: `app/models/plytix.py`, `app/models/webflow.py` (API data structures)

### Core Services
- **Sync Service**: `app/services/sync_service.py` (Main synchronization logic)
- **Variant Service**: `app/services/variant_service.py` (Product variant processing)
- **Transform Service**: `app/services/transform_service.py` (Data transformation)
- **Field Mapping Service**: `app/services/field_mapping_service.py` (Custom field mappings)
- **Collection Mapping**: `app/services/collection_mapping_service.py` (Dynamic collections)
- **Auth Service**: `app/services/auth_service.py` (Authentication management)

### API Clients & Utilities
- **Plytix Client**: `app/clients/plytix_client.py` (Plytix API integration)
- **Webflow Client**: `app/clients/webflow_client.py` (Webflow API integration)
- **Rate Limiter**: `app/utils/rate_limiter.py` (API rate limiting)
- **Asset Handler**: `app/utils/asset_handler.py` (File and asset management)
- **Field Separator**: `app/utils/field_separator.py` (Field processing utilities)

### Background Tasks & Configuration
- **Celery App**: `app/tasks/celery_app.py` (Celery configuration)
- **Sync Tasks**: `app/tasks/sync_tasks.py` (Background sync tasks)
- **Field Mappings**: `field_mappings.json` (Field mapping configuration file)
- **Database Migrations**: `alembic/versions/` (Database schema versions)

### Infrastructure & Deployment
- **Docker Compose**: `docker-compose.yml` (Main services), `docker-compose.prod.yml` (Production)
- **Dockerfiles**: `Dockerfile` (API), `Dockerfile.worker` (Celery worker)
- **Scripts**: `scripts/start.sh` (Development startup), `scripts/migrate.sh` (Database migrations)
- **Deploy Scripts**: `deploy/` (Production deployment scripts)

## Development Workflow

1. **Environment Setup**: Copy `.env.example` to `.env` and configure credentials
2. **Database Setup**: Run `alembic upgrade head` to apply migrations
3. **Making Changes**: Edit code in `app/` directory following existing patterns
4. **Database Changes**: Create migrations with `alembic revision --autogenerate -m "Description"`
5. **API Changes**: Test with `/docs` endpoint (Swagger UI)
6. **Background Tasks**: Monitor with Flower at `http://localhost:5555`
7. **Field Mappings**: Test transformations via `/field-mappings/test-transform` endpoint
8. **Testing**: Run `pytest` before committing changes
9. **Deployment**: Use production Docker Compose configuration

## Monitoring and Debugging

- **Structured Logging**: JSON logging with structlog for all components
- **Health Checks**: Comprehensive health endpoints with external API verification
- **Task Monitoring**: Flower UI with authentication at port 5555
- **Performance Metrics**: Built-in statistics and performance monitoring
- **Error Tracking**: Detailed error logging with sync history
- **Database Access**: Direct PostgreSQL access for debugging
- **Configuration Validation**: Field mapping validation and testing endpoints

## Security & Best Practices

- **Environment Variables**: All credentials loaded from environment, never hardcoded
- **Authentication**: Secure API authentication for all external services
- **Database Security**: Connection pooling with secure credentials
- **Error Sanitization**: Logs sanitize sensitive information
- **Rate Limiting**: Respects API limits to prevent throttling
- **CORS Configuration**: Properly configured CORS middleware
- **File Upload Security**: Secure file handling for configuration imports
- **Never commit**: `.env` files with real credentials to version control

## Production Deployment

- **Docker Compose**: Use `docker-compose.prod.yml` for production
- **Environment**: Set `ENVIRONMENT=production` and `DEBUG=false`
- **Monitoring**: Enable Flower with secure credentials
- **Logging**: Configure structured logging with appropriate log levels
- **Scheduling**: Use production cron schedules for sync tasks
- **Health Checks**: Enable health check endpoints for load balancers