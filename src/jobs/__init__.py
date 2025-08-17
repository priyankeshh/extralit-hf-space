"""
RQ job definitions for PDF extraction and processing.

This package contains all background job implementations for the PDF extraction service.
Jobs are designed to be framework-agnostic and can be executed by RQ workers or
called directly for testing purposes.

Following the rq_pymupdf reference implementation pattern for clean separation
between Apache 2.0 licensed orchestration code and AGPL 3.0 licensed PyMuPDF processing code.
"""

# Import job functions to make them available to RQ workers
from .extraction_jobs import (
    extract_pdf_markdown_job,
    extract_pdf_with_config_job
)

__all__ = [
    "extract_pdf_markdown_job",
    "extract_pdf_with_config_job"
]
