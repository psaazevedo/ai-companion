from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Optional

import httpx

from config import get_settings
from models.agent import Assessment


@dataclass
class WebSource:
    title: str
    url: str
    snippet: str
    published_at: Optional[str] = None


@dataclass
class ExternalContext:
    kind: str
    query: str
    source: str
    summary: str
    fetched_at: str
    confidence: float = 0.75
    sources: list[WebSource] = field(default_factory=list)
    error: Optional[str] = None


CURRENT_INFO_MARKERS = {
    "today",
    "latest",
    "current",
    "currently",
    "right now",
    "this week",
    "this month",
    "recent",
    "new",
    "news",
    "market",
    "stock",
    "price",
    "weather",
    "forecast",
    "search",
    "look up",
    "lookup",
    "internet",
    "online",
    "web",
}


class InternetToolService:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def context_for_turn(
        self,
        query: str,
        assessment: Optional[Assessment] = None,
    ) -> Optional[ExternalContext]:
        if not self.should_search(query, assessment):
            return None
        return await self.search(query)

    def should_search(self, query: str, assessment: Optional[Assessment] = None) -> bool:
        lowered = query.lower()
        if any(marker in lowered for marker in CURRENT_INFO_MARKERS):
            return True
        if assessment and assessment.stakes == "high":
            return any(marker in lowered for marker in ["law", "legal", "tax", "medical", "finance", "investment"])
        return False

    async def search(self, query: str) -> ExternalContext:
        provider = self.settings.internet_search_provider.lower().strip()
        fetched_at = datetime.now(timezone.utc).isoformat()

        if provider == "brave":
            if not self.settings.brave_search_api_key:
                return self._unavailable_context(query, provider, fetched_at)
            return await self._search_brave(query, fetched_at)

        if provider == "tavily":
            if not self.settings.tavily_api_key:
                return self._unavailable_context(query, provider, fetched_at)
            return await self._search_tavily(query, fetched_at)

        return ExternalContext(
            kind="web_search",
            query=query,
            source=provider or "unknown",
            summary="Internet search is not available because the configured provider is not supported.",
            fetched_at=fetched_at,
            confidence=0.0,
            error="unsupported_provider",
        )

    async def _search_tavily(self, query: str, fetched_at: str) -> ExternalContext:
        payload = {
            "api_key": self.settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": self._max_results(),
            "include_answer": False,
            "include_raw_content": False,
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.post("https://api.tavily.com/search", json=payload)
            response.raise_for_status()
            data = response.json()

        sources = [
            WebSource(
                title=str(item.get("title") or "Untitled"),
                url=str(item.get("url") or ""),
                snippet=str(item.get("content") or ""),
                published_at=str(item.get("published_date") or "") or None,
            )
            for item in list(data.get("results") or [])
            if item.get("url")
        ]

        return ExternalContext(
            kind="web_search",
            query=query,
            source="Tavily",
            summary=self._summarize_sources(sources),
            fetched_at=fetched_at,
            confidence=0.78 if sources else 0.25,
            sources=sources,
            error=None if sources else "no_results",
        )

    async def _search_brave(self, query: str, fetched_at: str) -> ExternalContext:
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": str(self.settings.brave_search_api_key),
        }
        params = {
            "q": query,
            "count": self._max_results(),
            "text_decorations": "false",
            "safesearch": "moderate",
        }
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers=headers,
                params=params,
            )
            response.raise_for_status()
            data = response.json()

        sources = [
            WebSource(
                title=str(item.get("title") or "Untitled"),
                url=str(item.get("url") or ""),
                snippet=str(item.get("description") or ""),
                published_at=str(item.get("age") or "") or None,
            )
            for item in list((data.get("web") or {}).get("results") or [])
            if item.get("url")
        ]

        return ExternalContext(
            kind="web_search",
            query=query,
            source="Brave Search",
            summary=self._summarize_sources(sources),
            fetched_at=fetched_at,
            confidence=0.78 if sources else 0.25,
            sources=sources,
            error=None if sources else "no_results",
        )

    def _unavailable_context(self, query: str, provider: str, fetched_at: str) -> ExternalContext:
        return ExternalContext(
            kind="web_search",
            query=query,
            source=provider,
            summary=(
                "Internet search was requested, but no search API key is configured. "
                "Answer from memory only if safe, and be explicit that live web access is unavailable."
            ),
            fetched_at=fetched_at,
            confidence=0.0,
            sources=[],
            error="missing_api_key",
        )

    def _summarize_sources(self, sources: list[WebSource]) -> str:
        if not sources:
            return "No web results were returned."

        lines = []
        for index, source in enumerate(sources[: self._max_results()], start=1):
            snippet = " ".join(source.snippet.split())
            if len(snippet) > 260:
                snippet = snippet[:257].rstrip() + "..."
            date_note = f" Published: {source.published_at}." if source.published_at else ""
            lines.append(f"{index}. {source.title}.{date_note} {snippet} Source: {source.url}")
        return "\n".join(lines)

    def _max_results(self) -> int:
        return max(1, min(int(self.settings.internet_search_max_results or 5), 8))


@lru_cache
def get_internet_tool_service() -> InternetToolService:
    return InternetToolService()

