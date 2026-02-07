"""Supabase Storage service for file uploads.

Uses the Supabase Storage REST API directly via httpx.
No extra SDK needed.
"""

import httpx

from app.core.config import settings
from app.core.logging import logger


class StorageService:
    """Lightweight wrapper around Supabase Storage REST API."""

    def __init__(self):
        self.base_url = None
        self.headers = {}

    def _ensure_configured(self):
        """Lazy init — reads config on first use."""
        if self.base_url:
            return
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_KEY must be set for file storage."
            )
        self.base_url = f"{settings.SUPABASE_URL}/storage/v1"
        self.headers = {
            "apikey": settings.SUPABASE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_KEY}",
        }

    def _storage_path(self, rel_path: str) -> str:
        """Build the full storage API path for a file."""
        bucket = settings.SUPABASE_BUCKET
        return f"{self.base_url}/object/{bucket}/{rel_path}"

    def public_url(self, rel_path: str) -> str:
        """Get the public URL for a file in the bucket."""
        bucket = settings.SUPABASE_BUCKET
        return f"{settings.SUPABASE_URL}/storage/v1/object/public/{bucket}/{rel_path}"

    async def upload(
        self, rel_path: str, content: bytes, content_type: str = "application/pdf"
    ) -> str:
        """
        Upload a file to Supabase Storage.

        Args:
            rel_path: Path inside the bucket (e.g. "ISC/BSc/CS20/uuid.pdf")
            content: File bytes
            content_type: MIME type

        Returns:
            Public URL of the uploaded file
        """
        self._ensure_configured()

        url = self._storage_path(rel_path)
        headers = {
            **self.headers,
            "Content-Type": content_type,
            "x-upsert": "true",  # overwrite if exists
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, content=content, headers=headers)

        if resp.status_code not in (200, 201):
            logger.error(f"Supabase upload failed ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"File upload failed: {resp.text}")

        public = self.public_url(rel_path)
        logger.info(f"Uploaded to Supabase: {rel_path} → {public}")
        return public

    async def delete(self, rel_path: str) -> None:
        """Delete a file from Supabase Storage."""
        self._ensure_configured()

        bucket = settings.SUPABASE_BUCKET
        url = f"{self.base_url}/object/{bucket}"
        headers = {**self.headers, "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                url, headers=headers, json={"prefixes": [rel_path]}
            )

        if resp.status_code not in (200, 201):
            logger.warning(f"Supabase delete failed ({resp.status_code}): {resp.text}")
        else:
            logger.info(f"Deleted from Supabase: {rel_path}")

    async def download(self, rel_path: str) -> bytes:
        """Download file bytes from Supabase Storage (for AI chat text extraction)."""
        self._ensure_configured()

        bucket = settings.SUPABASE_BUCKET
        url = f"{self.base_url}/object/{bucket}/{rel_path}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(url, headers=self.headers)

        if resp.status_code != 200:
            logger.error(f"Supabase download failed ({resp.status_code}): {resp.text}")
            raise RuntimeError(f"File download failed: {resp.text}")

        return resp.content


# Singleton
storage_service = StorageService()
