"""
Metrics endpoint for monitoring application performance.
"""
from fastapi import APIRouter, Depends, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import Counter, Histogram, Gauge
import time
import psutil
import structlog

from app.core.middleware import get_request_id
from app.core.request_tracker import request_tracker

logger = structlog.get_logger(__name__)

router = APIRouter()

# Prometheus metrics
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

ACTIVE_REQUESTS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests in progress',
    ['method', 'endpoint']
)

SYSTEM_MEMORY = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes'
)

SYSTEM_CPU = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

@router.get("/metrics")
async def metrics():
    """
    Expose Prometheus metrics endpoint.
    """
    # Update system metrics
    SYSTEM_MEMORY.set(psutil.virtual_memory().used)
    SYSTEM_CPU.set(psutil.cpu_percent())
    
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/system")
async def system_metrics():
    """
    Get detailed system metrics.
    """
    memory = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=1)
    disk = psutil.disk_usage('/')
    
    return {
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "used": memory.used,
            "percent": memory.percent
        },
        "cpu": {
            "usage_percent": cpu
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent
        }
    }

@router.get("/requests")
async def request_stats():
    """
    Get detailed request statistics.
    """
    active_requests = await request_tracker.get_active_requests()
    stats = await request_tracker.get_request_stats()
    
    return {
        "active_requests": active_requests,
        "statistics": stats
    } 