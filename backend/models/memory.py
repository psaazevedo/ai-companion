from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


MemoryStatus = Literal["active", "archived", "pinned"]
MemoryKind = Literal["episodic", "semantic", "procedural", "graph"]
VisibilityScope = Literal["global", "restricted", "private"]
MemoryUse = Literal["mention", "silent"]


class RetrievedMemory(BaseModel):
    kind: MemoryKind
    content: str
    score: float
    source_id: str
    confidence: Optional[float] = None
    memory_status: Optional[MemoryStatus] = None
    source_episode_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    superseded_by: Optional[str] = None
    archive_reason: Optional[str] = None
    conversation_mode: str = "general"
    visibility_scope: VisibilityScope = "global"
    allowed_modes: list[str] = Field(default_factory=list)
    use: MemoryUse = "mention"
    relevance_reason: Optional[str] = None


class EpisodeRecord(BaseModel):
    id: str
    user_id: str
    timestamp: str
    user_input: str
    agent_response: str
    summary: str
    emotional_tone: str
    salience: float
    memory_status: MemoryStatus
    recall_count: int = 0
    stability: float = 1.0
    archive_reason: Optional[str] = None
    dialogue_signals: dict[str, object] = Field(default_factory=dict)
    conversation_mode: str = "general"
    visibility_scope: VisibilityScope = "global"
    allowed_modes: list[str] = Field(default_factory=list)


class SemanticRecord(BaseModel):
    id: str
    user_id: str
    content: str
    category: str
    fact_key: Optional[str] = None
    confidence: float = 0.7
    reinforcement_count: int = 1
    memory_status: MemoryStatus = "active"
    source_episode_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    superseded_by: Optional[str] = None
    conversation_mode: str = "general"
    visibility_scope: VisibilityScope = "global"
    allowed_modes: list[str] = Field(default_factory=list)


class ProceduralRecord(BaseModel):
    id: str
    user_id: str
    content: str
    pattern_key: Optional[str] = None
    confidence: float = 0.7
    reinforcement_count: int = 1
    memory_status: MemoryStatus = "active"
    source_episode_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    superseded_by: Optional[str] = None
    conversation_mode: str = "general"
    visibility_scope: VisibilityScope = "global"
    allowed_modes: list[str] = Field(default_factory=list)


class GraphFact(BaseModel):
    source_label: str
    target_label: str
    relation: str
    source_type: str = "person"
    target_type: str = "concept"
    weight: float = Field(default=0.4, ge=0.0, le=1.0)
