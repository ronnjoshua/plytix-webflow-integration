# Plytix to Webflow E-commerce Integration

A robust Python FastAPI application that synchronizes products and their variants from Plytix PIM to Webflow E-commerce in one direction (Plytix → Webflow). The system handles complex product variants, maintains data integrity, and runs on a scheduled basis.

## Features

- **Complete Product Synchronization**: Syncs products with complex variant matrices
- **Async Architecture**: Built with FastAPI and async/await for high performance
- **Rate Limiting**: Respects API rate limits for both Plytix and Webflow
- **Error Handling**: Comprehensive error tracking and reporting
- **Background Processing**: Celery-based task queue for scheduled syncs
- **Monitoring**: Built-in health checks and performance metrics
- **Database Tracking**: Full audit trail of sync operations
- **Docker Support**: Complete containerization for easy deployment

## Technology Stack

- **Framework**: FastAPI 0.104.1
- **Database**: PostgreSQL with SQLAlchemy 2.0 (async)
- **Task Queue**: Celery with Redis
- **HTTP Client**: httpx with tenacity for retries
- **Logging**: Structured logging with structlog
- **Containerization**: Docker and Docker Compose

## Project Structure

```
plytix-webflow-integration/
├── app/
│   ├── api/routes/           # FastAPI route handlers
│   ├── clients/              # API clients for Plytix and Webflow
│   ├── config/               # Configuration and settings
│   ├── core/                 # Core utilities and exceptions
│   ├── models/               # Pydantic and SQLAlchemy models
│   ├── services/             # Business logic services
│   ├── tasks/                # Celery background tasks
│   └── utils/                # Utility functions
├── alembic/                  # Database migrations
├── docker/                   # Docker configuration
├── scripts/                  # Deployment and utility scripts
└── tests/                    # Test suite
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL
- Redis

### Environment Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd plytix-webflow-integration
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

3. **Configure your credentials** in `.env`:
   ```env
   # Required API credentials
   PLYTIX_API_KEY=your_plytix_api_key_here
   WEBFLOW_TOKEN=your_webflow_token_here
   WEBFLOW_SITE_ID=your_webflow_site_id_here
   
   # Database connection
   DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/integration_db
   ```

### Development Setup

1. **Using Docker (Recommended)**:
   ```bash
   # Start all services
   chmod +x scripts/start.sh
   ./scripts/start.sh
   ```

2. **Manual Setup**:
   ```bash
   # Install dependencies
   pip install -r requirements.txt
   
   # Start infrastructure
   docker-compose up -d postgres redis
   
   # Run migrations
   alembic upgrade head
   
   # Start the API
   uvicorn app.main:app --reload
   
   # Start Celery worker (in another terminal)
   celery -A app.tasks.celery_app worker --loglevel=info
   
   # Start Celery beat scheduler (in another terminal)
   celery -A app.tasks.celery_app beat --loglevel=info
   ```

### Production Deployment

```bash
# Deploy with production configuration
docker-compose -f docker-compose.prod.yml up -d
```

## API Endpoints

### Health Checks
- `GET /health/` - Basic health check
- `GET /health/detailed` - Detailed service health status

### Synchronization
- `POST /sync/trigger` - Manually trigger full sync
- `POST /sync/trigger/product/{product_id}` - Sync single product
- `GET /sync/status/{task_id}` - Get sync task status
- `GET /sync/history` - Get sync history
- `GET /sync/errors/{sync_id}` - Get errors for specific sync

### Monitoring
- `GET /monitoring/stats` - Sync statistics
- `GET /monitoring/recent-activity` - Recent activity log
- `GET /monitoring/health-metrics` - System health metrics

### Interactive Documentation
- Access Swagger UI at: `http://localhost:8000/docs`
- Access ReDoc at: `http://localhost:8000/redoc`

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PLYTIX_API_KEY` | Plytix API key | Required |
| `PLYTIX_BASE_URL` | Plytix API base URL | `https://pim.plytix.com/api/v1` |
| `PLYTIX_RATE_LIMIT` | Requests per 10 seconds | `50` |
| `WEBFLOW_TOKEN` | Webflow API token | Required |
| `WEBFLOW_SITE_ID` | Webflow site ID | Required |
| `WEBFLOW_COLLECTION_ID` | Webflow E-commerce collection ID | Required |
| `WEBFLOW_BASE_URL` | Webflow API base URL | `https://api.webflow.com/v2` |
| `WEBFLOW_RATE_LIMIT` | Requests per minute | `60` |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |

