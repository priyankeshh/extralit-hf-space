from __future__ import annotations

import io
import os
import time
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
from .schemas import ExtractionResponse, ExtractionMetadata, ErrorResponse


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
        
        # Extract markdown using pymupdf
        markdown, metadata = extract_markdown_with_hierarchy(pdf_bytes, pdf.filename or "document.pdf")
        
        # Create response metadata
        extraction_metadata = ExtractionMetadata(**metadata)
        
        processing_time = time.time() - start_time
        
        return ExtractionResponse(
            markdown=markdown,
            metadata=extraction_metadata,
            filename=pdf.filename,
            processing_time=processing_time
        )
        
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        LOGGER.exception("Unexpected extraction error")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
