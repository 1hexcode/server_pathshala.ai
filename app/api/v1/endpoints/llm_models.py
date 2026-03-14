"""CRUD endpoints for LLM model management (super admin only)."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging import logger
from app.dependencies import require_super_admin
from app.models.user import User
from app.models.llm_model import LLMModel
from app.schemas import LLMModelCreate, LLMModelUpdate, LLMModelResponse

router = APIRouter()

SUPPORTED_PLATFORMS = {"groq", "openrouter"}


@router.get("/llm-models", response_model=List[LLMModelResponse])
async def list_llm_models(
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """List all configured LLM models."""
    result = await db.execute(
        select(LLMModel).order_by(LLMModel.priority, LLMModel.created_at)
    )
    return result.scalars().all()


@router.post("/llm-models", response_model=LLMModelResponse)
async def create_llm_model(
    data: LLMModelCreate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Add a new LLM model configuration."""
    if data.platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported platform '{data.platform}'. Use: {', '.join(SUPPORTED_PLATFORMS)}",
        )

    model = LLMModel(**data.model_dump())
    db.add(model)
    await db.flush()
    await db.refresh(model)

    logger.info(f"LLM model added by {current_user.email}: {data.platform}/{data.model_id}")
    return model


@router.patch("/llm-models/{model_id}", response_model=LLMModelResponse)
async def update_llm_model(
    model_id: UUID,
    data: LLMModelUpdate,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Update an LLM model's fields."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(model, key, value)

    await db.flush()
    await db.refresh(model)

    logger.info(f"LLM model updated by {current_user.email}: {model.display_name}")
    return model


@router.patch("/llm-models/{model_id}/toggle", response_model=LLMModelResponse)
async def toggle_llm_model(
    model_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable an LLM model."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model.is_enabled = not model.is_enabled
    await db.flush()
    await db.refresh(model)

    status = "enabled" if model.is_enabled else "disabled"
    logger.info(f"LLM model {status} by {current_user.email}: {model.display_name}")
    return model


@router.delete("/llm-models/{model_id}")
async def delete_llm_model(
    model_id: UUID,
    current_user: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Remove an LLM model configuration."""
    result = await db.execute(select(LLMModel).where(LLMModel.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    await db.delete(model)
    logger.info(f"LLM model deleted by {current_user.email}: {model.display_name}")
    return {"message": f"Model '{model.display_name}' deleted"}
