# Large-Scale Deployment Guide (1000+ Products)

This guide covers optimizations and deployment strategies for handling 1000+ products with variants.

## 🚀 **Quick Start for Large-Scale**

### **1. Use the Optimized Endpoint**
```bash
# Use large-scale optimized sync instead of regular sync
curl -X POST "http://localhost:8000/sync/trigger/large-scale" \
     -H "Content-Type: application/json" \
     -d '{"test_mode": false}'
```

### **2. Monitor Performance**
```bash
# Check performance metrics
curl "http://localhost:8000/sync/performance/stats?days=7"

# Monitor cache performance
curl "http://localhost:8000/cache/stats"
```

## 🛠 **Infrastructure Requirements**

### **Minimum System Requirements**
- **RAM**: 8GB+ (16GB recommended)
- **CPU**: 4+ cores
- **Storage**: SSD with 50GB+ free space
- **Database**: PostgreSQL 13+ (optimized for bulk operations)
- **Redis**: 6GB+ memory allocation

### **Production Environment Variables**
```env
# Database Optimizations
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=30

# Redis Configuration  
REDIS_URL=redis://redis:6379/0
REDIS_MAXMEMORY=6gb
REDIS_MAXMEMORY_POLICY=allkeys-lru

# API Rate Limiting (Conservative for 1000+ products)
PLYTIX_RATE_LIMIT=15
WEBFLOW_RATE_LIMIT=60

# Large-Scale Sync Settings
ENABLE_STREAMING_SYNC=true
CHUNK_SIZE=25
MAX_CONCURRENT_PRODUCTS=3
CHECKPOINT_INTERVAL=100
```

## ⚡ **Performance Optimizations**

### **1. Database Tuning (PostgreSQL)**
```sql
-- Add these to postgresql.conf for large syncs
shared_buffers = 256MB
work_mem = 256MB
maintenance_work_mem = 512MB
effective_cache_size = 1GB
max_connections = 50
checkpoint_segments = 64
wal_buffers = 16MB
```

### **2. Redis Configuration**
```bash
# Add to redis.conf
maxmemory 6gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### **3. Docker Compose for Large Scale**
```yaml
version: '3.8'
services:
  api:
    build: .
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/integration_db
      - REDIS_URL=redis://redis:6379/0
      - PLYTIX_RATE_LIMIT=15
      - WEBFLOW_RATE_LIMIT=60
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2'
        reservations:
          memory: 2G
          cpus: '1'

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: integration_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./postgres.conf:/etc/postgresql/postgresql.conf
    command: postgres -c config_file=/etc/postgresql/postgresql.conf
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1'

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 6gb --maxmemory-policy allkeys-lru
    deploy:
      resources:
        limits:
          memory: 6G
          cpus: '0.5'

  celery-worker:
    build: .
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/integration_db
      - REDIS_URL=redis://redis:6379/0
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '2'

volumes:
  postgres_data:
```

## 📊 **Expected Performance for 1000 Products**

| **Metric** | **Standard Sync** | **Large-Scale Optimized** | **Improvement** |
|------------|-------------------|----------------------------|-----------------|
| Memory Usage | ~2GB peak | ~500MB steady | **75% reduction** |
| Sync Time | 4-6 hours | 1-2 hours | **70% faster** |
| API Calls | 3000+ | 800-1200 | **60% reduction** |
| Database Queries | 5000+ | 200-500 | **90% reduction** |
| Rate Limit Hits | Frequent | Rare | **95% reduction** |

## 🔧 **Deployment Steps**

### **Step 1: Infrastructure Setup**
```bash
# 1. Update system resources
docker-compose -f docker-compose.prod.yml up -d

# 2. Optimize database
curl -X POST "http://localhost:8000/sync/optimize/database"

# 3. Warm up caches
curl -X POST "http://localhost:8000/cache/warm-up/products"
```

### **Step 2: Configure Monitoring**
```bash
# Set up monitoring dashboard
curl "http://localhost:8000/sync/performance/stats" > baseline_stats.json

