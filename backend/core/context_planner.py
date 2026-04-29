from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from core.llm import LLMClient
from models.agent import Assessment


@dataclass
class MemoryNeed:
    slot: str
    query: str
    reason: str
    required: bool = False
    limit: int = 3


@dataclass
class ToolNeed:
    tool: str
    query: str
    reason: str
    requires_memory_slots: list[str] = field(default_factory=list)
    required: bool = False


@dataclass
class ContextPlan:
    intent: str
    answer_strategy: str
    memory_needs: list[MemoryNeed] = field(default_factory=list)
    tool_needs: list[ToolNeed] = field(default_factory=list)
    ask_if_missing: list[str] = field(default_factory=list)
    confidence: float = 0.7
    source: str = "llm"


class ContextPlanner:
    """Model-guided plan for what context must be gathered before answering."""

    def __init__(self, llm: LLMClient) -> None:
        self.llm = llm

    async def resolve_user_input(
        self,
        user_input: str,
        recent_turns: Optional[list[dict[str, str]]] = None,
        conversation_mode: str = "general",
    ) -> str:
        if self.llm.is_mock_mode or not recent_turns:
            return user_input

        recent_context = self._format_recent_turns(recent_turns)
        try:
            raw = await self.llm.complete(
                system_prompt="""
You rewrite the current user message into a standalone request for a personal AI companion.
Use recent conversation only to resolve follow-ups, pronouns, corrections, missing parameters, and ellipses.
Do not answer the request.
Do not infer durable personal facts unless the user explicitly states them.
If the current message already stands alone, return it unchanged.
Return JSON only.
""",
                user_prompt=f"""
Conversation mode: {conversation_mode}

Recent conversation:
{recent_context}

Current user message:
{user_input}

Return exactly this JSON shape:
{{
  "standalone_user_request": "the resolved request the companion should answer",
  "depends_on_recent": true
}}
""",
            )
            payload = json.loads(self._extract_json(raw))
            resolved = str(payload.get("standalone_user_request") or "").strip()
            return resolved or user_input
        except Exception:
            return user_input

    async def plan(
        self,
        user_input: str,
        assessment: Assessment,
        conversation_mode: str = "general",
        recent_turns: Optional[list[dict[str, str]]] = None,
    ) -> ContextPlan:
        if self.llm.is_mock_mode:
            return self._fallback_plan(user_input, assessment)

        recent_context = self._format_recent_turns(recent_turns or [])
        raw = await self.llm.complete(
            system_prompt="""
You are the context planner for a personal AI companion.
Before the companion replies, ask: "What information do I need to best answer this user?"
Do not answer the user. Return JSON only.

Allowed memory slots:
- home_location: where the user lives or usually means by "outside"/"near me"
- current_location: where the user is right now if different from home
- identity: stable identity facts
- preferences: communication and personal preferences
- goals: active goals and priorities
- projects: current projects and work
- people: people or relationships mentioned by the user
- recent_episodes: recent conversation history
- procedures: how the companion should help this user
- sensory_state: current emotional/body/environment context

Allowed tools:
- weather: current weather or forecast for a concrete location
- web_search: current facts, news, or general internet lookup
- finance: market, stock, crypto, or pricing data

Rules:
- Infer the minimum personal memory needed from the user's wording.
- Use recent conversation to resolve short follow-ups, pronouns, corrections, and ellipses before deciding what memory or tools are needed.
- Treat short clarifications like "yes, from San Francisco" as context for the active thread unless the user clearly states a durable personal fact.
- If the recent thread contains an unanswered or partially answered user request and the current message supplies the missing parameter, plan to answer that original request with the new parameter.
- When a short follow-up conflicts with an assistant's prior interpretation, prefer the user's wording and the prior user request over the assistant's interpretation.
- If the answer depends on a user-specific fact such as where they live, what "my city" means, their preferences, their current project, or their prior constraints, request the relevant memory slot.
- If the answer depends on current or external facts, request the right tool.
- If a tool query needs a remembered fact, list that memory slot in requires_memory_slots and phrase the query with a clear placeholder such as "resolved home location".
- If required context is unavailable, the final answer should ask for the missing detail rather than inventing it.
- Prefer a small, precise context plan over broad retrieval. Do not add memory or tools just because they might be interesting.
""",
            user_prompt=f"""
Conversation mode: {conversation_mode}
Assessment:
- stakes: {assessment.stakes}
- novelty: {assessment.novelty}
- emotional_tone: {assessment.emotional_tone}

Recent conversation:
{recent_context}

User message:
{user_input}

Return exactly this JSON shape:
{{
  "intent": "short intent label",
  "answer_strategy": "how the companion should answer after context is gathered",
  "memory_needs": [
    {{"slot": "home_location", "query": "Where does the user live?", "reason": "Needed for local weather", "required": true, "limit": 2}}
  ],
  "tool_needs": [
    {{"tool": "weather", "query": "current weather for the resolved location", "reason": "User asked for current local weather", "requires_memory_slots": ["home_location"], "required": true}}
  ],
  "ask_if_missing": ["location"],
  "confidence": 0.0
}}
""",
        )
        return self._parse_plan(raw, user_input, assessment)

    def _format_recent_turns(self, recent_turns: list[dict[str, str]]) -> str:
        if not recent_turns:
            return "- No recent turns available."
        lines = []
        for turn in recent_turns[-8:]:
            role = str(turn.get("role") or "unknown").strip() or "unknown"
            text = " ".join(str(turn.get("text") or "").split())
            if not text:
                continue
            lines.append(f"- {role}: {text[:700]}")
        return "\n".join(lines) if lines else "- No recent turns available."

    def _parse_plan(self, raw: str, user_input: str, assessment: Assessment) -> ContextPlan:
        try:
            payload = json.loads(self._extract_json(raw))
            memory_needs = [
                MemoryNeed(
                    slot=str(item.get("slot") or "recent_episodes"),
                    query=str(item.get("query") or user_input),
                    reason=str(item.get("reason") or "Planner requested this memory."),
                    required=bool(item.get("required", False)),
                    limit=max(1, min(int(item.get("limit") or 3), 6)),
                )
                for item in list(payload.get("memory_needs") or [])
                if isinstance(item, dict)
            ]
            tool_needs = [
                ToolNeed(
                    tool=str(item.get("tool") or "web_search"),
                    query=str(item.get("query") or user_input),
                    reason=str(item.get("reason") or "Planner requested this tool."),
                    requires_memory_slots=[str(slot) for slot in list(item.get("requires_memory_slots") or [])],
                    required=bool(item.get("required", False)),
                )
                for item in list(payload.get("tool_needs") or [])
                if isinstance(item, dict)
            ]
            return ContextPlan(
                intent=str(payload.get("intent") or "answer_user"),
                answer_strategy=str(payload.get("answer_strategy") or "Answer naturally with retrieved evidence."),
                memory_needs=memory_needs,
                tool_needs=tool_needs,
                ask_if_missing=[str(item) for item in list(payload.get("ask_if_missing") or [])],
                confidence=float(payload.get("confidence") or 0.7),
                source="llm",
            )
        except Exception:
            return self._fallback_plan(user_input, assessment)

    def _extract_json(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            return stripped[start : end + 1]
        return stripped

    def _fallback_plan(self, user_input: str, assessment: Assessment) -> ContextPlan:
        memory_needs: list[MemoryNeed] = []
        tool_needs: list[ToolNeed] = []

        if assessment.stakes == "high":
            memory_needs.append(
                MemoryNeed(
                    slot="procedures",
                    query="How should the companion handle high-stakes or sensitive questions for this user?",
                    reason="High-stakes answers need calibrated support and user-specific procedure.",
                    required=False,
                    limit=2,
                )
            )

        if not memory_needs:
            memory_needs.append(
                MemoryNeed(
                    slot="recent_episodes",
                    query=user_input,
                    reason="General relevance retrieval for the current message.",
                    required=False,
                    limit=4,
                )
            )

        return ContextPlan(
            intent="answer_user",
            answer_strategy="Answer with generally relevant retrieved memory. If important context is missing, ask a focused follow-up.",
            memory_needs=memory_needs,
            tool_needs=tool_needs,
            ask_if_missing=[],
            confidence=0.35,
            source="fallback",
        )
