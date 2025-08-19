"""
Configuration management for the PDF extraction service.

This module centralizes all configuration settings for both HTTP endpoints
and RQ workers, supporting environment-based configuration with sensible defaults.
It follows the twelve-factor app methodology for configuration management.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RedisConfig:
    """Configuration for Redis connection and RQ queues."""

    url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    max_connections: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))
    socket_timeout: int = int(os.getenv("REDIS_SOCKET_TIMEOUT", "5"))
    socket_connect_timeout: int = int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5"))
    health_check_interval: int = int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))


@dataclass
class QueueConfig:
    """Configuration for RQ queue behavior."""

    default_timeout: int = int(os.getenv("RQ_DEFAULT_TIMEOUT", "600"))  # 10 minutes
    result_ttl: int = int(os.getenv("RQ_RESULT_TTL", "3600"))  # 1 hour
    failure_ttl: int = int(os.getenv("RQ_FAILURE_TTL", "86400"))  # 24 hours
    job_timeout: int = int(os.getenv("RQ_JOB_TIMEOUT", "600"))  # 10 minutes

    # Queue names
    extraction_queue: str = os.getenv("RQ_EXTRACTION_QUEUE", "extraction")
    chunking_queue: str = os.getenv("RQ_CHUNKING_QUEUE", "chunking")
    embedding_queue: str = os.getenv("RQ_EMBEDDING_QUEUE", "embedding")

    @property
    def all_queues(self) -> list[str]:
        """Get list of all configured queue names."""
        return [self.extraction_queue, self.chunking_queue, self.embedding_queue]


@dataclass
class WorkerConfig:
    """Configuration for RQ worker processes."""

    # Worker behavior
    worker_name: Optional[str] = os.getenv("RQ_WORKER_NAME")
    worker_ttl: int = int(os.getenv("RQ_WORKER_TTL", "420"))  # 7 minutes
    job_monitoring_interval: int = int(os.getenv("RQ_JOB_MONITORING_INTERVAL", "30"))

    # Queues to listen on
    queues: list[str] = field(default_factory=lambda: os.getenv("RQ_QUEUES", "extraction,chunking").split(","))

    # Logging
    log_level: str = os.getenv("RQ_LOG_LEVEL", "INFO")
    log_format: str = os.getenv("RQ_LOG_FORMAT", "%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Performance tuning
    max_jobs: Optional[int] = int(os.getenv("RQ_MAX_JOBS", "0")) or None
    max_idle_time: Optional[int] = int(os.getenv("RQ_MAX_IDLE_TIME", "0")) or None


@dataclass
class ExtractionConfig:
    """Configuration for PDF extraction behavior."""

    # File handling
    max_file_size: int = int(os.getenv("PDF_MAX_FILE_SIZE", "100")) * 1024 * 1024  # 100MB default
    allowed_content_types: list[str] = field(
        default_factory=lambda: os.getenv("PDF_ALLOWED_CONTENT_TYPES", "application/pdf").split(",")
    )

    # Extraction settings
    default_margins: tuple = (
        int(os.getenv("PDF_MARGIN_LEFT", "0")),
        int(os.getenv("PDF_MARGIN_TOP", "50")),
        int(os.getenv("PDF_MARGIN_RIGHT", "0")),
        int(os.getenv("PDF_MARGIN_BOTTOM", "30")),
    )

    header_detection_max_levels: int = int(os.getenv("PDF_HEADER_MAX_LEVELS", "4"))
    header_detection_body_limit: int = int(os.getenv("PDF_HEADER_BODY_LIMIT", "10"))

    # Output settings
    write_markdown_files: bool = os.getenv("PDF_WRITE_MARKDOWN", "false").lower() == "true"
    markdown_output_dir: Optional[str] = os.getenv("PDF_MARKDOWN_OUTPUT_DIR")
    markdown_write_mode: str = os.getenv("PDF_MARKDOWN_WRITE_MODE", "overwrite")  # or "skip"


@dataclass
class APIConfig:
    """Configuration for FastAPI application."""

    # Server settings
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "7860"))
    debug: bool = os.getenv("API_DEBUG", "false").lower() == "true"

    # API behavior
    docs_url: Optional[str] = (
        os.getenv("API_DOCS_URL", "/docs") if os.getenv("API_ENABLE_DOCS", "false").lower() == "true" else None
    )
    redoc_url: Optional[str] = (
        os.getenv("API_REDOC_URL", "/redoc") if os.getenv("API_ENABLE_DOCS", "false").lower() == "true" else None
    )
    openapi_url: Optional[str] = os.getenv("API_OPENAPI_URL", "/openapi.json")

    # CORS settings
    cors_origins: list[str] = field(
        default_factory=lambda: os.getenv("API_CORS_ORIGINS", "http://localhost,http://127.0.0.1").split(",")
    )
    cors_methods: list[str] = field(default_factory=lambda: os.getenv("API_CORS_METHODS", "GET,POST").split(","))

    # Request limits
    max_request_size: int = int(os.getenv("API_MAX_REQUEST_SIZE", "100")) * 1024 * 1024  # 100MB
    request_timeout: int = int(os.getenv("API_REQUEST_TIMEOUT", "300"))  # 5 minutes


@dataclass
class LoggingConfig:
    """Configuration for application logging."""

    level: str = os.getenv("LOG_LEVEL", "INFO")
    format: str = os.getenv("LOG_FORMAT", "%(asctime)s %(levelname)s %(name)s: %(message)s")

    # Enable debug logging for PDF processing
    pdf_debug: bool = os.getenv("PDF_ENABLE_LOG_DEBUG", "0") == "1"

    # Log file settings (optional)
    log_file: Optional[str] = os.getenv("LOG_FILE")
    log_rotation: bool = os.getenv("LOG_ROTATION", "true").lower() == "true"
    log_max_size: str = os.getenv("LOG_MAX_SIZE", "10MB")
    log_backup_count: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))


@dataclass
class ServiceConfig:
    """Main configuration container for the entire service."""

    redis: RedisConfig
    queue: QueueConfig
    worker: WorkerConfig
    extraction: ExtractionConfig
    api: APIConfig
    logging: LoggingConfig

    # Service metadata
    service_name: str = os.getenv("SERVICE_NAME", "extralit-pdf-extraction")
    service_version: str = os.getenv("SERVICE_VERSION", "0.1.0")
    environment: str = os.getenv("ENVIRONMENT", "development")

    @classmethod
    def from_environment(cls) -> ServiceConfig:
        """
        Create a ServiceConfig instance from environment variables.

        Returns:
            ServiceConfig with all settings loaded from environment
        """
        return cls(
            redis=RedisConfig(),
            queue=QueueConfig(),
            worker=WorkerConfig(),
            extraction=ExtractionConfig(),
            api=APIConfig(),
            logging=LoggingConfig(),
        )

    def validate(self) -> None:
        """
        Validate the configuration settings.

        Raises:
            ValueError: If any configuration values are invalid
        """
        # Validate Redis URL format
        if not self.redis.url.startswith(("redis://", "rediss://")):
            raise ValueError(f"Invalid Redis URL format: {self.redis.url}")

        # Validate queue names are not empty
        if not all(self.queue.all_queues):
            raise ValueError("Queue names cannot be empty")

        # Validate file size limits
        if self.extraction.max_file_size <= 0:
            raise ValueError("Max file size must be positive")

        # Validate timeout values
        if self.queue.default_timeout <= 0:
            raise ValueError("Queue timeout must be positive")

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level.upper() not in valid_log_levels:
            raise ValueError(f"Invalid log level: {self.logging.level}")


# Global configuration instance
_config: Optional[ServiceConfig] = None


def get_config() -> ServiceConfig:
    """
    Get the global service configuration.

    Returns:
        ServiceConfig instance loaded from environment variables
    """
    global _config
    if _config is None:
        _config = ServiceConfig.from_environment()
        _config.validate()
    return _config


def reload_config() -> ServiceConfig:
    """
    Reload configuration from environment variables.

    Returns:
        New ServiceConfig instance
    """
    global _config
    _config = ServiceConfig.from_environment()
    _config.validate()
    return _config
