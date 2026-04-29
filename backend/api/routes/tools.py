from __future__ import annotations

from fastapi import APIRouter

from tools.internet import get_internet_tool_service

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/internet/search")
async def internet_search(q: str) -> dict[str, object]:
    service = get_internet_tool_service()
    context = await service.search(q)
    return {
        "kind": context.kind,
        "query": context.query,
        "source": context.source,
        "summary": context.summary,
        "fetched_at": context.fetched_at,
        "confidence": context.confidence,
        "error": context.error,
        "sources": [
            {
                "title": source.title,
                "url": source.url,
                "snippet": source.snippet,
                "published_at": source.published_at,
            }
            for source in context.sources
        ],
    }


@router.get("/internet/route")
async def internet_route(q: str) -> dict[str, object]:
    service = get_internet_tool_service()
    route = service.route_for_turn(q)
    return {
        "should_search": route.should_search,
        "provider": route.provider,
        "provider_configured": route.provider_configured,
        "reason": route.reason,
        "categories": route.categories,
        "high_stakes": route.high_stakes,
    }
