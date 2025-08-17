"""
RQ job definitions for PDF extraction and processing.

This module contains job functions that can be executed by RQ workers to process
PDF documents. These jobs are designed to be called from the Extralit server
and provide asynchronous PDF processing capabilities.

Key principles:
- Jobs are stateless and can be retried safely
- All job parameters are serializable (no complex objects)
- Jobs return structured data that can be easily consumed
- Error handling is comprehensive with meaningful error messages
"""

import logging
import time
from typing import Dict, Any, Optional
from ..extract import extract_markdown_with_hierarchy, ExtractionConfig

logger = logging.getLogger(__name__)


def extract_pdf_markdown_job(
    pdf_bytes: bytes,
    filename: str,
    config_dict: Optional[Dict[str, Any]] = None,
    analysis_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    RQ job for extracting hierarchical markdown from PDF bytes.

    This job wraps the existing extract_markdown_with_hierarchy function
    to make it compatible with RQ job processing. It handles all the
    serialization and error handling needed for reliable job execution.

    Args:
        pdf_bytes: Raw PDF file data as bytes
        filename: Original filename (used for logging and output naming)
        config_dict: Optional extraction configuration as dictionary
        analysis_metadata: Optional preprocessing metadata from extralit-server

    Returns:
        Dict containing:
        - success: bool indicating if extraction succeeded
        - markdown: str with extracted markdown content (if successful)
        - metadata: dict with extraction metadata
        - filename: str original filename
        - processing_time: float time taken for extraction
        - error: str error message (if failed)

    Raises:
        ValueError: If input parameters are invalid
        Exception: For unexpected errors during processing
    """
    start_time = time.time()

    try:
        # Validate inputs
        if not pdf_bytes:
            raise ValueError("PDF bytes cannot be empty")

        if not filename:
            raise ValueError("Filename cannot be empty")

        logger.info(f"Starting PDF extraction job for {filename} ({len(pdf_bytes)} bytes)")

        # Convert config dict to ExtractionConfig if provided
        config = None
        if config_dict:
            try:
                config = ExtractionConfig(**config_dict)
                logger.debug(f"Using custom extraction config: {config_dict}")
            except Exception as e:
                logger.warning(f"Invalid config dict, using defaults: {e}")
                config = None

        # Extract markdown using existing logic
        markdown, metadata = extract_markdown_with_hierarchy(
            pdf_bytes, filename, config=config
        )

        # Add analysis metadata if provided
        if analysis_metadata:
            metadata["analysis_results"] = analysis_metadata
            logger.debug("Added analysis metadata to extraction results")

        processing_time = time.time() - start_time

        result = {
            "success": True,
            "markdown": markdown,
            "metadata": metadata,
            "filename": filename,
            "processing_time": processing_time
        }

        logger.info(
            f"Successfully extracted {len(markdown)} characters from {filename} "
            f"in {processing_time:.2f}s"
        )

        return result

    except ValueError as ve:
        # Input validation errors
        processing_time = time.time() - start_time
        error_msg = f"Invalid input for {filename}: {str(ve)}"
        logger.error(error_msg)

        return {
            "success": False,
            "error": error_msg,
            "filename": filename,
            "processing_time": processing_time
        }

    except Exception as e:
        # Unexpected errors
        processing_time = time.time() - start_time
        error_msg = f"Extraction failed for {filename}: {str(e)}"
        logger.exception(error_msg)

        return {
            "success": False,
            "error": error_msg,
            "filename": filename,
            "processing_time": processing_time
        }


def extract_pdf_with_chunking_job(
    pdf_bytes: bytes,
    filename: str,
    chunk_strategy: str = "header",
    chunk_size: int = 1024,
    chunk_overlap: int = 128,
    config_dict: Optional[Dict[str, Any]] = None,
    analysis_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    RQ job for extracting markdown and creating chunks in one operation.

    This job combines PDF extraction with text chunking to provide a complete
    processing pipeline. It's useful when you want both the full markdown
    and pre-chunked text for embedding generation.

    Args:
        pdf_bytes: Raw PDF file data as bytes
        filename: Original filename
        chunk_strategy: Chunking strategy ("header" or "token")
        chunk_size: Size of chunks in characters (for token strategy)
        chunk_overlap: Overlap between chunks in characters
        config_dict: Optional extraction configuration
        analysis_metadata: Optional preprocessing metadata

    Returns:
        Dict containing:
        - success: bool indicating if processing succeeded
        - markdown: str full extracted markdown
        - chunks: list of chunk dictionaries with text and metadata
        - metadata: dict extraction metadata
        - filename: str original filename
        - processing_time: float total processing time
        - error: str error message (if failed)
    """
    start_time = time.time()

    try:
        # First, extract the markdown using the existing job
        extraction_result = extract_pdf_markdown_job(
            pdf_bytes=pdf_bytes,
            filename=filename,
            config_dict=config_dict,
            analysis_metadata=analysis_metadata
        )

        if not extraction_result["success"]:
            # If extraction failed, return the error
            return extraction_result

        markdown = extraction_result["markdown"]
        metadata = extraction_result["metadata"]

        # Now chunk the markdown
        chunks = []
        if chunk_strategy == "header":
            chunks = _chunk_by_headers(markdown, filename)
        elif chunk_strategy == "token":
            chunks = _chunk_by_tokens(markdown, chunk_size, chunk_overlap, filename)
        else:
            raise ValueError(f"Unknown chunk strategy: {chunk_strategy}")

        processing_time = time.time() - start_time

        result = {
            "success": True,
            "markdown": markdown,
            "chunks": chunks,
            "metadata": metadata,
            "filename": filename,
            "processing_time": processing_time,
            "chunk_strategy": chunk_strategy,
            "total_chunks": len(chunks)
        }

        logger.info(
            f"Successfully extracted and chunked {filename}: "
            f"{len(markdown)} chars -> {len(chunks)} chunks in {processing_time:.2f}s"
        )

        return result

    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = f"Extraction with chunking failed for {filename}: {str(e)}"
        logger.exception(error_msg)

        return {
            "success": False,
            "error": error_msg,
            "filename": filename,
            "processing_time": processing_time
        }


def _chunk_by_headers(markdown: str, filename: str, min_length: int = 100) -> list:
    """
    Chunk markdown text by headers, creating semantic sections.

    This function splits markdown into chunks based on header boundaries,
    ensuring each chunk represents a logical section of the document.

    Args:
        markdown: The markdown text to chunk
        filename: Original filename for metadata
        min_length: Minimum chunk length in characters

    Returns:
        List of chunk dictionaries with text and metadata
    """
    import re

    lines = markdown.splitlines()
    chunks = []
    current_chunk = []
    current_header = None
    start_line = 0

    for i, line in enumerate(lines):
        # Check if line is a header (starts with #)
        header_match = re.match(r"^(#+)\s+(.+)", line)

        if header_match:
            # Save previous chunk if it exists and meets minimum length
            if current_chunk:
                text = "\n".join(current_chunk).strip()
                if len(text) >= min_length:
                    chunks.append({
                        "text": text,
                        "metadata": {
                            "header": current_header,
                            "start_line": start_line,
                            "end_line": i - 1,
                            "filename": filename,
                            "chunk_type": "header_based",
                            "header_level": len(header_match.group(1)) if current_header else None
                        }
                    })

            # Start new chunk
            current_chunk = [line]
            current_header = header_match.group(2)
            start_line = i
        else:
            current_chunk.append(line)

    # Add final chunk if it exists
    if current_chunk:
        text = "\n".join(current_chunk).strip()
        if len(text) >= min_length:
            chunks.append({
                "text": text,
                "metadata": {
                    "header": current_header,
                    "start_line": start_line,
                    "end_line": len(lines) - 1,
                    "filename": filename,
                    "chunk_type": "header_based",
                    "header_level": None
                }
            })

    return chunks


def _chunk_by_tokens(
    markdown: str,
    chunk_size: int,
    chunk_overlap: int,
    filename: str
) -> list:
    """
    Chunk markdown text by token/character count with overlap.

    This function creates fixed-size chunks with configurable overlap,
    useful for consistent chunk sizes for embedding models.

    Args:
        markdown: The markdown text to chunk
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        filename: Original filename for metadata

    Returns:
        List of chunk dictionaries with text and metadata
    """
    if chunk_size <= chunk_overlap:
        raise ValueError("Chunk size must be greater than chunk overlap")

    chunks = []
    text = markdown.strip()
    start = 0
    chunk_index = 0

    while start < len(text):
        # Calculate end position
        end = start + chunk_size

        # If this isn't the last chunk, try to break at a word boundary
        if end < len(text):
            # Look for the last space within the chunk to avoid breaking words
            last_space = text.rfind(' ', start, end)
            if last_space > start:
                end = last_space

        chunk_text = text[start:end].strip()

        if chunk_text:  # Only add non-empty chunks
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "start_char": start,
                    "end_char": end,
                    "chunk_index": chunk_index,
                    "filename": filename,
                    "chunk_type": "token_based",
                    "chunk_size": len(chunk_text)
                }
            })
            chunk_index += 1

        # Move start position for next chunk (with overlap)
        start = end - chunk_overlap

        # Ensure we make progress even with small chunks
        if start <= 0:
            start = end

    return chunks