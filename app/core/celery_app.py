"""
Celery configuration for background task processing.
"""
from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery instance
celery_app = Celery(
    "riverside_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.video_processing"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Result backend settings
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    
    # Task routing
    task_routes={
        "app.tasks.video_processing.process_video": {"queue": "video_processing"},
    },
    
    # Task priorities
    task_default_priority=5,
    worker_disable_rate_limits=False,
    
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Task annotations for different priorities
celery_app.conf.task_annotations = {
    "app.tasks.video_processing.process_video": {
        "rate_limit": "10/m",  # Max 10 video processing tasks per minute
        "time_limit": 1800,    # 30 minutes max
        "soft_time_limit": 1500,  # 25 minutes soft limit
        "max_retries": 3,
        "default_retry_delay": 300,  # 5 minutes
    }
}

def init_celery():
    """Initialize Celery with the FastAPI app."""
    logger.info("Initializing Celery...")
    return celery_app 