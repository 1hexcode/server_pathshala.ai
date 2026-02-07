from fastapi import APIRouter

from app.api.v1.endpoints import pdf, users, admin

api_router = APIRouter()

api_router.include_router(pdf.router, prefix="/pdf", tags=["PDF"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
