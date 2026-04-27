from functools import lru_cache
from typing import Any, AsyncIterator, Optional
import re

from core.llm import LLMClient
from core.voice import VoiceProcessor
from memory.service import get_memory_service
from models.agent import AgentResponse, Assessment, DialogueSignals
from models.memory import RetrievedMemory
from sensory.service import ContextualState, get_contextual_state_service
from tools.internet import ExternalContext, get_internet_tool_service

SYSTEM_PROMPT = """
You are a personal AI companion.
You are warm, present, and direct without sounding robotic.
You never pretend to know things you do not know.
If the model is uncertain, it should say so plainly.
Keep responses conversational and useful.
"""


class AgentOrchestrator:
    def __init__(self) -> None:
        self.llm = LLMClient()
        self.voice = VoiceProcessor()
        self.memory = get_memory_service()
        self.contextual_state = get_contextual_state_service()
        self.internet = get_internet_tool_service()

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

        final_text = accumulated.strip() or self.llm._mock_reply(prepared["prompt"])
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

        assessment = self.assess_input(transcript)
        memories = await self.memory.retrieve_context(
            user_id=user_id,
            query=transcript,
            assessment=assessment,
            conversation_mode=conversation_mode,
        )
        contextual_state = await self.contextual_state.build_state(
            user_id=user_id,
            assessment=assessment,
        )
        external_context = await self.internet.context_for_turn(
            query=transcript,
            assessment=assessment,
        )
        prompt = self.build_prompt(
            user_id=user_id,
            transcript=transcript,
            assessment=assessment,
            memories=memories,
            contextual_state=contextual_state,
            external_context=external_context,
            conversation_mode=conversation_mode,
        )

        return {
            "user_id": user_id,
            "transcript": transcript,
            "assessment": assessment,
            "prompt": prompt,
            "conversation_mode": conversation_mode,
        }

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
        assessment: Assessment,
        memories: list[RetrievedMemory],
        contextual_state: ContextualState,
        external_context: Optional[ExternalContext],
        conversation_mode: str = "general",
    ) -> str:
        memory_section = self.format_memories(memories)
        contextual_state_section = self.format_contextual_state(contextual_state)
        external_context_section = self.format_external_context(external_context)
        return f"""
User ID: {user_id}
Conversation mode: {conversation_mode}
Assessment:
- Stakes: {assessment.stakes}
- Novelty: {assessment.novelty}
- Emotional tone: {assessment.emotional_tone}
- Dialogue style: {assessment.dialogue_signals.verbosity} verbosity, hedging {assessment.dialogue_signals.hedging_score:.2f}, indirectness {assessment.dialogue_signals.indirectness_score:.2f}, ramble {assessment.dialogue_signals.ramble_score:.2f}, disfluency {assessment.dialogue_signals.disfluency_score:.2f}

Current contextual state:
{contextual_state_section}

External information:
{external_context_section}

Memory layers in play:
{memory_section}

Current user message:
{transcript}

Respond naturally. Keep it concise, warm, and honest.
If the input touches a high-stakes domain, be more careful and explicit about uncertainty.
Use relevant memory naturally, but do not force it into every reply.
Use external information when present, but keep it separate from personal memory.
When external information has source URLs, cite the source naturally in text.
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
            line = f"- {label}{provenance}: {memory.content}{reason}"
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

    def format_external_context(self, external_context: Optional[ExternalContext]) -> str:
        if not external_context:
            return "- No external lookup was needed for this turn."

        lines = [
            f"- Tool: {external_context.kind}",
            f"- Provider: {external_context.source}",
            f"- Query: {external_context.query}",
            f"- Fetched at: {external_context.fetched_at}",
            f"- Confidence: {external_context.confidence:.2f}",
        ]
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


@lru_cache
def get_agent() -> AgentOrchestrator:
    return AgentOrchestrator()
