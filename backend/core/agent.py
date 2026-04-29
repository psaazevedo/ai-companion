from dataclasses import asdict
from functools import lru_cache
from typing import Any, AsyncIterator, Optional
import re

from core.context_planner import ContextPlan, ContextPlanner, MemoryNeed, ToolNeed
from core.llm import LLMClient
from core.modes import AgentModePolicy, get_mode_policy, list_mode_policies
from core.voice import VoiceProcessor
from memory.service import get_memory_service
from models.agent import AgentResponse, Assessment, DialogueSignals
from models.memory import RetrievedMemory
from sensory.service import ContextualState, get_contextual_state_service
from tools.internet import ExternalContext, ToolRoute, get_internet_tool_service

SYSTEM_PROMPT = """
You are a personal AI companion.
You sound like a thoughtful person speaking out loud, not a report generator.
You are warm, present, and direct without sounding robotic, customer-support-ish, or overly formal.
You never pretend to know things you do not know.
If the model is uncertain, it should say so plainly.
Keep responses conversational, useful, and easy to hear.
Every response may be spoken aloud by a voice agent.
Write for listening first: natural phrasing, short-ish sentences, no raw URLs, no markdown links, and no dense citation strings.
When using external sources, weave the source name in casually when it helps. Do not sound like you are reading citations.
"""

MEMORY_CONTENT_LIMITS = {
    ("episodic", "mention"): 720,
    ("episodic", "silent"): 520,
    ("semantic", "mention"): 460,
    ("semantic", "silent"): 360,
    ("procedural", "mention"): 460,
    ("procedural", "silent"): 380,
    ("graph", "mention"): 380,
    ("graph", "silent"): 320,
}


