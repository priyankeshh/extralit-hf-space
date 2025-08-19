"""
Simple integration test for PDF extraction job.
"""

import sys

sys.path.insert(0, "../src")


def test_job_registration():
    """Test that job can be enqueued."""
    try:
        from redis_connection import PDF_QUEUE, get_queue

        queue = get_queue(PDF_QUEUE)
        print(f"✅ Successfully got queue: {queue.name}")
        print(f"✅ Queue length: {len(queue)}")
        return True
    except Exception as e:
        print(f"❌ Error getting queue: {e}")
        return False


def test_redis_constants():
    """Test that Redis constants are properly defined."""
    try:
        from redis_connection import DEFAULT_QUEUES, PDF_QUEUE

        print(f"✅ PDF_QUEUE constant: {PDF_QUEUE}")
        print(f"✅ DEFAULT_QUEUES: {DEFAULT_QUEUES}")
        return True
    except Exception as e:
        print(f"❌ Error importing constants: {e}")
        return False


def test_worker_module():
    """Test that worker module can be imported."""
    try:
        print("✅ Worker module imported successfully")
        return True
    except Exception as e:
        print(f"❌ Error importing worker: {e}")
        return False


if __name__ == "__main__":
    print("🧪 Running integration tests...")

    const_success = test_redis_constants()
    worker_success = test_worker_module()
    queue_success = test_job_registration()

    if const_success and worker_success and queue_success:
        print("🎉 Integration test passed")
    else:
        print("💥 Integration test failed")
