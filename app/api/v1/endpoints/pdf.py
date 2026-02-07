"""PDF processing endpoints."""

import traceback

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.core.config import settings
from app.core.logging import logger
from app.services.pdf_service import pdf_service
from app.services.summarization_service import summarization_service

router = APIRouter()


@router.post("/extract")
async def extract_text_from_pdf(file: UploadFile = File(...)):
    """
    Upload a PDF file and extract text from it.

    - Extracts all text from the PDF
    - Cleans up the extracted text
    - Saves the cleaned text to a file
    - Returns the file path and text preview
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF files are accepted.",
        )

    # Validate content type
    if file.content_type not in ["application/pdf", "application/octet-stream"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type: {file.content_type}. Expected application/pdf.",
        )

    try:
        # Read file content
        content = await file.read()

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        logger.info(f"Processing PDF: {file.filename} ({len(content)} bytes)")

        # Process PDF
        result = pdf_service.process_pdf(content, file.filename)

        logger.info(f"PDF processed successfully: {result['output_path']}")

        return {
            "success": True,
            "message": "PDF processed successfully",
            "data": result,
        }

    except HTTPException:
        raise

    except Exception as e:
        # Log detailed error to console
        logger.error(f"PDF processing failed for '{file.filename}': {e}")
        if settings.DEBUG:
            logger.error(f"Traceback:\n{traceback.format_exc()}")

        raise HTTPException(
            status_code=500,
            detail="Error processing PDF. Check server logs for details.",
        )


@router.post("/summarize")
async def summarize_pdf(
    file: UploadFile = File(...),
    platform: str = Query(
        default=None,
        description="LLM platform to use: 'groq' or 'openrouter'. Defaults to server config.",
    ),
):
    """
    Upload a PDF file and get an AI-generated summary.

    - Extracts text from the PDF
    - Cleans the extracted text
    - Sends it to the chosen LLM platform for summarization
    - Returns the summary

    **Platforms**: `groq` (default), `openrouter`
    """
    # Validate file type
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only PDF files are accepted.",
        )

    if file.content_type not in ["application/pdf", "application/octet-stream"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content type: {file.content_type}. Expected application/pdf.",
        )

    try:
        content = await file.read()

        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded.")

        logger.info(f"Summarizing PDF: {file.filename} ({len(content)} bytes)")

        # Step 1: Extract and clean text
        raw_text = pdf_service.extract_text_from_pdf(content)
        cleaned_text = pdf_service.cleanup_text(raw_text)

        if not cleaned_text.strip():
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from this PDF.",
            )

        logger.info(f"Extracted {len(cleaned_text)} chars, sending to LLM...")

        # Step 2: Summarize via chosen platform
        result = await summarization_service.summarize(cleaned_text, platform=platform)

        logger.info("PDF summarized successfully")

        return {
            "success": True,
            "message": "PDF summarized successfully",
            "data": {
                "filename": file.filename,
                "original_text_length": len(cleaned_text),
                "word_count": len(cleaned_text.split()),
                **result,
            },
        }

    except HTTPException:
        raise

    except ValueError as e:
        # Missing API key
        raise HTTPException(status_code=500, detail=str(e))

    except Exception as e:
        logger.error(f"PDF summarization failed for '{file.filename}': {e}")
        if settings.DEBUG:
            logger.error(f"Traceback:\n{traceback.format_exc()}")

        raise HTTPException(
            status_code=500,
            detail="Error summarizing PDF. Check server logs for details.",
        )

