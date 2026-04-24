from typing import Union

from fastapi import APIRouter

from config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, Union[str, bool]]:
    settings = get_settings()
    return {
        "status": "ok",
        "environment": settings.environment,
        "mock_mode": settings.mock_mode,
        "memory_backend": "postgres-pgvector",
        "embeddings_enabled": settings.embeddings_enabled,
        "embedding_provider": settings.embedding_provider,
        "background_runner_enabled": settings.background_runner_enabled,
    }
