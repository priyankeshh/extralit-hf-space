import os
import sys
import redis
from rq import Worker, Queue

# Import PDF extraction jobs to register them
from .jobs.pdf_extraction_jobs import extract_pdf_from_s3_job  # noqa: F401

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Primary queue for direct RQ communication with extralit-server
QUEUES = os.getenv("RQ_QUEUES", "pdf_queue,high_priority,low_priority").split(",")

def main():
    conn = redis.from_url(REDIS_URL)
    queues = [Queue(name.strip(), connection=conn) for name in QUEUES if name.strip()]

    # Windows compatibility: use SimpleWorker which doesn't fork
    if sys.platform.startswith('win'):
        from rq import SimpleWorker
        w = SimpleWorker(queues, connection=conn)
        print("🪟 Starting SimpleWorker for Windows compatibility...")
        print(f"📋 Listening on queues: {[q.name for q in queues]}")
    else:
        w = Worker(queues, connection=conn)
        print("🐧 Starting standard Worker...")
        print(f"📋 Listening on queues: {[q.name for q in queues]}")

    w.work(logging_level="INFO")

if __name__ == "__main__":
    main()
