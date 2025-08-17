from __future__ import annotations

import io
import os
import time
import json
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple, List

import pymupdf4llm
from fastapi import FastAPI, UploadFile, HTTPException, Request, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse
from rq.job import Job

from .extract import extract_markdown_with_hierarchy
from .schemas import ExtractionResponse, PDFMetadata, ErrorResponse, JobStatusResponse, ExtractionJobResponse
from .redis_connection import get_queue, get_queue_by_priority, EXTRACTION_QUEUE, health_check
from .config import get_config


config = get_config()

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.logging.level.upper()),
    format=config.logging.format
)
LOGGER = logging.getLogger("pdf-markdown-service")

app = FastAPI(
    title="Extralit PDF Markdown Extraction Service",
    version=config.service_version,
    docs_url=config.api.docs_url,
    redoc_url=config.api.redoc_url,
    openapi_url=config.api.openapi_url,
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=False,
    allow_methods=config.api.cors_methods,
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


@app.post("/jobs/extract", response_model=ExtractionJobResponse)
async def enqueue_extraction_job(
    pdf: UploadFile,
    analysis_metadata: Optional[str] = Form(None, description="JSON string of analysis metadata"),
    extraction_config: Optional[str] = Form(None, description="JSON string of extraction configuration"),
    priority: str = Form("normal", description="Job priority (low, normal, high)")
) -> ExtractionJobResponse:
    """
    Enqueue a PDF extraction job for background processing.

    Args:
        pdf: The PDF file to extract from
        analysis_metadata: Optional JSON string containing analysis metadata
        extraction_config: Optional JSON string containing extraction configuration
        priority: Job priority level

    Returns:
        ExtractionJobResponse with job ID and status
    """
    if not pdf.filename or not pdf.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Read PDF bytes
        pdf_bytes = await pdf.read()
        if not pdf_bytes:
            raise HTTPException(status_code=400, detail="Empty file uploaded")

        # Parse metadata and config if provided
        parsed_analysis_metadata = None
        if analysis_metadata:
            try:
                parsed_analysis_metadata = json.loads(analysis_metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in analysis_metadata")

        parsed_extraction_config = None
        if extraction_config:
            try:
                parsed_extraction_config = json.loads(extraction_config)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid JSON in extraction_config")

        # Get the extraction queue
        queue = get_queue(EXTRACTION_QUEUE)

        # Enqueue the job
        job = queue.enqueue(
            "src.jobs.extraction_jobs.extract_pdf_markdown_job",
            pdf_bytes=pdf_bytes,
            filename=pdf.filename or "document.pdf",
            analysis_metadata=parsed_analysis_metadata,
            extraction_config=parsed_extraction_config,
            job_timeout=config.queue.job_timeout,
            result_ttl=config.queue.result_ttl,
            failure_ttl=config.queue.failure_ttl,
            description=f"extract_pdf:{pdf.filename or 'document.pdf'}"
        )

        LOGGER.info(f"Enqueued extraction job {job.get_id()} for {pdf.filename}")

        return ExtractionJobResponse(
            job_id=job.get_id(),
            status=job.get_status(),
            queue_name=EXTRACTION_QUEUE,
            estimated_start_time=None  # Could be calculated based on queue length
        )

    except Exception as e:
        LOGGER.exception(f"Failed to enqueue extraction job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {e}")


@app.post("/jobs/batch-extract", response_model=ExtractionJobResponse)
async def enqueue_batch_extraction_job(
    files: List[UploadFile],
    analysis_metadata: Optional[str] = Form(None, description="JSON string of analysis metadata"),
    extraction_config: Optional[str] = Form(None, description="JSON string of extraction configuration"),
    priority: str = Form("normal", description="Job priority (low, normal, high)")
) -> ExtractionJobResponse:
    """
    Enqueue a batch PDF extraction job for multiple files.

    This endpoint allows processing multiple PDF files in a single batch job,
    which can be more efficient for related documents or small files.
    """
    try:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")

        # Validate all files are PDFs
        pdf_files = []
        for file in files:
            if not file.filename or not file.filename.lower().endswith('.pdf'):
                raise HTTPException(status_code=400, detail=f"File {file.filename} is not a PDF")

            pdf_bytes = await file.read()
            if not pdf_bytes:
                raise HTTPException(status_code=400, detail=f"File {file.filename} is empty")

            pdf_files.append((pdf_bytes, file.filename))

        # Parse optional metadata
        parsed_analysis_metadata = None
        if analysis_metadata:
            try:
                parsed_analysis_metadata = json.loads(analysis_metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid analysis_metadata JSON")

        parsed_extraction_config = None
        if extraction_config:
            try:
                parsed_extraction_config = json.loads(extraction_config)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid extraction_config JSON")

        # Generate batch ID
        import uuid
        batch_id = str(uuid.uuid4())

        # Get appropriate queue based on priority
        queue = get_queue_by_priority(priority)

        # Enqueue batch job
        job = queue.enqueue(
            "src.jobs.extraction_jobs.batch_extract_pdfs_job",
            pdf_files=pdf_files,
            batch_id=batch_id,
            analysis_metadata=parsed_analysis_metadata,
            extraction_config=parsed_extraction_config,
            job_timeout=1800,  # 30 minutes for batch jobs
            result_ttl=7200,   # Keep results for 2 hours
            failure_ttl=86400, # Keep failed jobs for 24 hours
            description=f"batch_extract:{len(pdf_files)}_files"
        )

        job_id = job.get_id()
        LOGGER.info(f"Enqueued batch extraction job {job_id} for {len(pdf_files)} files (batch_id: {batch_id})")

        return ExtractionJobResponse(
            job_id=job_id,
            status="queued",
            message=f"Batch extraction job enqueued for {len(pdf_files)} files",
            metadata={"batch_id": batch_id, "file_count": len(pdf_files)}
        )

    except HTTPException:
        raise
    except Exception as e:
        LOGGER.exception(f"Failed to enqueue batch extraction job: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enqueue batch job: {e}")


@app.get("/jobs/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Get the status of a background job.

    Args:
        job_id: The unique job identifier

    Returns:
        JobStatusResponse with current job status and results
    """
    try:
        queue = get_queue(EXTRACTION_QUEUE)
        job = Job.fetch(job_id, connection=queue.connection)

        response_data = {
            "job_id": job_id,
            "status": job.get_status(),
            "enqueued_at": job.enqueued_at.isoformat() if job.enqueued_at else None,
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "ended_at": job.ended_at.isoformat() if job.ended_at else None,
        }

        if job.is_failed:
            response_data["error"] = str(job.exc_info or "Job failed without error details")

        if job.is_finished and job.result:
            # Convert job result to ExtractionResponse if successful
            result = job.result
            if result.get("success", False):
                try:
                    pdf_metadata = PDFMetadata(**result["metadata"])
                    extraction_response = ExtractionResponse(
                        markdown=result["markdown"],
                        metadata=pdf_metadata,
                        filename=result.get("filename"),
                        processing_time=result.get("processing_time")
                    )
                    response_data["result"] = extraction_response
                except Exception as e:
                    LOGGER.warning(f"Failed to parse job result: {e}")
                    response_data["error"] = f"Failed to parse job result: {e}"
            else:
                response_data["error"] = result.get("error", "Job completed with errors")

        return JobStatusResponse(**response_data)

    except Exception as e:
        LOGGER.exception(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(status_code=404, detail=f"Job not found or error retrieving status: {e}")


@app.get("/health/redis")
async def redis_health():
    """Check Redis connection health."""
    is_healthy = health_check()
    if is_healthy:
        return {"status": "healthy", "redis": "connected"}
    else:
        raise HTTPException(status_code=503, detail="Redis connection failed")
