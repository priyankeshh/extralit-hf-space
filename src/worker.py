import os
import sys
import redis
from rq import Worker, Queue

# Pre-import heavy libs (PyMuPDF imported by jobs module)
from .jobs import extraction_jobs  # noqa: F401

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUES = os.getenv("RQ_QUEUES", "extraction").split(",")

def main():
    conn = redis.from_url(REDIS_URL)
    queues = [Queue(name.strip(), connection=conn) for name in QUEUES if name.strip()]
    
    # Windows compatibility: use SimpleWorker which doesn't fork
    if sys.platform.startswith('win'):
        from rq import SimpleWorker
        w = SimpleWorker(queues, connection=conn)
        print("🪟 Starting SimpleWorker for Windows compatibility...")
    else:
        w = Worker(queues, connection=conn)
        print("🐧 Starting standard Worker...")
    
    w.work(logging_level="INFO")

if __name__ == "__main__":
    main()
