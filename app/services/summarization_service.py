"""PDF summarization service with multi-platform LLM support (Groq, OpenRouter)."""

import asyncio
from typing import Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.logging import logger

# Platform configurations
PLATFORMS: Dict[str, Dict] = {
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "key_setting": "GROQ_API_KEY",
        "model_setting": "GROQ_MODEL",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "key_setting": "OPENROUTER_API_KEY",
        "model_setting": "OPENROUTER_MODEL",
    },
}

MAX_CHUNK_CHARS = 6000
MAX_RETRIES = 2
RETRY_BASE_DELAY = 3


class SummarizationService:
    """Service for summarizing text via LLM APIs (Groq, OpenRouter, etc.)."""

    def _get_platform_config(self, platform: str) -> dict:
        """Get URL, API key, and model for the given platform."""
        if platform not in PLATFORMS:
            raise ValueError(
                f"Unknown platform '{platform}'. "
                f"Supported: {', '.join(PLATFORMS.keys())}"
            )

        config = PLATFORMS[platform]
        api_key = getattr(settings, config["key_setting"], None)
        model = getattr(settings, config["model_setting"])

        if not api_key:
            raise ValueError(
                f"{config['key_setting']} is not set. "
                f"Add it to your .env file."
            )

        return {
            "url": config["url"],
            "api_key": api_key,
            "model": model,
        }

    def _build_payload(self, text: str, model: str, prompt: Optional[str] = None) -> dict:
        """Build the chat completion request payload."""
        system_prompt = (
            "You are an expert document summarizer. "
            "Provide a clear, concise, and well-structured summary of the given text. "
            "Highlight the key points, main arguments, and important findings. "
            "Use bullet points for clarity when appropriate."
        )
        user_prompt = prompt or "Please summarize the following document text:"

        return {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{user_prompt}\n\n{text}"},
            ],
        }

    async def _call_llm(self, url: str, api_key: str, payload: dict) -> str:
        """Call an OpenAI-compatible chat completions API with retry on 429."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(MAX_RETRIES + 1):
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, headers=headers, json=payload)

            if response.status_code == 200:
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    raise RuntimeError("LLM returned no choices in the response.")
                return choices[0]["message"]["content"]

            if response.status_code == 429 and attempt < MAX_RETRIES:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    f"Rate limited (429). Retry {attempt + 1}/{MAX_RETRIES} in {delay}s..."
                )
                await asyncio.sleep(delay)
                continue

            # Non-retryable or exhausted retries
            error_detail = response.text
            logger.error(f"LLM API error ({response.status_code}): {error_detail}")
            raise RuntimeError(
                f"LLM API returned {response.status_code}: {error_detail}"
            )

    def _split_text(self, text: str) -> List[str]:
        """Split text into chunks that fit within model context limits."""
        if len(text) <= MAX_CHUNK_CHARS:
            return [text]

        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para_len = len(para) + 2
            if current_length + para_len > MAX_CHUNK_CHARS and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_length = para_len
            else:
                current_chunk.append(para)
                current_length += para_len

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    async def summarize(
        self, text: str, platform: Optional[str] = None, prompt: Optional[str] = None
    ) -> dict:
        """
        Summarize text using the specified platform.

        Args:
            text: The text to summarize.
            platform: 'groq' or 'openrouter'. Defaults to DEFAULT_LLM_PLATFORM.
            prompt: Optional custom prompt.
        """
        if not text.strip():
            return {"summary": "", "chunks_processed": 0}

        platform = platform or settings.DEFAULT_LLM_PLATFORM
        config = self._get_platform_config(platform)

        chunks = self._split_text(text)
        logger.info(
            f"Summarizing via {platform} ({config['model']}): "
            f"{len(text)} chars, {len(chunks)} chunk(s)"
        )

        if len(chunks) == 1:
            payload = self._build_payload(chunks[0], model=config["model"], prompt=prompt)
            summary = await self._call_llm(config["url"], config["api_key"], payload)
            return {
                "summary": summary.strip(),
                "platform": platform,
                "model": config["model"],
                "chunks_processed": 1,
            }

        # Multiple chunks
        partial_summaries = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Summarizing chunk {i + 1}/{len(chunks)}")
            chunk_prompt = f"Summarize this section (part {i + 1} of {len(chunks)}):"
            payload = self._build_payload(chunk, model=config["model"], prompt=chunk_prompt)
            partial = await self._call_llm(config["url"], config["api_key"], payload)
            partial_summaries.append(partial.strip())

        # Combine
        combined = "\n\n".join(partial_summaries)
        combine_prompt = (
            "The following are summaries of different sections of the same document. "
            "Combine them into a single coherent summary:"
        )
        payload = self._build_payload(combined, model=config["model"], prompt=combine_prompt)
        final_summary = await self._call_llm(config["url"], config["api_key"], payload)

        return {
            "summary": final_summary.strip(),
            "platform": platform,
            "model": config["model"],
            "chunks_processed": len(chunks),
        }


# Singleton instance
summarization_service = SummarizationService()
