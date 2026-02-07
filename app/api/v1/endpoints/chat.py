"""Note-specific AI chat endpoint."""

import traceback
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.dependencies import get_current_user
from app.models.user import User
from app.models.note import Note
from app.services.pdf_service import pdf_service
from app.services.summarization_service import summarization_service
from app.services.storage_service import storage_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    platform: str
    model: str


def _extract_storage_path(file_url: str) -> str:
    """Extract the storage path from a Supabase public URL.

    Public URL: https://xxx.supabase.co/storage/v1/object/public/notes/ISC/BSc/CS20/uuid.pdf
    Returns:    ISC/BSc/CS20/uuid.pdf
    """
    marker = f"/object/public/{settings.SUPABASE_BUCKET}/"
    if marker in file_url:
        return file_url.split(marker, 1)[1]
    # Fallback: treat as relative path
    return file_url


async def _download_and_extract_text(storage_path: str) -> str:
    """Download a PDF from Supabase and extract its text content."""
    content = await storage_service.download(storage_path)
    raw_text = pdf_service.extract_text_from_pdf(content)
    cleaned = pdf_service.cleanup_text(raw_text)
    return cleaned


@router.post("/note/{note_id}", response_model=ChatResponse)
async def chat_about_note(
    note_id: str,
    body: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ask an AI question about a specific note.

    Downloads the PDF from Supabase Storage, extracts text, sends it as context
    along with the user's question to the LLM, and returns the answer.
    """
    # Validate note exists
    result = await db.execute(select(Note).where(Note.id == note_id))
    note = result.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    # Ensure we have a file to read
    if not note.file_url:
        raise HTTPException(status_code=400, detail="This note has no uploaded file")

    storage_path = _extract_storage_path(note.file_url)

    try:
        # Download and extract text from PDF
        doc_text = await _download_and_extract_text(storage_path)
        if not doc_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from this document.",
            )

        # Truncate to fit context window (keep first ~12k chars)
        max_context = 12000
        if len(doc_text) > max_context:
            doc_text = doc_text[:max_context] + "\n\n[... document truncated ...]"

        # Build prompt with document context
        prompt = (
            f"The user is reading a study note titled \"{note.title}\".\n"
            f"Here is the document content:\n\n"
            f"---\n{doc_text}\n---\n\n"
            f"Answer the following question about this document. "
            f"Be helpful, accurate, and reference specific parts of the document when relevant.\n\n"
            f"Question: {body.message}"
        )

        # Use the existing summarization service's LLM calling infrastructure
        platform = settings.DEFAULT_LLM_PLATFORM
        config = summarization_service._get_platform_config(platform)

        payload = {
            "model": config["model"],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an AI study assistant for PathshalaAI. "
                        "You help students understand their study materials. "
                        "Answer questions based on the provided document content. "
                        "Be concise, clear, and educational. "
                        "If the answer is not in the document, say so honestly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }

        response_text = await summarization_service._call_llm(
            config["url"], config["api_key"], payload
        )

        logger.info(
            f"Chat response for note '{note.title}' by {current_user.email} "
            f"({len(response_text)} chars)"
        )

        return ChatResponse(
            response=response_text.strip(),
            platform=platform,
            model=config["model"],
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Chat failed for note {note_id}: {e}")
        if settings.DEBUG:
            logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Error processing your question. Please try again.",
        )
