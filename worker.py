import os
import logging

from redis import Redis
from rq import Worker, Queue, Connection

# Import the module that defines your extraction function.
# Ensure that `tasks.py` (or wherever you define extract_text) is in the PYTHONPATH.
import tasks  

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

def main():
    """
    Launch an RQ Worker listening on the `pymupdf` queue.
    The worker will pick up jobs that call `tasks.extract_text`,
    passing in raw PDF bytes and returning extracted text.
    """
    redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
    logger.info(f"Connecting to Redis at {redis_url}")
    conn = Redis.from_url(redis_url)

    queue_names = ["pymupdf"]
    logger.info(f"Starting RQ worker for queues: {queue_names}")

    with Connection(conn):
        queues = [Queue(name, connection=conn) for name in queue_names]
        worker = Worker(queues)
        worker.work()

if __name__ == "__main__":
    main()