def format_for_voice_delivery(text: str) -> str:
    """Remove artifacts that sound bad when read aloud by TTS."""
    if not text:
        return text

    cleaned = re.sub(r"\s*\((?:https?://|www\.)[^)]*\)", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:source|sources|url|link):\s*(?:https?://|www\.)\S+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\b(?:at|see|visit)\s+(?:https?://|www\.)\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(?:https?://|www\.)\S+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+([,.!?;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


class AgentOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.voice = VoiceProcessor()
        self.memory = get_memory_service()
        self.contextual_state = get_contextual_state_service()
        self.internet = get_internet_tool_service()
        self.context_planner = ContextPlanner(self.llm)

    async def process_input(
        self,
        user_id: str,
        user_input: Optional[str] = None,
        audio_data: Optional[bytes] = None,
        audio_filename: Optional[str] = None,
        conversation_mode: str = "general",
        visibility_scope: Optional[str] = None,
        allowed_modes: Optional[list[str]] = None,
    ) -> AgentResponse:
        prepared = await self._prepare_turn(
            user_id=user_id,
            user_input=user_input,
            audio_data=audio_data,
            audio_filename=audio_filename,
            conversation_mode=conversation_mode,
        )

        text = await self.llm.complete(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prepared["prompt"],
        )
        text = format_for_voice_delivery(text)
        audio_base64 = await self.voice.speak(text)
        await self.memory.store_interaction(
            user_id=prepared["user_id"],
            user_input=prepared["transcript"],
            agent_response=text,
            assessment=prepared["assessment"],
            input_mode="voice" if audio_data is not None else "text",
            conversation_mode=prepared["conversation_mode"],
            visibility_scope=visibility_scope,
            allowed_modes=allowed_modes,
        )
        dialogue_profile = await self.memory.dialogue_profile(prepared["user_id"])

        confidence = 0.45 if self.llm.is_mock_mode else 0.78

        return AgentResponse(
            text=text,
            confidence=confidence,
            audio_base64=audio_base64,
            audio_mime_type=self.voice.output_mime_type,
            transcript=prepared["transcript"],
            pause_tolerance_seconds=float(dialogue_profile.get("pause_tolerance_seconds", 0.9)),
        )

    async def stream_input(
        self,
        user_id: str,
        user_input: Optional[str] = None,
        audio_data: Optional[bytes] = None,
        audio_filename: Optional[str] = None,
        conversation_mode: str = "general",
        visibility_scope: Optional[str] = None,
        allowed_modes: Optional[list[str]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        prepared = await self._prepare_turn(
            user_id=user_id,
            user_input=user_input,
            audio_data=audio_data,
            audio_filename=audio_filename,
            conversation_mode=conversation_mode,
        )
        accumulated = ""

        async for chunk in self.llm.complete_stream(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=prepared["prompt"],
        ):
            if not chunk:
                continue
            accumulated += chunk
            yield {"type": "delta", "text": chunk}

        final_text = format_for_voice_delivery(accumulated.strip() or self.llm._mock_reply(prepared["prompt"]))
        await self.memory.store_interaction(
            user_id=prepared["user_id"],
            user_input=prepared["transcript"],
            agent_response=final_text,
            assessment=prepared["assessment"],
            input_mode="voice" if audio_data is not None else "text",
            conversation_mode=prepared["conversation_mode"],
            visibility_scope=visibility_scope,
            allowed_modes=allowed_modes,
        )
        dialogue_profile = await self.memory.dialogue_profile(prepared["user_id"])

        yield {
            "type": "complete",
            "text": final_text,
            "confidence": 0.45 if self.llm.is_mock_mode else 0.78,
            "transcript": prepared["transcript"],
            "pause_tolerance_seconds": float(dialogue_profile.get("pause_tolerance_seconds", 0.9)),
        }

    def assess_input(self, user_input: str) -> Assessment:
        lowered = user_input.lower()

        high_stakes_markers = {
            "medical",
            "legal",
            "lawsuit",
            "suicidal",
            "tax",
            "contract",
            "surgery",
            "diagnosis",
        }
        emotional_markers = {
            "overwhelmed": "stressed",
            "anxious": "stressed",
            "sad": "sad",
            "grieving": "grief",
            "excited": "excited",
            "stuck": "frustrated",
        }

        stakes = "high" if any(marker in lowered for marker in high_stakes_markers) else "low"
        novelty = "high" if len(user_input.split()) > 60 else "medium"

        emotional_tone = "neutral"
        for marker, tone in emotional_markers.items():
            if marker in lowered:
                emotional_tone = tone
                break

        dialogue_signals = self.analyze_dialogue_patterns(user_input)

        return Assessment(
            stakes=stakes,
            novelty=novelty,
            emotional_tone=emotional_tone,
            dialogue_signals=dialogue_signals,
        )

    async def _prepare_turn(
        self,
        user_id: str,
        user_input: Optional[str] = None,
        audio_data: Optional[bytes] = None,
        audio_filename: Optional[str] = None,
        conversation_mode: str = "general",
    ) -> dict[str, Any]:
        transcript = (user_input or "").strip()

        if audio_data:
            transcript = await self.voice.transcribe(
                audio_data,
                audio_filename=audio_filename or "audio.webm",
            )

        if not transcript:
            transcript = "The user sent an empty message."

        recent_turns = await self.recent_conversation_turns(
            user_id=user_id,
            conversation_mode=conversation_mode,
            limit=8,
        )
        resolved_transcript = await self.context_planner.resolve_user_input(
            user_input=transcript,
            recent_turns=recent_turns,
            conversation_mode=conversation_mode,
        )
        assessment = self.assess_input(resolved_transcript)
        context_plan = await self.context_planner.plan(
            user_input=resolved_transcript,
            assessment=assessment,
            conversation_mode=conversation_mode,
            recent_turns=recent_turns,
        )
        memories = await self.retrieve_context_for_plan(
            user_id=user_id,
            transcript=resolved_transcript,
            assessment=assessment,
            context_plan=context_plan,
            conversation_mode=conversation_mode,
        )
        contextual_state = await self.contextual_state.build_state(
            user_id=user_id,
            assessment=assessment,
        )
        mode_policy = get_mode_policy(conversation_mode)
        missing_context = self.missing_required_context(context_plan, memories)
        tool_route = self.tool_route_for_plan(
            context_plan=context_plan,
            fallback_query=resolved_transcript,
            assessment=assessment,
            missing_context=missing_context,
        )
        external_query = self.external_query_for_plan(resolved_transcript, context_plan, memories, missing_context)
        external_context = await self.external_context_for_plan(
            query=external_query,
            assessment=assessment,
            route=tool_route,
            missing_context=missing_context,
        )
        prompt = self.build_prompt(
            user_id=user_id,
            transcript=transcript,
            resolved_transcript=resolved_transcript,
            assessment=assessment,
            memories=memories,
            contextual_state=contextual_state,
            external_context=external_context,
            mode_policy=mode_policy,
            tool_route=tool_route,
            context_plan=context_plan,
            recent_turns=recent_turns,
            conversation_mode=conversation_mode,
        )
        context_manifest = self.build_context_manifest(
            prompt=prompt,
            memories=memories,
            external_context=external_context,
            tool_route=tool_route,
        )

        return {
            "user_id": user_id,
            "transcript": transcript,
            "resolved_transcript": resolved_transcript,
            "assessment": assessment,
            "memories": memories,
            "contextual_state": contextual_state,
            "external_context": external_context,
            "mode_policy": mode_policy,
            "tool_route": tool_route,
            "context_plan": context_plan,
            "recent_turns": recent_turns,
            "external_query": external_query,
            "missing_context": missing_context,
            "context_manifest": context_manifest,
            "prompt": prompt,
            "conversation_mode": conversation_mode,
        }

    async def preview_context(
        self,
        user_id: str,
        user_input: str,
        conversation_mode: str = "general",
    ) -> dict[str, Any]:
        """Build the exact turn context without calling the LLM or storing memory."""
        prepared = await self._prepare_turn(
            user_id=user_id,
            user_input=user_input,
            conversation_mode=conversation_mode,
        )
        assessment: Assessment = prepared["assessment"]
        contextual_state: ContextualState = prepared["contextual_state"]
        external_context: Optional[ExternalContext] = prepared["external_context"]
        mode_policy: AgentModePolicy = prepared["mode_policy"]
        tool_route: ToolRoute = prepared["tool_route"]
        context_plan: ContextPlan = prepared["context_plan"]
        memories: list[RetrievedMemory] = prepared["memories"]

        return {
            "user_id": prepared["user_id"],
            "conversation_mode": prepared["conversation_mode"],
            "transcript": prepared["transcript"],
            "resolved_transcript": prepared["resolved_transcript"],
            "assessment": {
                "stakes": assessment.stakes,
                "novelty": assessment.novelty,
                "emotional_tone": assessment.emotional_tone,
                "dialogue_signals": assessment.dialogue_signals.model_dump(),
            },
            "contextual_state": asdict(contextual_state),
            "mode_policy": asdict(mode_policy),
            "tool_route": asdict(tool_route),
            "context_plan": asdict(context_plan),
            "external_context": (
                {
                    "kind": external_context.kind,
                    "query": external_context.query,
                    "source": external_context.source,
                    "summary": external_context.summary,
                    "fetched_at": external_context.fetched_at,
                    "confidence": external_context.confidence,
                    "error": external_context.error,
                    "sources": [
                        {
                            "title": source.title,
                            "url": source.url,
                            "snippet": source.snippet,
                            "published_at": source.published_at,
                        }
                        for source in external_context.sources
                    ],
                }
                if external_context
                else None
            ),
            "memories": [memory.model_dump() for memory in memories],
            "context_manifest": prepared["context_manifest"],
            "prompt": prepared["prompt"],
        }

    async def recent_conversation_turns(
        self,
        user_id: str,
        conversation_mode: str,
        limit: int = 8,
    ) -> list[dict[str, str]]:
        feed = await self.memory.conversation_feed(
            user_id=user_id,
            limit=max(1, min(limit, 12)),
            conversation_mode=conversation_mode,
        )
        turns: list[dict[str, str]] = []
        for turn in list(feed.get("turns") or [])[-limit:]:
            if not isinstance(turn, dict):
                continue
            text = " ".join(str(turn.get("text") or "").split())
            if not text:
                continue
            turns.append(
                {
                    "role": str(turn.get("role") or "unknown"),
                    "text": text,
                }
            )
        return turns

    async def retrieve_context_for_plan(
        self,
        user_id: str,
        transcript: str,
        assessment: Assessment,
        context_plan: ContextPlan,
        conversation_mode: str,
    ) -> list[RetrievedMemory]:
        memories: list[RetrievedMemory] = []
        for need in context_plan.memory_needs:
            memories.extend(
                await self._retrieve_memory_need(
                    user_id=user_id,
                    need=need,
                    assessment=assessment,
                    conversation_mode=conversation_mode,
                )
            )

        memories.extend(
            await self.memory.retrieve_context(
                user_id=user_id,
                query=transcript,
                assessment=assessment,
                conversation_mode=conversation_mode,
            )
        )

        deduped: list[RetrievedMemory] = []
        seen = set()
        for memory in memories:
            key = (memory.kind, memory.source_id)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(memory)
        return deduped[:14]

    async def _retrieve_memory_need(
        self,
        user_id: str,
        need: MemoryNeed,
        assessment: Assessment,
        conversation_mode: str,
    ) -> list[RetrievedMemory]:
        if need.slot in {"home_location", "current_location"}:
            location = await self.memory.user_home_location(
                user_id=user_id,
                conversation_mode=conversation_mode,
            )
            return [location] if location else []

        memories = await self.memory.retrieve_context(
            user_id=user_id,
            query=need.query,
            limit=max(1, min(need.limit, 6)),
            assessment=assessment,
            conversation_mode=conversation_mode,
        )
        for memory in memories:
            if not memory.relevance_reason:
                memory.relevance_reason = f"context plan requested {need.slot}: {need.reason}"
        return memories

    def tool_route_for_plan(
        self,
        context_plan: ContextPlan,
        fallback_query: str,
        assessment: Assessment,
        missing_context: list[str],
    ) -> ToolRoute:
        if missing_context:
            return ToolRoute(
                should_search=False,
                provider=self.internet.settings.internet_search_provider.lower().strip() or "unknown",
                provider_configured=self.internet.settings.internet_search_enabled,
                reason=f"context_plan_missing_required_memory:{','.join(missing_context)}",
                categories=[],
                high_stakes=assessment.stakes == "high",
            )

        if not context_plan.tool_needs:
            return self.internet.route_for_turn(fallback_query, assessment)

        categories = sorted({self._tool_category(tool.tool) for tool in context_plan.tool_needs})
        return ToolRoute(
            should_search=True,
            provider=self.internet.settings.internet_search_provider.lower().strip() or "unknown",
            provider_configured=self.internet.settings.internet_search_enabled,
            reason=f"context_plan:{context_plan.intent}",
            categories=categories,
            high_stakes=assessment.stakes == "high",
        )

    def external_query_for_plan(
        self,
        transcript: str,
        context_plan: ContextPlan,
        memories: list[RetrievedMemory],
        missing_context: list[str],
    ) -> str:
        if missing_context:
            return transcript
        location = self._resolve_location_from_memories(memories)
        for tool in context_plan.tool_needs:
            if location and self._tool_requires_location(tool):
                return self._query_with_location(
                    query=tool.query or transcript,
                    location=location,
                )
            if tool.tool == "weather":
                return transcript
            if tool.query:
                return tool.query
        return transcript

    async def external_context_for_plan(
        self,
        query: str,
        assessment: Assessment,
        route: ToolRoute,
        missing_context: list[str],
    ) -> Optional[ExternalContext]:
        if missing_context:
            return ExternalContext(
                kind="missing_context",
                query=query,
                source="context_planner",
                summary=(
                    "A tool lookup was intentionally skipped because required personal context "
                    f"is missing: {', '.join(missing_context)}. Ask the user for the missing detail "
                    "or use memory correction if they already provided it."
                ),
                fetched_at="not_fetched",
                confidence=0.0,
                sources=[],
                error="missing_required_memory",
            )
        return await self.internet.context_for_turn(
            query=query,
            assessment=assessment,
            route=route,
        )

    def missing_required_context(
        self,
        context_plan: ContextPlan,
        memories: list[RetrievedMemory],
    ) -> list[str]:
        available_slots = set()
        if self._resolve_location_from_memories(memories):
            available_slots.update({"home_location", "current_location"})

        missing: list[str] = []
        for tool in context_plan.tool_needs:
            if not tool.required:
                continue
            for slot in tool.requires_memory_slots:
                if slot not in available_slots and slot not in missing:
                    missing.append(slot)
        return missing

    def _tool_category(self, tool_name: str) -> str:
        if tool_name == "weather":
            return "weather"
        if tool_name == "finance":
            return "finance"
        return "current_info"

    def _tool_requires_location(self, tool: ToolNeed) -> bool:
        return bool(
            {"home_location", "current_location"}.intersection(tool.requires_memory_slots)
            or "[user's city]" in tool.query.lower()
            or "[city]" in tool.query.lower()
            or "resolved location" in tool.query.lower()
            or "resolved home location" in tool.query.lower()
        )

    def _query_with_location(self, query: str, location: str) -> str:
        location = location.strip()
        if not location:
            return query

        replacements = [
            "{user's city}",
            "{user city}",
            "{city}",
            "{location}",
            "{resolved home location}",
            "{resolved location}",
            "[user's city]",
            "[user city]",
            "[city]",
            "[location]",
            "the resolved home location",
            "the resolved location",
            "resolved home location",
            "resolved location",
        ]

        resolved = query
        for marker in replacements:
            resolved = re.sub(re.escape(marker), location, resolved, flags=re.IGNORECASE)

        lowered = resolved.lower()
        if location.lower() in lowered:
            return resolved
        if re.search(r"\b(?:in|near|around|for)\s*$", resolved, flags=re.IGNORECASE):
            return f"{resolved} {location}"
        return f"{resolved} in {location}"

    def _resolve_location_from_memories(self, memories: list[RetrievedMemory]) -> Optional[str]:
        for memory in memories:
            match = re.search(r"^User lives in (.+?)\.$", memory.content)
            if match:
                return self._normalize_location(match.group(1).strip())
        return None

    def _normalize_location(self, location: str) -> str:
        location = re.sub(r"\s+", " ", location).strip(" .,")
        match = re.fullmatch(r"([A-Z][A-Za-z .'-]+) in ([A-Z][A-Za-z .'-]+)", location)
        if match:
            return f"{match.group(2).strip()}, {match.group(1).strip()}"
        return location

    def _prepend_memory_once(
        self,
        memories: list[RetrievedMemory],
        memory: RetrievedMemory,
    ) -> list[RetrievedMemory]:
        existing_keys = {(item.kind, item.source_id) for item in memories}
        if (memory.kind, memory.source_id) in existing_keys:
            return memories
        return [memory] + memories

    def available_modes(self) -> list[dict[str, str]]:
        return list_mode_policies()

    def analyze_dialogue_patterns(self, user_input: str) -> DialogueSignals:
        lowered = user_input.lower()
        words = re.findall(r"\b[\w']+\b", lowered)
        word_count = len(words)

        filler_patterns = [
            r"\bum\b",
            r"\buh\b",
            r"\byou know\b",
            r"\bi mean\b",
            r"\bhmm\b",
            r"\bwell\b",
        ]
        hedge_patterns = [
            r"\bi think\b",
            r"\bi guess\b",
            r"\bmaybe\b",
            r"\bperhaps\b",
            r"\bkind of\b",
            r"\bsort of\b",
            r"\bnot sure\b",
            r"\ba bit\b",
            r"\bprobably\b",
        ]
        self_correction_patterns = [
            r"\bi mean\b",
            r"\bor rather\b",
            r"\bactually\b",
            r"\bno wait\b",
            r"\blet me rephrase\b",
            r"\bsorry\b",
        ]

        filler_count = sum(len(re.findall(pattern, lowered)) for pattern in filler_patterns)
        hedge_count = sum(len(re.findall(pattern, lowered)) for pattern in hedge_patterns)
        self_correction_count = sum(len(re.findall(pattern, lowered)) for pattern in self_correction_patterns)
        repeated_word_count = len(re.findall(r"\b([a-z']+)\s+\1\b", lowered))
        self_correction_count += repeated_word_count

        first_question_index = user_input.find("?")
        words_before_question = word_count if first_question_index == -1 else len(
            re.findall(r"\b[\w']+\b", user_input[:first_question_index].lower())
        )
        long_preamble = words_before_question >= 18
        point_markers = sum(
            lowered.count(marker)
            for marker in ["what i mean", "my point is", "basically", "so yeah", "anyway"]
        )

        hedging_score = min((hedge_count * 0.18) + (filler_count * 0.05), 1.0)
        disfluency_score = min((filler_count * 0.12) + (self_correction_count * 0.16), 1.0)
        indirectness_score = min(
            (0.32 if long_preamble else 0.0)
            + (hedge_count * 0.12)
            + (point_markers * 0.1),
            1.0,
        )
        ramble_score = min(
            max(word_count - 35, 0) / 65.0
            + (0.18 if long_preamble else 0.0)
            + (point_markers * 0.06),
            1.0,
        )

        if word_count >= 70:
            verbosity = "high"
        elif word_count >= 20:
            verbosity = "medium"
        else:
            verbosity = "low"

        pause_tolerance_seconds = 0.9
        if disfluency_score >= 0.45:
            pause_tolerance_seconds += 0.45
        if indirectness_score >= 0.45 or ramble_score >= 0.55:
            pause_tolerance_seconds += 0.25

        return DialogueSignals(
            word_count=word_count,
            verbosity=verbosity,
            hedging_score=round(hedging_score, 3),
            indirectness_score=round(indirectness_score, 3),
            ramble_score=round(ramble_score, 3),
            disfluency_score=round(disfluency_score, 3),
            filler_count=filler_count,
            self_correction_count=self_correction_count,
            needs_extra_pause_tolerance=(pause_tolerance_seconds > 1.05),
            pause_tolerance_seconds=round(min(pause_tolerance_seconds, 1.8), 2),
        )

    def build_prompt(
        self,
        user_id: str,
        transcript: str,
        resolved_transcript: str,
        assessment: Assessment,
        memories: list[RetrievedMemory],
        contextual_state: ContextualState,
        external_context: Optional[ExternalContext],
        mode_policy: AgentModePolicy,
        tool_route: ToolRoute,
        context_plan: ContextPlan,
        recent_turns: Optional[list[dict[str, str]]] = None,
        conversation_mode: str = "general",
    ) -> str:
        memory_section = self.format_memories(memories)
        contextual_state_section = self.format_contextual_state(contextual_state)
        mode_policy_section = self.format_mode_policy(mode_policy)
        context_plan_section = self.format_context_plan(context_plan)
        recent_conversation_section = self.format_recent_conversation(recent_turns or [])
        external_context_section = self.format_external_context(external_context, tool_route)
        return f"""
Internal context for the companion. Use it silently unless the user asks how you know something.

User ID: {user_id}
Conversation mode: {conversation_mode}
Mode policy:
{mode_policy_section}

Context plan:
{context_plan_section}

Recent conversation:
{recent_conversation_section}

Assessment:
- Stakes: {assessment.stakes}
- Novelty: {assessment.novelty}
- Emotional tone: {assessment.emotional_tone}
- Dialogue style: {assessment.dialogue_signals.verbosity} verbosity, hedging {assessment.dialogue_signals.hedging_score:.2f}, indirectness {assessment.dialogue_signals.indirectness_score:.2f}, ramble {assessment.dialogue_signals.ramble_score:.2f}, disfluency {assessment.dialogue_signals.disfluency_score:.2f}

Internal context contract:
- Personal memory is evidence about this user, not proof about the outside world.
- Treat high-confidence and pinned memories as stable, but hedge or ask when memory is tentative.
- Mention memories only when they improve the response. Silent memories should shape tone and strategy without being quoted.
- Respect memory scope. Restricted/private context should not be generalized outside the current mode unless the user explicitly allows it.
- Keep external information separate from personal memory.
- Cite external information in a voice-friendly way by source name or publisher only. Never include raw URLs in the final response.
- If the context plan required something and it is missing from memory or tools, ask for that missing detail instead of guessing.
- Treat brief follow-ups as part of the active conversation thread. Do not reinterpret them as new durable memory unless the user explicitly says they live there, prefer it, or asks you to remember it.

Voice style:
- The final response will be spoken aloud, so sound like a person answering in conversation.
- Lead with the answer, then add one useful detail if needed.
- Use simple transitions, but do not over-explain the process.
- Do not output raw URLs, markdown links, parenthetical URLs, tracking parameters, or long citation strings.
- If a source URL is present in the context, use only the human-readable source name or site name.
- Avoid slash-heavy labels, tables, bullets, and dense lists unless the user explicitly asks for a list.
- Avoid phrases like "To answer your question", "I need to", "according to my memory", and "as an AI".
- Prefer "From San Francisco, Napa Valley is roughly an hour north, depending on traffic" over a citation-heavy report.

Current contextual state:
{contextual_state_section}

External information:
{external_context_section}

Memory layers in play:
{memory_section}

Current user message:
{transcript}

Resolved current request:
{resolved_transcript}

Respond to the user now. Do not mention the context plan, contracts, retrieved memories, or tool routing.
Keep it concise, warm, and honest.
If the input touches a high-stakes domain, be more careful and explicit about uncertainty.
Use relevant memory naturally, but do not force it into every reply.
Use external information when present, but keep it separate from personal memory.
When external information has source URLs, use the source name only if it improves trust. Do not include the URL.
If external information says live web access is unavailable, say that plainly instead of inventing current facts.
Use the contextual state to calibrate tone:
- grounding = calmer, simpler, more regulating
- direct = crisp and low-friction
- steady = supportive without being too soft
- balanced = natural and conversational
Do not mistake hesitation, self-correction, or a winding preamble for lack of clarity or lack of intent.
"""

    def format_memories(self, memories: list[RetrievedMemory]) -> str:
        if not memories:
            return "- No strongly relevant memories surfaced yet."

        mention_lines = []
        silent_lines = []
        for memory in memories:
            label = memory.kind.capitalize()
            confidence = self._memory_confidence_label(memory.confidence)
            provenance = f" [{confidence} confidence]" if confidence else ""
            reason = f" ({memory.relevance_reason})" if memory.relevance_reason else ""
            content = self._memory_prompt_content(memory)
            scope = self._memory_scope_note(memory)
            line = f"- {label}{provenance}{scope}: {content}{reason}"
            if memory.use == "silent":
                silent_lines.append(line)
            else:
                mention_lines.append(line)

        sections = []
        if mention_lines:
            sections.append("Mention naturally only if useful:\n" + "\n".join(mention_lines))
        if silent_lines:
            sections.append("Use silently to shape tone/strategy; do not quote unless directly asked:\n" + "\n".join(silent_lines))
        return "\n\n".join(sections)

    def format_contextual_state(self, contextual_state: ContextualState) -> str:
        lines = [
            f"- Emotional pressure: {contextual_state.emotional_pressure}",
            f"- Response mode: {contextual_state.response_mode}",
            f"- Communication preference: {contextual_state.communication_preference}",
            f"- Dialogue style: {contextual_state.dialogue_style}",
            f"- Suggested pause tolerance: {contextual_state.pause_tolerance_seconds:.2f} seconds",
        ]
        lines.extend(f"- Note: {note}" for note in contextual_state.notes)
        return "\n".join(lines)

    def build_context_manifest(
        self,
        prompt: str,
        memories: list[RetrievedMemory],
        external_context: Optional[ExternalContext],
        tool_route: ToolRoute,
    ) -> dict[str, Any]:
        by_kind: dict[str, int] = {}
        by_use: dict[str, int] = {}
        by_scope: dict[str, int] = {}
        statuses: dict[str, int] = {}

        for memory in memories:
            by_kind[memory.kind] = by_kind.get(memory.kind, 0) + 1
            by_use[memory.use] = by_use.get(memory.use, 0) + 1
            by_scope[memory.visibility_scope] = by_scope.get(memory.visibility_scope, 0) + 1
            if memory.memory_status:
                statuses[memory.memory_status] = statuses.get(memory.memory_status, 0) + 1

        return {
            "memory_count": len(memories),
            "memory_by_kind": by_kind,
            "memory_by_use": by_use,
            "memory_by_scope": by_scope,
            "memory_statuses": statuses,
            "external_query": external_context.query if external_context else None,
            "external_source_count": len(external_context.sources) if external_context else 0,
            "external_error": external_context.error if external_context else None,
            "tool_route": asdict(tool_route),
            "estimated_prompt_tokens": max(1, len(prompt) // 4),
            "prompt_characters": len(prompt),
        }

    def format_mode_policy(self, mode_policy: AgentModePolicy) -> str:
        return "\n".join(
            [
                f"- Role: {mode_policy.role}",
                f"- Memory boundary: {mode_policy.memory_boundary}",
                f"- Response bias: {mode_policy.response_bias}",
                f"- Caution: {mode_policy.caution}",
            ]
        )

    def format_context_plan(self, context_plan: ContextPlan) -> str:
        lines = [
            f"- Intent: {context_plan.intent}",
            f"- Strategy: {context_plan.answer_strategy}",
            f"- Planner source: {context_plan.source}; confidence: {context_plan.confidence:.2f}",
        ]
        if context_plan.memory_needs:
            lines.append("- Memory needed:")
            lines.extend(
                f"  - {need.slot}: {need.query} ({need.reason}; required={need.required})"
                for need in context_plan.memory_needs
            )
        if context_plan.tool_needs:
            lines.append("- Tools needed:")
            lines.extend(
                f"  - {tool.tool}: {tool.query} ({tool.reason}; requires={', '.join(tool.requires_memory_slots) or 'none'})"
                for tool in context_plan.tool_needs
            )
        if context_plan.ask_if_missing:
            lines.append(f"- Ask if missing: {', '.join(context_plan.ask_if_missing)}")
        return "\n".join(lines)

    def format_recent_conversation(self, recent_turns: list[dict[str, str]]) -> str:
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

    def format_external_context(
        self,
        external_context: Optional[ExternalContext],
        tool_route: Optional[ToolRoute] = None,
    ) -> str:
        if not external_context:
            route_note = ""
            if tool_route:
                categories = ", ".join(tool_route.categories) if tool_route.categories else "none"
                route_note = (
                    f"\n- Tool route: {tool_route.reason}; categories: {categories}; "
                    f"provider: {tool_route.provider}; configured: {tool_route.provider_configured}"
                )
            return "- No external lookup was needed for this turn." + route_note

        lines = [
            f"- Tool: {external_context.kind}",
            f"- Provider: {external_context.source}",
            f"- Query: {external_context.query}",
            f"- Fetched at: {external_context.fetched_at}",
            f"- Confidence: {external_context.confidence:.2f}",
        ]
        if tool_route:
            categories = ", ".join(tool_route.categories) if tool_route.categories else "none"
            lines.append(f"- Tool route: {tool_route.reason}; categories: {categories}")
        if external_context.error:
            lines.append(f"- Tool status: {external_context.error}")
        lines.append("- Results:")
        lines.extend(f"  {line}" for line in external_context.summary.splitlines())
        return "\n".join(lines)

    def _memory_confidence_label(self, confidence: Optional[float]) -> Optional[str]:
        if confidence is None:
            return None
        if confidence >= 0.86:
            return "high"
        if confidence >= 0.68:
            return "medium"
        return "tentative"

    def _memory_prompt_content(self, memory: RetrievedMemory) -> str:
        limit = MEMORY_CONTENT_LIMITS.get((memory.kind, memory.use), 420)
        text = " ".join(memory.content.split())
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "..."

    def _memory_scope_note(self, memory: RetrievedMemory) -> str:
        if memory.visibility_scope == "global":
            return ""
        modes = ", ".join(memory.allowed_modes) if memory.allowed_modes else memory.conversation_mode
        return f" [{memory.visibility_scope}; mode: {modes}]"


@lru_cache
def get_agent() -> AgentOrchestrator:
    return AgentOrchestrator()
