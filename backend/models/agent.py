from typing import Literal, Optional

from pydantic import BaseModel, Field


class DialogueSignals(BaseModel):
    word_count: int = 0
    verbosity: Literal["low", "medium", "high"] = "low"
    hedging_score: float = 0.0
    indirectness_score: float = 0.0
    ramble_score: float = 0.0
    disfluency_score: float = 0.0
    filler_count: int = 0
    self_correction_count: int = 0
    needs_extra_pause_tolerance: bool = False
    pause_tolerance_seconds: float = 0.9


class Assessment(BaseModel):
    stakes: Literal["low", "medium", "high"]
    novelty: Literal["low", "medium", "high"]
    emotional_tone: str
    dialogue_signals: DialogueSignals = Field(default_factory=DialogueSignals)


class AgentResponse(BaseModel):
    text: str
    confidence: float
    audio_base64: Optional[str] = None
    audio_mime_type: Optional[str] = None
    transcript: Optional[str] = None
    pause_tolerance_seconds: Optional[float] = None
