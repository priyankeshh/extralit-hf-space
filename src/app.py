from __future__ import annotations

import io
import os
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple

import pymupdf4llm
from fastapi import FastAPI, UploadFile, HTTPException, Request, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from .extract import extract_markdown_with_hierarchy
from .schemas import ExtractionResponse, PDFMetadata, ErrorResponse


_LOG_LEVEL = "DEBUG" if os.getenv("PDF_ENABLE_LOG_DEBUG", "0") == "1" else "INFO"
logging.basicConfig(level=_LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
LOGGER = logging.getLogger("pdf-markdown-service")

app = FastAPI(
    title="Extralit PDF Markdown Extraction Service",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/openapi.json",  # can be disabled later if desired
)

# If you ever need CORS for cross-container scenarios (normally unnecessary for internal usage)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": "pdf-markdown"}


@app.get("/info")
async def info():
    return {
        "service": "pdf-markdown",
        "pymupdf4llm_version": getattr(pymupdf4llm, "__version__", "unknown"),
    }

@app.post("/extract", response_model=ExtractionResponse, responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}})
async def extract(
    pdf: UploadFile,
    analysis_metadata: Optional[str] = Form(None, description="JSON string of analysis metadata")
) -> ExtractionResponse:
    """
    Extract hierarchical markdown from a PDF using PyMuPDF.

    Args:
        pdf: The PDF file to extract from
        analysis_metadata: Optional JSON string containing analysis metadata from extralit-server

    Returns:
        ExtractionResponse with markdown content and metadata
    """
    if not pdf.filename or not pdf.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    start_time = time.time()

    try:
        # Read PDF bytes
        pdf_bytes = await pdf.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Parse analysis metadata if provided
        parsed_analysis_metadata = None
        if analysis_metadata:
            try:
                parsed_analysis_metadata = json.loads(analysis_metadata)
            except json.JSONDecodeError:
                LOGGER.warning("Invalid JSON in analysis_metadata, ignoring")

        # Extract markdown using pymupdf
        markdown, extraction_metadata = extract_markdown_with_hierarchy(pdf_bytes, pdf.filename or "document.pdf")

        processing_time = time.time() - start_time

        # Create PDFMetadata combining extraction results with analysis metadata
        metadata_dict = {
            "filename": pdf.filename or "document.pdf",
            "processing_time": processing_time,
            "page_count": extraction_metadata.get("pages"),
            **extraction_metadata  # Include all pymupdf extraction metadata
        }

        # Add analysis metadata if provided
        if parsed_analysis_metadata:
            metadata_dict["analysis_results"] = parsed_analysis_metadata

        pdf_metadata = PDFMetadata(**metadata_dict)

        return ExtractionResponse(
            markdown=markdown,
            metadata=pdf_metadata,
            filename=pdf.filename,
            processing_time=processing_time
        )

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        LOGGER.exception("Unexpected extraction error")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


# RQ Job Management Endpoints

@app.post("/jobs/extract")
async def enqueue_extraction_job(
    pdf: UploadFile,
    analysis_metadata: Optional[str] = Form(None, description="JSON string of analysis metadata"),
    config: Optional[str] = Form(None, description="JSON string of extraction configuration")
) -> dict:
    """
    Enqueue a PDF extraction job for asynchronous processing.

    Args:
        pdf: The PDF file to extract from
        analysis_metadata: Optional JSON string containing analysis metadata
        config: Optional JSON string containing extraction configuration

    Returns:
        Dict with job_id and status
    """
    try:
        from .redis_connection import get_queue
        from .jobs.extraction_jobs import extract_pdf_markdown_job

        if not pdf.filename or not pdf.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Read PDF bytes
        pdf_bytes = await pdf.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Parse optional parameters
        parsed_analysis_metadata = None
        if analysis_metadata:
            try:
                parsed_analysis_metadata = json.loads(analysis_metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in analysis_metadata")

        parsed_config = None
        if config:
            try:
                parsed_config = json.loads(config)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in config")

        # Enqueue the job
        queue = get_queue("extraction")
        job = queue.enqueue(
            extract_pdf_markdown_job,
            pdf_bytes=pdf_bytes,
            filename=pdf.filename,
            config_dict=parsed_config,
            analysis_metadata=parsed_analysis_metadata,
            job_timeout=600,  # 10 minutes
            result_ttl=3600,  # 1 hour
            failure_ttl=86400  # 24 hours
        )

        LOGGER.info(f"Enqueued extraction job {job.id} for {pdf.filename}")

        return {
            "job_id": job.id,
            "status": job.get_status(),
            "filename": pdf.filename,
            "queue": "extraction"
        }

    except Exception as e:
        LOGGER.exception("Failed to enqueue extraction job")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {str(e)}")


@app.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str) -> dict:
    """
    Get the status of a job by its ID.

    Args:
        job_id: The job ID to check

    Returns:
        Dict with job status and result (if completed)
    """
    try:
        from .redis_connection import get_redis_connection
        from rq.job import Job

        redis_conn = get_redis_connection()
        job = Job.fetch(job_id, connection=redis_conn)

        response = {
            "job_id": job_id,
            "status": job.get_status(),
            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        }

        if job.is_failed:
            response["error"] = str(job.exc_info or "Unknown error")

        if job.is_finished and job.result:
            response["result"] = job.result

        return response

    except Exception as e:
        LOGGER.exception(f"Failed to get job status for {job_id}")
        raise HTTPException(status_code=404, detail=f"Job not found: {str(e)}")


@app.get("/jobs/health")
async def jobs_health_check() -> dict:
    """
    Check the health of the RQ job system.

    Returns:
        Dict with Redis connection status and queue information
    """
    try:
        from .redis_connection import get_redis_connection_manager

        connection_manager = get_redis_connection_manager()
        redis_healthy = connection_manager.health_check()

        queues_info = {}
        if redis_healthy:
            for queue_name in ["extraction", "chunking"]:
                try:
                    queue = connection_manager.get_queue(queue_name)
                    queues_info[queue_name] = {
                        "length": len(queue),
                        "name": queue.name
                    }
                except Exception as e:
                    queues_info[queue_name] = {"error": str(e)}

        return {
            "redis_healthy": redis_healthy,
            "queues": queues_info,
            "timestamp": time.time()
        }

    except Exception as e:
        LOGGER.exception("Jobs health check failed")
        return {
            "redis_healthy": False,
            "error": str(e),
            "timestamp": time.time()
        }