### Sync Scheduling

The system supports two sync schedules:

- **Production**: Every 2 days at midnight (`0 0 */2 * *`)
- **Testing**: Every minute (`*/1 * * * *`)

Configure via:
- `SYNC_SCHEDULE_PRODUCTION`
- `SYNC_SCHEDULE_TESTING`

## Architecture

### Data Flow

1. **Scheduled Trigger**: Celery Beat triggers sync tasks
2. **Product Fetching**: Plytix client fetches products with variants
3. **Variant Processing**: Complex variant matrices are generated
4. **Data Transformation**: Plytix data is transformed to Webflow format
5. **Webflow Sync**: Products are created/updated in Webflow
6. **Database Tracking**: All operations are logged and tracked

### Variant Handling

The system handles complex product variants by:
- Extracting variant attributes from Plytix
- Creating complete SKU matrices for Webflow
- Mapping variant combinations intelligently
- Handling missing variant combinations gracefully

### Error Handling

- **Retry Logic**: Automatic retries with exponential backoff
- **Error Tracking**: All errors are logged to database
- **Graceful Degradation**: Partial sync failures don't stop entire process
- **Monitoring**: Real-time error tracking and alerting

## Database Schema

### Core Tables

- **sync_states**: Track sync execution status and metrics
- **product_mappings**: Map Plytix products to Webflow products
- **variant_mappings**: Map individual variants between systems
- **sync_errors**: Log all sync errors with context

### Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_sync_service.py
```

## Monitoring

### Celery Flower
Monitor background tasks at: `http://localhost:5555`

### Logging
Structured JSON logging with:
- Request/response tracking
- Performance metrics
- Error context
- Business event logging

### Health Monitoring
- Database connectivity
- External API availability
- Task queue status
- Sync success rates

## Performance Optimization

- **Batch Processing**: Products processed in configurable batches
- **Async Operations**: Non-blocking I/O throughout
- **Connection Pooling**: Efficient database connections
- **Rate Limiting**: Prevents API overuse
- **Caching**: Strategic caching of API responses

## Security

- **Environment Variables**: Sensitive data in environment
- **API Key Management**: Secure credential handling
- **Input Validation**: Comprehensive data validation
- **Error Sanitization**: No sensitive data in logs

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   ```bash
   # Check PostgreSQL is running
   docker-compose logs postgres
   
   # Verify connection string
   echo $DATABASE_URL
   ```

2. **API Authentication Failures**:
   ```bash
   # Verify API credentials
   curl -H "Authorization: Bearer $PLYTIX_API_KEY" https://pim.plytix.com/api/v1/products?page_size=1
   ```

3. **Celery Tasks Not Running**:
   ```bash
   # Check Redis connection
   docker-compose logs redis
   
   # Restart Celery services
   docker-compose restart celery-worker celery-beat
   ```

### Debug Mode

Enable debug logging:
```env
DEBUG=True
LOG_LEVEL=DEBUG
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support and questions:
- Check the [API documentation](http://localhost:8000/docs)
- Review the [troubleshooting guide](#troubleshooting)
- Create an issue on GitHub

## Roadmap

- [ ] Webhook support for real-time sync triggers
- [ ] Advanced variant mapping rules
- [ ] Multi-site Webflow support
- [ ] Enhanced monitoring dashboard
- [ ] Performance analytics
- [ ] Custom field mapping