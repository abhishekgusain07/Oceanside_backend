#!/usr/bin/env python3
"""
Test script to verify Celery and Redis setup for video processing.

Usage:
    python test_celery_setup.py
"""

import os
import sys
import asyncio
import logging
from datetime import datetime

# Add the current directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_redis_connection():
    """Test Redis connection."""
    try:
        import redis
        from app.core.config import settings
        
        logger.info("🔍 Testing Redis connection...")
        r = redis.from_url(settings.REDIS_URL)
        
        # Test basic operations
        test_key = f"test_key_{int(datetime.now().timestamp())}"
        r.set(test_key, "test_value", ex=10)  # Expire in 10 seconds
        value = r.get(test_key)
        
        if value == b"test_value":
            logger.info("✅ Redis connection successful")
            r.delete(test_key)
            return True
        else:
            logger.error("❌ Redis test failed - value mismatch")
            return False
            
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {str(e)}")
        return False

def test_celery_app():
    """Test Celery app initialization."""
    try:
        logger.info("🔍 Testing Celery app initialization...")
        from app.core.celery_app import celery_app
        
        # Check if the app is configured
        logger.info(f"✅ Celery app created: {celery_app.main}")
        logger.info(f"✅ Broker: {celery_app.conf.broker_url}")
        logger.info(f"✅ Backend: {celery_app.conf.result_backend}")
        
        # Check if tasks are registered
        registered_tasks = list(celery_app.tasks.keys())
        logger.info(f"✅ Registered tasks: {len(registered_tasks)}")
        
        for task in registered_tasks:
            if not task.startswith('celery.'):  # Skip built-in tasks
                logger.info(f"   - {task}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Celery app test failed: {str(e)}")
        return False

def test_video_processing_task():
    """Test video processing task registration."""
    try:
        logger.info("🔍 Testing video processing task...")
        from app.tasks.video_processing import process_video
        
        logger.info(f"✅ Video processing task imported: {process_video.name}")
        
        # Test task signature (don't actually run it)
        task_signature = process_video.signature(
            args=("test-room-id", "test-recording-id", "test-user-id")
        )
        logger.info(f"✅ Task signature created: {task_signature}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Video processing task test failed: {str(e)}")
        return False

def test_database_connection():
    """Test database connection for recording service."""
    try:
        logger.info("🔍 Testing database connection...")
        
        async def test_db():
            from app.core.database import AsyncSessionLocal
            from app.services.recording_service import RecordingService
            
            async with AsyncSessionLocal() as db:
                service = RecordingService(db)
                # Just test that we can create the service
                logger.info("✅ Recording service created successfully")
                return True
        
        return asyncio.run(test_db())
        
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {str(e)}")
        return False

def test_r2_storage():
    """Test R2 storage connection."""
    try:
        logger.info("🔍 Testing R2 storage connection...")
        
        async def test_r2():
            from app.services.r2_storage import r2_storage
            
            # Test basic configuration
            logger.info(f"✅ R2 bucket: {r2_storage.bucket_name}")
            logger.info(f"✅ R2 endpoint: {r2_storage.endpoint_url}")
            
            # Test presigned URL generation
            result = await r2_storage.generate_presigned_upload_url(
                recording_id="test-recording",
                chunk_index=1,
                content_type="video/webm",
                user_type="host"
            )
            
            if result:
                logger.info("✅ R2 presigned URL generation successful")
                return True
            else:
                logger.error("❌ R2 presigned URL generation failed")
                return False
        
        return asyncio.run(test_r2())
        
    except Exception as e:
        logger.error(f"❌ R2 storage test failed: {str(e)}")
        return False

def main():
    """Run all tests."""
    logger.info("🚀 Testing Riverside backend components...")
    logger.info("=" * 50)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Celery App", test_celery_app), 
        ("Video Processing Task", test_video_processing_task),
        ("Database Connection", test_database_connection),
        ("R2 Storage", test_r2_storage)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 Running {test_name} test...")
        try:
            results[test_name] = test_func()
        except Exception as e:
            logger.error(f"❌ {test_name} test crashed: {str(e)}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 50)
    logger.info("📊 Test Results Summary:")
    
    passed = 0
    failed = 0
    
    for test_name, passed_test in results.items():
        status = "✅ PASS" if passed_test else "❌ FAIL"
        logger.info(f"   {test_name}: {status}")
        
        if passed_test:
            passed += 1
        else:
            failed += 1
    
    logger.info(f"\n📈 Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        logger.info("🎉 All tests passed! Your system is ready for video processing.")
        logger.info("\n📋 Next steps:")
        logger.info("1. Start Redis: redis-server (or Docker)")
        logger.info("2. Start Celery worker: celery -A app.core.celery_app worker --loglevel=info")
        logger.info("3. Start FastAPI backend: uvicorn app.main:app --reload")
        logger.info("4. Test video recording and processing!")
    else:
        logger.error("⚠️ Some tests failed. Please fix the issues before proceeding.")
        
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)