from fastapi import APIRouter

from app.api.v1.endpoints import pdf, users, admin, notes, stats, chat

api_router = APIRouter()

api_router.include_router(pdf.router, prefix="/pdf", tags=["PDF"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(notes.router, prefix="/notes", tags=["Notes"])
api_router.include_router(stats.router, prefix="/stats", tags=["Stats"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])
