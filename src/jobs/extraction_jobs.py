"""
RQ job implementations for PDF extraction using PyMuPDF.

This module contains the actual job functions that are executed by RQ workers.
Following the rq_pymupdf reference implementation pattern for clean separation
between Apache 2.0 orchestration code and AGPL 3.0 PyMuPDF processing code.
"""

import os
import time
import tempfile
from typing import Dict, Any, Optional, Tuple

# Import the existing extraction logic (AGPL code)
from ..extract import extract_markdown_with_hierarchy, ExtractionConfig


def extract_pdf_markdown_job(
    pdf_bytes: bytes,
    filename: str,
    analysis_metadata: Optional[Dict[str, Any]] = None,
    extraction_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    RQ job for extracting hierarchical markdown from a PDF.

    This is the primary job function for PDF extraction. It takes PDF bytes
    and returns structured markdown with comprehensive metadata.

    Args:
        pdf_bytes: Raw PDF file bytes
        filename: Original filename of the PDF
        analysis_metadata: Optional metadata from extralit-server preprocessing
        extraction_config: Optional configuration overrides for extraction

    Returns:
        Dictionary containing extraction results and metadata
    """
    job_start_time = time.time()

    try:
        # Validate input
        if not pdf_bytes:
            return {
                "ok": False,
                "error": "Empty PDF content provided",
                "filename": filename,
                "processing_time": time.time() - job_start_time
            }

        if not filename:
            filename = "document.pdf"

        # Convert extraction config dict to ExtractionConfig if provided
        config = None
        if extraction_config:
            try:
                config = ExtractionConfig(**extraction_config)
            except Exception as e:
                # Log warning but continue with defaults
                config = None

        # Extract markdown using existing logic
        markdown, metadata = extract_markdown_with_hierarchy(
            pdf_bytes, filename, config=config
        )

        # Calculate total processing time
        total_processing_time = time.time() - job_start_time

        # Enhance metadata with job information
        enhanced_metadata = {
            "filename": filename,
            "processing_time": total_processing_time,
            **metadata  # Include all extraction metadata
        }

        # Add analysis metadata if provided
        if analysis_metadata:
            enhanced_metadata["analysis_results"] = analysis_metadata

        # Return result following rq_pymupdf pattern
        return {
            "ok": True,
            "markdown": markdown,
            "metadata": enhanced_metadata,
            "filename": filename,
            "processing_time": total_processing_time
        }

    except Exception as e:
        # Handle any errors
        return {
            "ok": False,
            "error": str(e),
            "filename": filename,
            "processing_time": time.time() - job_start_time
        }


def extract_pdf_with_config_job(
    pdf_bytes: bytes,
    filename: str,
    margins: Optional[Tuple[int, int, int, int]] = None,
    header_max_levels: Optional[int] = None,
    header_body_limit: Optional[int] = None,
    write_markdown: bool = False,
    output_dir: Optional[str] = None,
    analysis_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    RQ job for PDF extraction with detailed configuration options.

    This job provides more granular control over extraction parameters
    compared to the basic extraction job.
    """
    # Build extraction config from parameters
    config_dict = {}

    if margins:
        config_dict["margins"] = margins

    if header_max_levels is not None:
        config_dict["header_detection_max_levels"] = header_max_levels

    if header_body_limit is not None:
        config_dict["header_detection_body_limit"] = header_body_limit

    if write_markdown and output_dir:
        config_dict["write_dir"] = output_dir
        config_dict["write_mode"] = "overwrite"

    # Use the main extraction job with custom config
    return extract_pdf_markdown_job(
        pdf_bytes=pdf_bytes,
        filename=filename,
        analysis_metadata=analysis_metadata,
        extraction_config=config_dict
    )
