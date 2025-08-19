"""
Test script to verify worker can start without errors.
"""

import sys
import os
sys.path.insert(0, '../src')

def test_worker_startup():
    """Test that worker can be imported and initialized without errors."""
    try:
        # Test basic imports
        from worker import main
        print("✅ Successfully imported worker main function")

        # Test job imports (with expected warnings about extralit_server)
        from jobs.pdf_extraction_jobs import extract_pdf_from_s3_job
        print("✅ Successfully imported PDF extraction job")

        # Test Redis connection setup
        from redis_connection import get_redis_connection, PDF_QUEUE
        print(f"✅ Redis connection setup successful, PDF_QUEUE: {PDF_QUEUE}")

        # Test RQ imports
        from rq import Queue, Worker
        print("✅ RQ imports successful")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_queue_creation():
    """Test that queues can be created without Redis connection."""
    try:
        import redis
        from rq import Queue

        # Mock Redis connection for testing
        class MockRedis:
            def ping(self):
                raise redis.ConnectionError("Mock Redis not connected")

        mock_conn = MockRedis()

        # This should work even with mock connection
        queue = Queue("test_queue", connection=mock_conn)
        print(f"✅ Queue creation successful: {queue.name}")
        return True

    except Exception as e:
        print(f"❌ Queue creation failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing worker startup capabilities...")

    startup_success = test_worker_startup()
    queue_success = test_queue_creation()

    if startup_success and queue_success:
        print("\n🎉 Worker startup tests passed!")
        print("Note: Redis connection warnings are expected without running Redis server")
    else:
        print("\n💥 Worker startup tests failed!")
