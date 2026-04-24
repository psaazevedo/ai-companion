from __future__ import annotations

import logging
from typing import List, Optional

import httpx
from openai import AsyncOpenAI

from config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = (
            AsyncOpenAI(
                api_key=self.settings.embedding_api_key,
                base_url=self.settings.embedding_base_url,
            )
            if self.settings.embedding_api_key
            else None
        )

    @property
    def is_enabled(self) -> bool:
        if not self.settings.embeddings_enabled:
            return False
        if self.settings.embedding_provider == "supabase":
            return bool(self.settings.supabase_url and self.settings.supabase_publishable_key)
        return self.client is not None

    async def embed_text(self, text: str) -> Optional[List[float]]:
        if not self.is_enabled or not text.strip():
            return None

        if self.settings.embedding_provider == "supabase":
            return await self._embed_with_supabase(text)

        response = await self.client.embeddings.create(
            model=self.settings.embedding_model,
            input=text,
            dimensions=self.settings.embedding_dimensions,
        )
        return list(response.data[0].embedding)

    async def _embed_with_supabase(self, text: str) -> Optional[List[float]]:
        function_url = (
            f"{self.settings.supabase_url}/functions/v1/"
            f"{self.settings.supabase_embedding_function_name}"
        )
        headers = {
            "Authorization": f"Bearer {self.settings.supabase_publishable_key}",
            "apikey": str(self.settings.supabase_publishable_key),
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(function_url, json={"input": text}, headers=headers)
                response.raise_for_status()
            except httpx.HTTPError:
                logger.exception("Supabase embedding function request failed")
                return None

        payload = response.json()
        if isinstance(payload, dict):
            vector = payload.get("embedding") or payload.get("data")
        else:
            vector = payload
        if not isinstance(vector, list):
            return None
        return [float(value) for value in vector]


def vector_literal(embedding: Optional[List[float]]) -> Optional[str]:
    if embedding is None:
        return None
    return "[" + ",".join(f"{value:.8f}" for value in embedding) + "]"
