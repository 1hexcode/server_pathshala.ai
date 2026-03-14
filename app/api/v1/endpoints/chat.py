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
from app.models.ai_chat_log import AIChatLog
from app.services.pdf_service import pdf_service
from app.services.summarization_service import summarization_service
from app.services.storage_service import storage_service

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


async def _download_and_extract_text(file_url: str) -> str:
    """Download a file from storage and extract its text content."""
    storage_path = storage_service.extract_storage_path(file_url)
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

    try:
        # Use stored OCR text for handwritten notes, otherwise extract from PDF
        if note.is_handwritten and note.extracted_text:
            logger.info(f"Using stored OCR text for handwritten note: {note.title}")
            doc_text = note.extracted_text
        elif note.is_handwritten and not note.extracted_text:
            # OCR failed during upload — no text available
            raise HTTPException(
                status_code=400,
                detail=(
                    "OCR text is not available for this handwritten note. "
                    "The OCR service may have been unavailable during upload. "
                    "Please try re-processing this note."
                ),
            )
        else:
            doc_text = await _download_and_extract_text(note.file_url)

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

        # Get active model from DB (falls back to env-var config)
        config = await summarization_service.get_active_model(db)

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
            f"via {config.get('display_name', 'unknown')} ({len(response_text)} chars)"
        )

        # Log the AI interaction
        chat_log = AIChatLog(
            user_id=current_user.id,
            note_id=note.id,
            question=body.message,
            platform=config.get("platform", "unknown"),
        )
        db.add(chat_log)

        return ChatResponse(
            response=response_text.strip(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat failed for note {note_id}: {e}")
        if settings.DEBUG:
            logger.error(f"Traceback:\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong. Please try again later.",
        )
