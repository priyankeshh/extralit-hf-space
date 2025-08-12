"""
Pydantic schemas for the extralit-hf-space API endpoints.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class ExtractionRequest(BaseModel):
    """
    Request schema for PDF extraction endpoint.
    
    This schema represents the metadata and configuration for PDF extraction.
    The actual PDF file is sent as a multipart upload.
    """
    
    file_url: Optional[str] = Field(
        None, 
        description="Optional URL to the PDF file if hosted externally"
    )
    analysis_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional analysis and preprocessing metadata from extralit-server"
    )
    extraction_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom extraction configuration parameters"
    )


class ExtractionMetadata(BaseModel):
    """
    Metadata returned from PDF extraction.
    """
    
    pages: int = Field(..., description="Number of pages in the PDF")
    toc_entries: int = Field(..., description="Number of table of contents entries")
    headers_strategy: str = Field(..., description="Strategy used for header detection (toc or identify)")
    header_levels_detected: Optional[int] = Field(None, description="Number of distinct header levels found")
    margins: Dict[str, int] = Field(..., description="Margins used for extraction (left, top, right, bottom)")
    output_path: Optional[str] = Field(None, description="Path where markdown was written (if configured)")
    output_size_chars: int = Field(..., description="Number of characters in extracted markdown")


class ExtractionResponse(BaseModel):
    """
    Response schema for PDF extraction endpoint.
    """
    
    markdown: str = Field(..., description="Extracted markdown content")
    metadata: ExtractionMetadata = Field(..., description="Extraction metadata")
    filename: Optional[str] = Field(None, description="Original filename of the PDF")
    processing_time: Optional[float] = Field(None, description="Time taken for extraction in seconds")


class ErrorResponse(BaseModel):
    """
    Error response schema.
    """
    
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code for programmatic handling")
