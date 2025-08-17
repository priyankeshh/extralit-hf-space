"""
Redis connection management for RQ-based PDF extraction jobs.

This module provides centralized Redis connection management and queue configuration
for the PDF extraction service. It handles connection pooling, error recovery,
and queue setup for different types of extraction jobs.

The module follows the principle of keeping AGPL-licensed code (PyMuPDF) isolated
while providing clean interfaces for job enqueueing and status monitoring.
"""

from __future__ import annotations

import os
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

import redis
from rq import Queue


LOGGER = logging.getLogger("pdf-redis-connection")


class RedisConnectionManager:
    """
    Manages Redis connections and RQ queues for the PDF extraction service.
    
    This class provides a centralized way to handle Redis connections with
    proper error handling, connection pooling, and queue management.
    It supports both single Redis instances and Redis clusters.
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize the Redis connection manager.
        
        Args:
            redis_url: Redis connection URL. If None, uses REDIS_URL environment variable.
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._connection: Optional[redis.Redis] = None
        self._queues: Dict[str, Queue] = {}
        
        # Parse Redis URL to extract connection parameters
        parsed = urlparse(self.redis_url)
        self.host = parsed.hostname or "localhost"
        self.port = parsed.port or 6379
        self.db = int(parsed.path.lstrip('/')) if parsed.path else 0
        self.password = parsed.password
        
        LOGGER.info(f"Initialized Redis connection manager for {self.host}:{self.port}/{self.db}")
    
    @property
    def connection(self) -> redis.Redis:
        """
        Get or create a Redis connection with proper error handling.
        
        Returns:
            Redis connection instance
            
        Raises:
            ConnectionError: If unable to establish Redis connection
        """
        if self._connection is None:
            try:
                self._connection = redis.from_url(
                    self.redis_url,
                    decode_responses=False,  # Keep binary data for PDF processing
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True,
                    health_check_interval=30
                )
                
                # Test the connection
                self._connection.ping()
                LOGGER.info("Successfully established Redis connection")
                
            except Exception as e:
                LOGGER.error(f"Failed to connect to Redis at {self.redis_url}: {e}")
                raise redis.ConnectionError(f"Redis connection failed: {e}") from e
        
        return self._connection
    
    def get_queue(self, queue_name: str) -> Queue:
        """
        Get or create an RQ queue with the specified name.
        
        Args:
            queue_name: Name of the queue to retrieve or create
            
        Returns:
            RQ Queue instance
        """
        if queue_name not in self._queues:
            try:
                self._queues[queue_name] = Queue(
                    queue_name,
                    connection=self.connection,
                    default_timeout=600  # 10 minutes default timeout
                )
                LOGGER.info(f"Created queue: {queue_name}")
            except Exception as e:
                LOGGER.error(f"Failed to create queue {queue_name}: {e}")
                raise
        
        return self._queues[queue_name]
    
    def health_check(self) -> bool:
        """
        Perform a health check on the Redis connection.
        
        Returns:
            True if Redis is healthy, False otherwise
        """
        try:
            self.connection.ping()
            return True
        except Exception as e:
            LOGGER.warning(f"Redis health check failed: {e}")
            return False
    
    def get_queue_info(self, queue_name: str) -> Dict[str, Any]:
        """
        Get information about a specific queue.
        
        Args:
            queue_name: Name of the queue to inspect
            
        Returns:
            Dictionary containing queue statistics
        """
        try:
            queue = self.get_queue(queue_name)
            return {
                "name": queue_name,
                "length": len(queue),
                "is_empty": queue.is_empty(),
                "job_ids": queue.job_ids,
                "started_job_registry_length": len(queue.started_job_registry),
                "finished_job_registry_length": len(queue.finished_job_registry),
                "failed_job_registry_length": len(queue.failed_job_registry),
            }
        except Exception as e:
            LOGGER.error(f"Failed to get queue info for {queue_name}: {e}")
            return {"error": str(e)}
    
    def clear_queue(self, queue_name: str) -> int:
        """
        Clear all jobs from a specific queue.
        
        Args:
            queue_name: Name of the queue to clear
            
        Returns:
            Number of jobs that were cleared
        """
        try:
            queue = self.get_queue(queue_name)
            job_count = len(queue)
            queue.empty()
            LOGGER.info(f"Cleared {job_count} jobs from queue: {queue_name}")
            return job_count
        except Exception as e:
            LOGGER.error(f"Failed to clear queue {queue_name}: {e}")
            raise
    
    def close(self):
        """
        Close the Redis connection and clean up resources.
        """
        if self._connection:
            try:
                self._connection.close()
                LOGGER.info("Closed Redis connection")
            except Exception as e:
                LOGGER.warning(f"Error closing Redis connection: {e}")
            finally:
                self._connection = None
                self._queues.clear()


# Global connection manager instance
_connection_manager: Optional[RedisConnectionManager] = None


def get_redis_connection() -> redis.Redis:
    """
    Get the global Redis connection.
    
    Returns:
        Redis connection instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = RedisConnectionManager()
    return _connection_manager.connection


def get_queue(queue_name: str) -> Queue:
    """
    Get an RQ queue by name using the global connection manager.
    
    Args:
        queue_name: Name of the queue to retrieve
        
    Returns:
        RQ Queue instance
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = RedisConnectionManager()
    return _connection_manager.get_queue(queue_name)


def health_check() -> bool:
    """
    Perform a health check on the global Redis connection.
    
    Returns:
        True if Redis is healthy, False otherwise
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = RedisConnectionManager()
    return _connection_manager.health_check()


# Queue names used by the service
PDF_QUEUE = "pdf_queue"  # Primary queue for direct RQ communication with extralit-server
EXTRACTION_QUEUE = "extraction"  # Legacy queue for FastAPI endpoints
CHUNKING_QUEUE = "chunking"
EMBEDDING_QUEUE = "embedding"
HIGH_PRIORITY_QUEUE = "high_priority"
LOW_PRIORITY_QUEUE = "low_priority"

# Default queue configuration - pdf_queue is primary
DEFAULT_QUEUES = [PDF_QUEUE, HIGH_PRIORITY_QUEUE, EXTRACTION_QUEUE, LOW_PRIORITY_QUEUE, CHUNKING_QUEUE, EMBEDDING_QUEUE]


def get_queue_by_priority(priority: str) -> Queue:
    """
    Get the appropriate queue based on priority level.

    Args:
        priority: Priority level ("high", "normal", "low")

    Returns:
        Queue object for the specified priority

    Raises:
        ValueError: If priority is not recognized
    """
    priority_lower = priority.lower()

    if priority_lower == "high":
        return get_queue(HIGH_PRIORITY_QUEUE)
    elif priority_lower == "normal":
        return get_queue(PDF_QUEUE)  # Use pdf_queue as default for direct RQ communication
    elif priority_lower == "low":
        return get_queue(LOW_PRIORITY_QUEUE)
    else:
        raise ValueError(f"Unknown priority level: {priority}. Must be 'high', 'normal', or 'low'")
