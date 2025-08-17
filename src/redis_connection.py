"""
Redis connection management for RQ workers and job processing.

This module provides centralized Redis connection management with proper
error handling and connection pooling for the RQ-based job processing system.
"""

import logging
import redis
from rq import Queue
from typing import Dict, Optional
from .config import get_rq_config

logger = logging.getLogger(__name__)


class RedisConnectionManager:
    """
    Manages Redis connections and RQ queues for the extraction service.
    
    This class provides a centralized way to manage Redis connections and
    RQ queues, ensuring proper connection pooling and error handling.
    """
    
    def __init__(self):
        self.config = get_rq_config()
        self._redis_connection: Optional[redis.Redis] = None
        self._queues: Dict[str, Queue] = {}
    
    @property
    def redis_connection(self) -> redis.Redis:
        """
        Get or create a Redis connection.
        
        Returns:
            redis.Redis: Active Redis connection
            
        Raises:
            redis.ConnectionError: If unable to connect to Redis
        """
        if self._redis_connection is None:
            try:
                self._redis_connection = redis.from_url(
                    self.config.redis_url,
                    decode_responses=False,  # Keep binary data as bytes for PDF processing
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
                # Test the connection
                self._redis_connection.ping()
                logger.info(f"Connected to Redis at {self.config.redis_url}")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise redis.ConnectionError(f"Cannot connect to Redis: {e}")
        
        return self._redis_connection
    
    def get_queue(self, queue_name: str) -> Queue:
        """
        Get or create an RQ queue.
        
        Args:
            queue_name: Name of the queue to get/create
            
        Returns:
            Queue: RQ Queue instance
        """
        if queue_name not in self._queues:
            self._queues[queue_name] = Queue(
                queue_name,
                connection=self.redis_connection,
                default_timeout=self.config.default_job_timeout
            )
            logger.debug(f"Created queue: {queue_name}")
        
        return self._queues[queue_name]
    
    def get_all_configured_queues(self) -> Dict[str, Queue]:
        """
        Get all queues configured in the RQ config.
        
        Returns:
            Dict[str, Queue]: Dictionary mapping queue names to Queue instances
        """
        queues = {}
        for queue_name in self.config.queues:
            queues[queue_name] = self.get_queue(queue_name)
        return queues
    
    def health_check(self) -> bool:
        """
        Check if Redis connection is healthy.
        
        Returns:
            bool: True if Redis is accessible, False otherwise
        """
        try:
            self.redis_connection.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False
    
    def close(self):
        """Close Redis connection and clean up resources."""
        if self._redis_connection:
            try:
                self._redis_connection.close()
                logger.info("Redis connection closed")
            except Exception as e:
                logger.warning(f"Error closing Redis connection: {e}")
            finally:
                self._redis_connection = None
                self._queues.clear()


# Global connection manager instance
_connection_manager: Optional[RedisConnectionManager] = None


def get_redis_connection_manager() -> RedisConnectionManager:
    """
    Get the global Redis connection manager instance.
    
    Returns:
        RedisConnectionManager: Global connection manager
    """
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = RedisConnectionManager()
    return _connection_manager


def get_redis_connection() -> redis.Redis:
    """
    Get a Redis connection using the global connection manager.
    
    Returns:
        redis.Redis: Active Redis connection
    """
    return get_redis_connection_manager().redis_connection


def get_queue(queue_name: str) -> Queue:
    """
    Get an RQ queue using the global connection manager.
    
    Args:
        queue_name: Name of the queue
        
    Returns:
        Queue: RQ Queue instance
    """
    return get_redis_connection_manager().get_queue(queue_name)
