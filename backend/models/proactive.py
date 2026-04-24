from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


InsightStatus = Literal["pending", "delivered", "dismissed", "expired"]


class ProactiveInsight(BaseModel):
    id: str
    user_id: str
    insight_key: str
    category: str
    title: str
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    status: InsightStatus = "pending"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None
    source_memory_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
