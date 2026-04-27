from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from db.postgres import get_database
from models.agent import Assessment


HEAVY_TONES = {"stressed", "frustrated", "sad", "grief"}


@dataclass
class ContextualState:
    emotional_pressure: str
    response_mode: str
    communication_preference: str
    dialogue_style: str
    pause_tolerance_seconds: float
    notes: list[str]


class ContextualStateService:
    def __init__(self) -> None:
        self.db = get_database()

    async def build_state(self, user_id: str, assessment: Assessment) -> ContextualState:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT emotional_tone, timestamp
                    FROM episodes
                    WHERE user_id = %s
                      AND visibility_scope = 'global'
                    ORDER BY timestamp DESC
                    LIMIT 6
                    """,
                    (user_id,),
                )
                recent_episodes = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT fact_key, content
                    FROM semantic_memories
                    WHERE user_id = %s
                      AND memory_status IN ('active', 'pinned')
                      AND visibility_scope = 'global'
                    ORDER BY confidence DESC, reinforcement_count DESC, last_updated DESC
                    LIMIT 12
                    """,
                    (user_id,),
                )
                semantic_rows = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT pattern_key, content
                    FROM procedural_memories
                    WHERE user_id = %s
                      AND memory_status IN ('active', 'pinned')
                      AND visibility_scope = 'global'
                    ORDER BY confidence DESC, reinforcement_count DESC, last_updated DESC
                    LIMIT 8
                    """,
                    (user_id,),
                )
                procedural_rows = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT
                        sample_count,
                        avg_words_per_turn,
                        hedging_score,
                        indirectness_score,
                        ramble_score,
                        disfluency_score,
                        filler_rate,
                        self_correction_rate,
                        pause_tolerance_seconds
                    FROM dialogue_profiles
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                dialogue_profile = await cur.fetchone()

        semantic_keys = {
            str(row["fact_key"]): str(row["content"])
            for row in semantic_rows
            if row["fact_key"]
        }
        procedural_keys = {
            str(row["pattern_key"]): str(row["content"])
            for row in procedural_rows
            if row["pattern_key"]
        }
        recent_tones = [
            str(row["emotional_tone"])
            for row in recent_episodes
            if row["emotional_tone"]
        ]

        heavy_recent = sum(1 for tone in recent_tones if tone in HEAVY_TONES)
        incoming_heavy = assessment.emotional_tone in HEAVY_TONES

        if incoming_heavy or heavy_recent >= 2:
            emotional_pressure = "high"
        elif heavy_recent == 1 or assessment.emotional_tone not in {"neutral", "excited"}:
            emotional_pressure = "medium"
        else:
            emotional_pressure = "low"

        prefers_direct = (
            "preference:communication_style" in semantic_keys
            or "style:direct_concise" in procedural_keys
        )
        prefers_grounding = (
            "preference:stress_response_style" in semantic_keys
            or "response:emotional_grounding" in procedural_keys
            or "pattern:recent_emotional_heaviness" in semantic_keys
        )

        if emotional_pressure == "high" and prefers_grounding:
            response_mode = "grounding"
        elif prefers_direct:
            response_mode = "direct"
        elif emotional_pressure == "medium":
            response_mode = "steady"
        else:
            response_mode = "balanced"

        communication_preference = "direct" if prefers_direct else "warm"
        dialogue_style = "plain"
        pause_tolerance_seconds = 0.9
        notes: list[str] = []

        if dialogue_profile:
            pause_tolerance_seconds = float(dialogue_profile["pause_tolerance_seconds"] or 0.9)
            if float(dialogue_profile["disfluency_score"] or 0.0) >= 0.42:
                dialogue_style = "hesitant"
            elif float(dialogue_profile["indirectness_score"] or 0.0) >= 0.5 or float(dialogue_profile["ramble_score"] or 0.0) >= 0.55:
                dialogue_style = "winding"
            elif float(dialogue_profile["avg_words_per_turn"] or 0.0) >= 45:
                dialogue_style = "expansive"

        if emotional_pressure == "high":
            notes.append("Recent conversation signals suggest elevated stress or emotional heaviness.")
        elif emotional_pressure == "medium":
            notes.append("There is some recent emotional load, so avoid overloading the response.")

        if prefers_direct:
            notes.append("The user tends to prefer direct, concise communication.")

        if prefers_grounding:
            notes.append("When the user feels overwhelmed, grounding and calm structure help.")

        if dialogue_profile:
            if dialogue_style == "hesitant":
                notes.append("The user may hesitate or self-correct while speaking. Do not rush to fill gaps or conclude the turn too quickly.")
            elif dialogue_style == "winding":
                notes.append("The user may take a longer path before landing the main point. Let the thread complete before reframing.")
            elif dialogue_style == "expansive":
                notes.append("The user often thinks out loud in longer turns. Summarize gently after the point lands instead of cutting in early.")

            if float(dialogue_profile["hedging_score"] or 0.0) >= 0.45:
                notes.append("The user may soften requests with hedging language. Infer intent gently without demanding perfect directness.")

        if not notes:
            notes.append("No special conversational pressure is active right now.")

        return ContextualState(
            emotional_pressure=emotional_pressure,
            response_mode=response_mode,
            communication_preference=communication_preference,
            dialogue_style=dialogue_style,
            pause_tolerance_seconds=round(pause_tolerance_seconds, 2),
            notes=notes,
        )


@lru_cache
def get_contextual_state_service() -> ContextualStateService:
    return ContextualStateService()
