from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
import structlog
import os

logger = structlog.get_logger()

class Base(DeclarativeBase):
    pass

# Initialize these as None, will be set up conditionally
engine = None
AsyncSessionLocal = None

def setup_database():
    """Setup database based on environment"""
    global engine, AsyncSessionLocal
    
    from app.config.settings import get_settings
    settings = get_settings()
    
    database_url = settings.DATABASE_URL
    
    # Handle SQLite for simple mode
    if database_url.startswith("sqlite"):
        database_url = database_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    
    # Create async engine
    engine = create_async_engine(
        database_url,
        echo=settings.DEBUG,
        pool_pre_ping=True,
        pool_recycle=3600
    )

    # Create session factory
    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

async def create_tables():
    """Create database tables"""
    if engine is None:
        setup_database()
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

async def get_db():
    """Dependency to get database session"""
    if AsyncSessionLocal is None:
        setup_database()
        
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()