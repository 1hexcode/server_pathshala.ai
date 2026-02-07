"""Storage service — switches between local filesystem and Supabase based on PRODUCTION flag.

- PRODUCTION=false → LocalStorageService (saves to server/uploads/)
- PRODUCTION=true  → SupabaseStorageService (saves to Supabase Storage bucket)
"""

import os
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings
from app.core.logging import logger


class BaseStorageService(ABC):
    """Abstract base for file storage backends."""

    @abstractmethod
    async def upload(self, rel_path: str, content: bytes, content_type: str = "application/pdf") -> str:
        """Upload a file and return its public URL."""
        ...

    @abstractmethod
    async def delete(self, rel_path: str) -> None:
        """Delete a file."""
        ...

    @abstractmethod
    async def download(self, rel_path: str) -> bytes:
        """Download file bytes."""
        ...

    @abstractmethod
    def extract_storage_path(self, file_url: str) -> str:
        """Extract the relative storage path from a file URL."""
        ...


# ──────────────────────────────────────────────────────────────────────────────
# LOCAL STORAGE (development)
# ──────────────────────────────────────────────────────────────────────────────

class LocalStorageService(BaseStorageService):
    """Save files to local uploads/ directory. Used in dev mode."""

    def __init__(self):
        # server/uploads/  (relative to server/ root)
        self.upload_root = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "uploads",
        )
        os.makedirs(self.upload_root, exist_ok=True)

    async def upload(self, rel_path: str, content: bytes, content_type: str = "application/pdf") -> str:
        full_path = os.path.join(self.upload_root, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "wb") as f:
            f.write(content)

        # Return URL path relative to the StaticFiles mount
        file_url = f"/uploads/{rel_path}"
        logger.info(f"Saved locally: {full_path} → {file_url}")
        return file_url

    async def delete(self, rel_path: str) -> None:
        full_path = os.path.join(self.upload_root, rel_path)
        if os.path.exists(full_path):
            os.remove(full_path)
            logger.info(f"Deleted local file: {full_path}")

    async def download(self, rel_path: str) -> bytes:
        full_path = os.path.join(self.upload_root, rel_path)
        if not os.path.exists(full_path):
            raise RuntimeError(f"File not found: {full_path}")
        with open(full_path, "rb") as f:
            return f.read()

    def extract_storage_path(self, file_url: str) -> str:
        """Extract path from local URL like /uploads/ISC/BSc/CS20/uuid.pdf → ISC/BSc/CS20/uuid.pdf"""
        return file_url.replace("/uploads/", "", 1)


# ──────────────────────────────────────────────────────────────────────────────
# SUPABASE STORAGE (production)
# ──────────────────────────────────────────────────────────────────────────────

class SupabaseStorageService(BaseStorageService):
    """Save files to Supabase Storage. Used in production."""

    def __init__(self):
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set for production storage.")
        self.base_url = f"{settings.SUPABASE_URL}/storage/v1"
        self.bucket = settings.SUPABASE_BUCKET
        self.headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        }

    def _public_url(self, rel_path: str) -> str:
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{self.bucket}/{rel_path}"

    async def upload(self, rel_path: str, content: bytes, content_type: str = "application/pdf") -> str:
        url = f"{self.base_url}/object/{self.bucket}/{rel_path}"
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, content=content, headers=headers)

        if resp.status_code not in (200, 201):
            logger.error(f"Supabase upload failed ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"File upload failed: {resp.text}")

        public = self._public_url(rel_path)
        logger.info(f"Uploaded to Supabase: {rel_path} → {public}")
        return public

    async def delete(self, rel_path: str) -> None:
        url = f"{self.base_url}/object/{self.bucket}"
        headers = {**self.headers, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(url, headers=headers, json={"prefixes": [rel_path]})

        if resp.status_code not in (200, 201):
            logger.warning(f"Supabase delete failed ({resp.status_code}): {resp.text}")
        else:
            logger.info(f"Deleted from Supabase: {rel_path}")

    async def download(self, rel_path: str) -> bytes:
        url = f"{self.base_url}/object/{self.bucket}/{rel_path}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self.headers)

        if resp.status_code != 200:
            logger.error(f"Supabase download failed ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"File download failed: {resp.text}")

        return resp.content

    def extract_storage_path(self, file_url: str) -> str:
        """Extract path from Supabase URL like .../object/public/notes/ISC/... → ISC/..."""
        marker = f"/object/public/{self.bucket}/"
        if marker in file_url:
            return file_url.split(marker, 1)[1]
        return file_url


# ──────────────────────────────────────────────────────────────────────────────
# Singleton — pick implementation based on PRODUCTION flag
# ──────────────────────────────────────────────────────────────────────────────

def _create_storage_service() -> BaseStorageService:
    if settings.PRODUCTION:
        logger.info("Storage: Supabase (production mode)")
        return SupabaseStorageService()
    else:
        logger.info("Storage: Local filesystem (dev mode)")
        return LocalStorageService()


storage_service = _create_storage_service()
