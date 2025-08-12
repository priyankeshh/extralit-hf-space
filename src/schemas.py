"""
Pydantic schemas for the extralit-hf-space API endpoints.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

# Import shared metadata schema from extralit-server
try:
    from extralit_server.api.schemas.v1.document.preprocessing import PDFMetadata
except ImportError:
    # Fallback for when extralit-server is not available
    class PDFMetadata(BaseModel):
        """
        Fallback metadata schema when extralit-server is not available.
        """
        filename: str
        processing_time: float
        page_count: Optional[int] = None
        language_detected: Optional[list] = None
        processing_settings: Optional[Dict] = None
        analysis_results: Optional[Dict] = None


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
    analysis_metadata: Optional[PDFMetadata] = Field(
        None,
        description="Analysis and preprocessing metadata from extralit-server"
    )
    extraction_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Custom extraction configuration parameters"
    )


class ExtractionResponse(BaseModel):
    """
    Response schema for PDF extraction endpoint.
    """
    
    markdown: str = Field(..., description="Extracted markdown content")
    metadata: PDFMetadata = Field(..., description="Extraction and processing metadata")
    filename: Optional[str] = Field(None, description="Original filename of the PDF")
    processing_time: Optional[float] = Field(None, description="Time taken for extraction in seconds")


class ErrorResponse(BaseModel):
    """
    Error response schema.
    """
    
    detail: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Specific error code for programmatic handling")
