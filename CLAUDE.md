# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a complete Python FastAPI application that synchronizes products and their variants from Plytix PIM to Webflow E-commerce in one direction (Plytix → Webflow). The system handles complex product variants, maintains data integrity, and runs on a scheduled basis.

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

# Monitor tasks with Flower
celery -A app.tasks.celery_app flower --port=5555
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test
pytest tests/test_sync_service.py -v
```

### Docker Operations
```bash
# Development environment
docker-compose up -d

# Production deployment
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose logs -f api
docker-compose logs -f celery-worker

# Rebuild containers
docker-compose build --no-cache
```

## Architecture Overview

### Core Components

1. **FastAPI Application** (`app/main.py`): Main web server with async endpoints
2. **Database Models** (`app/models/database.py`): SQLAlchemy models for tracking sync state
3. **API Clients** (`app/clients/`): Async HTTP clients for Plytix and Webflow APIs
4. **Services** (`app/services/`): Business logic for variant processing and synchronization
5. **Celery Tasks** (`app/tasks/`): Background job processing and scheduling
6. **API Routes** (`app/api/routes/`): REST endpoints for manual triggers and monitoring

### Data Flow

1. Celery Beat triggers scheduled sync tasks
2. Plytix client fetches products with variants
3. Variant service processes complex variant matrices
4. Transform service converts Plytix format to Webflow format
5. Webflow client creates/updates products
6. Database tracks all operations and errors

### Key Features

- **Async Architecture**: Built with FastAPI and asyncio for high performance
- **Rate Limiting**: Respects API limits for both Plytix and Webflow
- **Variant Processing**: Handles complex product variant matrices intelligently
- **Error Handling**: Comprehensive error tracking with retry logic
- **Monitoring**: Built-in health checks and performance metrics
- **Scheduling**: Configurable sync schedules via Celery Beat
- **Enhanced Field Mapping**: Custom field mappings with automatic image discovery
- **SKU-Based Matching**: Product identification using SKU instead of ID
- **Scalable Architecture**: Handles 2K+ products with 20+ variants each

## Environment Configuration

### Required Environment Variables
```env
# API Credentials (Required)
PLYTIX_API_KEY=your_plytix_api_key
WEBFLOW_TOKEN=your_webflow_token
WEBFLOW_SITE_ID=your_webflow_site_id
WEBFLOW_COLLECTION_ID=your_webflow_collection_id

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/integration_db

# Redis/Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### API Endpoints

#### Core Functionality
- `GET /health/` - Health check
- `POST /sync/trigger` - Manual sync trigger
- `GET /sync/status/{task_id}` - Check sync status
- `GET /sync/history` - Sync history
- `GET /monitoring/stats` - Performance statistics

#### Enhanced Field Mapping
- `GET /field-mappings/current` - Get current field mappings
- `POST /field-mappings/update` - Update field mappings
- `POST /field-mappings/test-transform` - Test field transformations
- `POST /field-mappings/discover-images` - Auto-discover image fields
- `GET /field-mappings/sample-mapping` - Get sample configuration

#### Collection Management
- `GET /collections/estimate-large-sync` - Estimate sync for large catalogs
- `GET /collections/statistics` - Collection usage statistics
- `GET /collections/mapping-info` - Dynamic collection mapping info

#### Documentation
- `GET /docs` - Interactive API documentation

## Important Files

### Core Application
- **Configuration**: `app/config/settings.py` (Pydantic settings)
- **Database Models**: `app/models/database.py` (SQLAlchemy models)
- **Main Sync Logic**: `app/services/sync_service.py`
- **Variant Processing**: `app/services/variant_service.py`
- **API Clients**: `app/clients/plytix_client.py`, `app/clients/webflow_client.py`
- **Background Tasks**: `app/tasks/sync_tasks.py`
- **Database Migrations**: `alembic/versions/`

### Enhanced Features
- **Field Mapping Service**: `app/services/field_mapping_service.py` (Custom field mappings)
- **Collection Mapping**: `app/services/collection_mapping_service.py` (Dynamic collections)
- **Field Mapping Config**: `field_mappings.json` (Configuration file)
- **Field Mapping API**: `app/api/routes/field_mappings.py` (Management endpoints)

### Documentation
- **Enhanced Features**: `ENHANCED_FEATURES.md` (New field mapping capabilities)
- **Dynamic Collections**: `DYNAMIC_COLLECTIONS.md` (Large-scale sync guide)

## Development Workflow

1. **Making Changes**: Edit code in `app/` directory
2. **Database Changes**: Create migrations with `alembic revision --autogenerate`
3. **API Changes**: Test with `/docs` endpoint
4. **Background Tasks**: Monitor with Flower at `http://localhost:5555`
5. **Testing**: Run pytest before committing
6. **Deployment**: Use production Docker Compose

## Monitoring and Debugging

- **Logs**: Structured JSON logging with structlog
- **Health Checks**: `/health/detailed` endpoint
- **Task Monitoring**: Flower UI at port 5555
- **Database**: Direct PostgreSQL access for debugging
- **Performance**: Built-in metrics and timing

## Security Notes

- Never commit `.env` file with real credentials
- API keys are loaded from environment variables only
- All external API calls use secure authentication
- Database connections use connection pooling
- Error logs sanitize sensitive information