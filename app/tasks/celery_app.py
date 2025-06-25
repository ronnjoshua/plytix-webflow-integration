from celery import Celery
from celery.schedules import crontab
from app.config.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "plytix_webflow_integration",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.sync_tasks"]
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",  # Back to JSON for better compatibility
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=3600,  # Results expire after 1 hour
    task_ignore_result=False,  # Store results
    task_store_errors_even_if_ignored=True,  # Always store errors
)

# Periodic tasks configuration
celery_app.conf.beat_schedule = {
    "sync-products-production": {
        "task": "app.tasks.sync_tasks.run_scheduled_sync",
        "schedule": crontab(minute=0, hour=0, day_of_month='*/2'),  # Every 2 days at midnight
        "kwargs": {"test_mode": False}
    },
    "sync-products-testing": {
        "task": "app.tasks.sync_tasks.run_scheduled_sync", 
        "schedule": crontab(minute='*/5'),  # Every 5 minutes (changed from every minute to reduce load)
        "kwargs": {"test_mode": True}
    },
}

if __name__ == "__main__":
    celery_app.start()