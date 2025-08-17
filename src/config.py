"""
Configuration management for the Extralit HF-Space microservice.

This module provides centralized configuration for both the FastAPI web server
and the RQ worker processes. It uses environment variables for configuration
with sensible defaults for development.
"""

import os
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings


class RQConfig(BaseSettings):
    """
    Configuration for Redis Queue (RQ) worker and job processing.

    All settings can be overridden via environment variables with the RQ_ prefix.
    """

    class Config:
        env_prefix = "RQ_"

    # Redis connection settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL for RQ"
    )

    # Queue configuration
    queues: List[str] = Field(
        default=["extraction", "chunking"],
        description="List of queue names to process"
    )

    # Job settings
    default_job_timeout: int = Field(
        default=600,  # 10 minutes
        description="Default job timeout in seconds"
    )

    result_ttl: int = Field(
        default=3600,  # 1 hour
        description="How long to keep job results in Redis (seconds)"
    )

    failure_ttl: int = Field(
        default=86400,  # 24 hours
        description="How long to keep failed job info in Redis (seconds)"
    )


class ServiceConfig(BaseSettings):
    """
    General service configuration for the FastAPI application.
    """

    # Service settings
    host: str = Field(default="0.0.0.0", description="Host to bind the service")
    port: int = Field(default=7860, description="Port to bind the service")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    enable_debug_logs: bool = Field(
        default=False,
        description="Enable debug logging for PDF processing"
    )


# Global configuration instances
rq_config = RQConfig()
service_config = ServiceConfig()


def get_rq_config() -> RQConfig:
    """Get the global RQ configuration instance."""
    return rq_config


def get_service_config() -> ServiceConfig:
    """Get the global service configuration instance."""
    return service_config