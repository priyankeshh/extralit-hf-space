"""
RQ Worker for the Extralit HF-Space microservice.

This module provides the RQ worker implementation that processes PDF extraction
and chunking jobs. The worker is designed to run as a separate process and
can be scaled horizontally for increased throughput.

Usage:
    python -m src.worker

Environment Variables:
    RQ_REDIS_URL: Redis connection URL (default: redis://localhost:6379/0)
    RQ_QUEUES: Comma-separated list of queue names (default: extraction,chunking)
    WORKER_NAME: Optional worker name for identification
    LOG_LEVEL: Logging level (default: INFO)
"""

import os
import sys
import logging
import signal
from typing import List
from rq import Worker, Connection
from rq.middleware import Middleware

# Import job modules to register them with RQ
from .jobs import extraction_jobs  # noqa: F401
from .redis_connection import get_redis_connection_manager
from .config import get_rq_config, get_service_config


class WorkerMiddleware(Middleware):
    """
    Custom middleware for RQ workers to add logging and monitoring.

    This middleware provides additional logging and can be extended
    for metrics collection and error reporting.
    """

    def call(self, queue, job_func, job, *args, **kwargs):
        """
        Called for each job execution.

        Args:
            queue: The RQ queue
            job_func: The job function being executed
            job: The RQ job instance
            *args: Job arguments
            **kwargs: Job keyword arguments
        """
        logger = logging.getLogger(__name__)

        logger.info(
            f"Starting job {job.id} ({job_func.__name__}) on queue {queue.name}"
        )

        try:
            # Execute the job
            result = job_func(*args, **kwargs)

            logger.info(
                f"Completed job {job.id} successfully"
            )

            return result

        except Exception as e:
            logger.error(
                f"Job {job.id} failed with error: {str(e)}"
            )
            raise


def setup_logging():
    """Configure logging for the worker process."""
    config = get_service_config()

    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set specific log levels for noisy libraries
    logging.getLogger("rq.worker").setLevel(logging.INFO)
    logging.getLogger("redis").setLevel(logging.WARNING)


def create_worker(queue_names: List[str], worker_name: str = None) -> Worker:
    """
    Create and configure an RQ worker.

    Args:
        queue_names: List of queue names to process
        worker_name: Optional worker name for identification

    Returns:
        Worker: Configured RQ worker instance
    """
    connection_manager = get_redis_connection_manager()

    # Get queue instances
    queues = []
    for queue_name in queue_names:
        queues.append(connection_manager.get_queue(queue_name))

    # Create worker with custom middleware
    worker = Worker(
        queues,
        connection=connection_manager.redis_connection,
        name=worker_name,
        middlewares=[WorkerMiddleware()]
    )

    return worker


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down worker...")

    # Close Redis connections
    connection_manager = get_redis_connection_manager()
    connection_manager.close()

    sys.exit(0)


def main():
    """
    Main entry point for the RQ worker.

    This function sets up logging, creates the worker, and starts processing jobs.
    It handles graceful shutdown on SIGINT and SIGTERM signals.
    """
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Get configuration
        rq_config = get_rq_config()

        # Get worker name from environment or generate one
        worker_name = os.getenv("WORKER_NAME")
        if not worker_name:
            import socket
            worker_name = f"worker-{socket.gethostname()}-{os.getpid()}"

        logger.info(f"Starting RQ worker: {worker_name}")
        logger.info(f"Processing queues: {rq_config.queues}")
        logger.info(f"Redis URL: {rq_config.redis_url}")

        # Test Redis connection
        connection_manager = get_redis_connection_manager()
        if not connection_manager.health_check():
            logger.error("Failed to connect to Redis. Exiting.")
            sys.exit(1)

        # Create and start worker
        worker = create_worker(rq_config.queues, worker_name)

        logger.info("Worker started successfully. Waiting for jobs...")

        # Start processing jobs (this blocks until shutdown)
        with Connection(connection_manager.redis_connection):
            worker.work(logging_level="INFO")

    except KeyboardInterrupt:
        logger.info("Worker interrupted by user")
    except Exception as e:
        logger.exception(f"Worker failed with error: {e}")
        sys.exit(1)
    finally:
        logger.info("Worker shutdown complete")


if __name__ == "__main__":
    main()