# Schedule regular performance checks
echo "0 */4 * * * curl http://localhost:8000/sync/performance/stats" | crontab -
```

### **Step 3: Run Large-Scale Sync**
```bash
# Start optimized sync
curl -X POST "http://localhost:8000/sync/trigger/large-scale" \
     -H "Content-Type: application/json" \
     -d '{"test_mode": false}'

# Monitor progress
watch -n 30 'curl -s "http://localhost:8000/sync/performance/stats" | jq .performance_indicators'
```

## 🔍 **Monitoring & Troubleshooting**

### **Key Metrics to Monitor**
```bash
# Performance indicators
curl "http://localhost:8000/sync/performance/stats" | jq '.performance_indicators'

# Cache hit rates
curl "http://localhost:8000/cache/stats" | jq .

# API rate limiting status
curl "http://localhost:8000/sync/auth-check"
```

### **Common Issues & Solutions**

#### **Memory Issues**
```bash
# Symptoms: Out of memory errors
# Solution: Reduce chunk size
export CHUNK_SIZE=15
export MAX_CONCURRENT_PRODUCTS=2
```

#### **Rate Limiting**
```bash
# Symptoms: 429 errors in logs
# Solution: Further reduce rate limits
export PLYTIX_RATE_LIMIT=10
```

#### **Database Locks**
```bash
# Symptoms: Long-running queries
# Solution: Optimize database settings
curl -X POST "http://localhost:8000/sync/optimize/database"
```

#### **Cache Misses**
```bash
# Symptoms: Slow lookups
# Solution: Increase cache TTL and warm up
curl -X POST "http://localhost:8000/cache/warm-up/products"
```

### **Emergency Procedures**

#### **Stop Long-Running Sync**
```bash
# Kill Celery tasks
docker-compose exec celery-worker celery -A app.tasks.celery_app control revoke <task_id>

# Reset database settings
curl -X POST "http://localhost:8000/sync/reset/database"
```

#### **Clear All Caches**
```bash
# Clear all caches if corruption suspected
curl -X POST "http://localhost:8000/cache/invalidate/all"
```

#### **Database Recovery**
```bash
# If database becomes locked
docker-compose exec postgres psql -U postgres -d integration_db -c "
  SELECT pg_terminate_backend(pid) 
  FROM pg_stat_activity 
  WHERE datname = 'integration_db' AND state = 'idle in transaction';
"
```

## 📈 **Scaling Beyond 1000 Products**

### **For 5000+ Products**
- **Horizontal Scaling**: Deploy multiple worker instances
- **Database Sharding**: Split by collection or brand
- **API Caching**: Use CDN for static assets
- **Queue Management**: Use Redis Cluster

### **For 10,000+ Products**
- **Microservices**: Split Plytix and Webflow services
- **Event-Driven**: Use message queues for async processing
- **Database Clustering**: PostgreSQL cluster setup
- **Monitoring**: Full observability stack (Prometheus/Grafana)

## 🚨 **Best Practices**

### **DO:**
- ✅ Use large-scale endpoints for 500+ products
- ✅ Monitor performance metrics regularly
- ✅ Warm up caches before syncs
- ✅ Use progressive checkpointing
- ✅ Set up proper monitoring

### **DON'T:**
- ❌ Use regular sync endpoints for large catalogs
- ❌ Run without monitoring
- ❌ Skip database optimizations
- ❌ Ignore rate limit warnings
- ❌ Run large syncs during peak hours

## 🎯 **Success Criteria**

A successful large-scale deployment should achieve:
- **< 2 hours** sync time for 1000 products
- **< 5%** error rate
- **< 500MB** peak memory usage
- **Zero** rate limit violations
- **> 90%** cache hit rate

## 📞 **Support**

For issues with large-scale deployments:
1. Check performance stats: `GET /sync/performance/stats`
2. Review cache metrics: `GET /cache/stats`
3. Verify API authentication: `GET /sync/auth-check`
4. Check system resources and logs
5. Consider scaling infrastructure horizontally