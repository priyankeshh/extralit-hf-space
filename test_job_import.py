"""
Simple test script to verify job imports work correctly.
"""

import sys
import os
sys.path.insert(0, 'src')

def test_job_import():
    """Test that PDF extraction job can be imported."""
    try:
        from jobs.pdf_extraction_jobs import extract_pdf_from_s3_job
        print("✅ Successfully imported extract_pdf_from_s3_job")
        return True
    except ImportError as e:
        print(f"❌ Failed to import job: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_redis_connection():
    """Test Redis connection setup."""
    try:
        from redis_connection import get_redis_connection, PDF_QUEUE
        conn = get_redis_connection()
        conn.ping()
        print("✅ Redis connection successful")
        print(f"✅ PDF_QUEUE constant: {PDF_QUEUE}")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing job imports and Redis connection...")

    import_success = test_job_import()
    redis_success = test_redis_connection()

    if import_success and redis_success:
        print("\n🎉 All tests passed!")
    else:
        print("\n💥 Some tests failed!")
