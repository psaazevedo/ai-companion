from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
import re
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


@dataclass
class ToolRoute:
    should_search: bool
    provider: str
    provider_configured: bool
    reason: str
    categories: list[str] = field(default_factory=list)
    high_stakes: bool = False


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
    "outside",
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
        route: Optional[ToolRoute] = None,
    ) -> Optional[ExternalContext]:
        route = route or self.route_for_turn(query, assessment)
        if not route.should_search:
            return None
        if "weather" in set(route.categories or []):
            location = self._extract_weather_location(query)
            if location:
                weather_context = await self._weather_context(query, location)
                if not weather_context.error:
                    return weather_context
        return await self.search(query)

    def should_search(self, query: str, assessment: Optional[Assessment] = None) -> bool:
        return self.route_for_turn(query, assessment).should_search

    def route_for_turn(self, query: str, assessment: Optional[Assessment] = None) -> ToolRoute:
        lowered = query.lower()
        provider = self.settings.internet_search_provider.lower().strip() or "unknown"
        provider_configured = self.settings.internet_search_enabled
        categories: list[str] = []

        if any(marker in lowered for marker in ["weather", "forecast", "temperature", "rain", "sunny", "outside"]):
            categories.append("weather")
        if any(marker in lowered for marker in ["news", "latest", "recent", "today", "this week", "current", "currently", "right now"]):
            categories.append("current_info")
        if any(marker in lowered for marker in ["market", "stock", "price", "finance", "investment"]):
            categories.append("finance")
        if any(marker in lowered for marker in ["search", "look up", "lookup", "internet", "online", "web"]):
            categories.append("explicit_web")

        if any(marker in lowered for marker in CURRENT_INFO_MARKERS):
            return ToolRoute(
                should_search=True,
                provider=provider,
                provider_configured=provider_configured,
                reason="current_or_external_info_requested",
                categories=categories or ["current_info"],
                high_stakes=bool(assessment and assessment.stakes == "high"),
            )

        if assessment and assessment.stakes == "high":
            high_stakes_external = any(
                marker in lowered
                for marker in ["law", "legal", "tax", "medical", "finance", "investment"]
            )
            return ToolRoute(
                should_search=high_stakes_external,
                provider=provider,
                provider_configured=provider_configured,
                reason="high_stakes_domain_requires_verification" if high_stakes_external else "high_stakes_but_no_external_marker",
                categories=categories or (["high_stakes_verification"] if high_stakes_external else []),
                high_stakes=True,
            )

        return ToolRoute(
            should_search=False,
            provider=provider,
            provider_configured=provider_configured,
            reason="personal_or_stable_context_only",
            categories=categories,
            high_stakes=False,
        )

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

    async def _weather_context(self, query: str, location: str) -> ExternalContext:
        fetched_at = datetime.now(timezone.utc).isoformat()
        try:
            geocoded = await self._geocode_location(location)
            if not geocoded:
                return ExternalContext(
                    kind="weather",
                    query=query,
                    source="Open-Meteo",
                    summary=f"I could not geocode the remembered location: {location}.",
                    fetched_at=fetched_at,
                    confidence=0.0,
                    sources=[],
                    error="weather_location_not_found",
                )

            latitude, longitude, resolved_name = geocoded
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "current": ",".join(
                    [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "precipitation",
                        "weather_code",
                        "wind_speed_10m",
                    ]
                ),
                "timezone": "auto",
            }
            url = "https://api.open-meteo.com/v1/forecast"
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            current = dict(data.get("current") or {})
            units = dict(data.get("current_units") or {})
            temp_c = self._float_or_none(current.get("temperature_2m"))
            apparent_c = self._float_or_none(current.get("apparent_temperature"))
            wind = self._float_or_none(current.get("wind_speed_10m"))
            humidity = self._float_or_none(current.get("relative_humidity_2m"))
            precipitation = self._float_or_none(current.get("precipitation"))
            code = int(current.get("weather_code") or 0)
            condition = self._weather_code_label(code)

            summary_parts = [
                f"Current weather for {resolved_name}: {condition}.",
            ]
            if temp_c is not None:
                summary_parts.append(
                    f"Temperature is {temp_c:.1f}{units.get('temperature_2m', '°C')} ({self._c_to_f(temp_c):.0f}°F)."
                )
            if apparent_c is not None:
                summary_parts.append(
                    f"Feels like {apparent_c:.1f}{units.get('apparent_temperature', '°C')} ({self._c_to_f(apparent_c):.0f}°F)."
                )
            if humidity is not None:
                summary_parts.append(f"Humidity is {humidity:.0f}{units.get('relative_humidity_2m', '%')}.")
            if wind is not None:
                summary_parts.append(f"Wind is {wind:.1f} {units.get('wind_speed_10m', 'km/h')}.")
            if precipitation is not None:
                summary_parts.append(f"Precipitation is {precipitation:.1f} {units.get('precipitation', 'mm')}.")

            summary = " ".join(summary_parts)
            return ExternalContext(
                kind="weather",
                query=query,
                source="Open-Meteo",
                summary=summary,
                fetched_at=fetched_at,
                confidence=0.86,
                sources=[
                    WebSource(
                        title=f"Open-Meteo current weather for {resolved_name}",
                        url=str(response.url),
                        snippet=summary,
                    )
                ],
                error=None,
            )
        except Exception as exc:
            return ExternalContext(
                kind="weather",
                query=query,
                source="Open-Meteo",
                summary=f"Weather lookup failed for {location}: {type(exc).__name__}.",
                fetched_at=fetched_at,
                confidence=0.0,
                sources=[],
                error="weather_lookup_failed",
            )

    async def _geocode_location(self, location: str) -> Optional[tuple[float, float, str]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={
                    "name": location,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                },
            )
            response.raise_for_status()
            data = response.json()

        results = list(data.get("results") or [])
        if not results:
            return None
        result = results[0]
        name_parts = [
            str(result.get("name") or location),
            str(result.get("admin1") or ""),
            str(result.get("country") or ""),
        ]
        resolved_name = ", ".join(part for part in name_parts if part)
        return (
            float(result["latitude"]),
            float(result["longitude"]),
            resolved_name,
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

    def _extract_weather_location(self, query: str) -> Optional[str]:
        match = re.search(r"\b(?:in|for|near)\s+(.+)$", query, flags=re.IGNORECASE)
        if not match:
            return None
        location = re.sub(r"\b(?:today|right now|currently|outside|weather|forecast)\b", "", match.group(1), flags=re.IGNORECASE)
        location = re.sub(r"\s+", " ", location).strip(" ?.,")
        return location or None

    def _weather_code_label(self, code: int) -> str:
        labels = {
            0: "clear sky",
            1: "mostly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "foggy",
            48: "rime fog",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            61: "slight rain",
            63: "rain",
            65: "heavy rain",
            71: "slight snow",
            73: "snow",
            75: "heavy snow",
            80: "slight rain showers",
            81: "rain showers",
            82: "violent rain showers",
            95: "thunderstorm",
        }
        return labels.get(code, f"weather code {code}")

    def _float_or_none(self, value: object) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _c_to_f(self, value: float) -> float:
        return (value * 9 / 5) + 32


@lru_cache
def get_internet_tool_service() -> InternetToolService:
    return InternetToolService()
