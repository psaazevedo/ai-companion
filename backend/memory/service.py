from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Iterable, List, Optional

from core.embeddings import EmbeddingClient, vector_literal
from db.postgres import get_database
from models.agent import Assessment, DialogueSignals
from models.memory import GraphFact, RetrievedMemory


@dataclass
class RetrievalPlan:
    include_archived: bool
    episodic_limit: int
    semantic_limit: int
    procedural_limit: int
    graph_limit: int
    reactivation_limit: int = 0
    episodic_weight: float = 1.0
    semantic_weight: float = 1.0
    procedural_weight: float = 1.0
    graph_weight: float = 1.0


@dataclass(frozen=True)
class RetrievalIntent:
    name: str
    mention_kinds: tuple[str, ...]
    silent_kinds: tuple[str, ...]
    mention_limit: int = 4
    silent_limit: int = 3


@dataclass
class SemanticCandidate:
    category: str
    fact_key: str
    content: str
    confidence: float = 0.72


SEMANTIC_CANONICAL_FAMILIES = {
    "project:primary": {
        "content": "User is building an extraordinary personal AI companion.",
        "category": "project",
        "keywords": [
            "ai companion",
            "personal ai companion",
            "autonomous ai agent",
            "advanced memory system",
            "human like friend",
            "human-like friend",
            "samantha",
            "jarvis",
        ],
    },
    "preference:communication_style": {
        "content": "User prefers direct, concise communication.",
        "category": "preference",
        "keywords": [
            "direct communication",
            "direct + concise",
            "direct concise",
            "answer directly",
            "answers directly",
            "answer clearly",
            "concise answers",
            "keep it concise",
        ],
    },
    "preference:stress_response_style": {
        "content": "When things feel heavy, the user benefits from short, calm, grounding responses.",
        "category": "preference",
        "keywords": [
            "grounding support",
            "stay short and grounding",
            "when the user is stressed",
            "when things feel heavy",
            "concise answers under stress",
            "calm grounding",
            "grounding responses",
        ],
    },
    "procedure:direct_concise_response": {
        "content": "Default to direct, concise communication unless the user asks for more depth.",
        "category": "procedure",
        "keywords": [
            "direct + concise",
            "answer directly first",
            "default to direct",
            "concise communication",
            "direct communication and concise answers",
        ],
    },
    "location:home": {
        "content": "",
        "category": "location",
        "keywords": [],
    },
}


@dataclass
class ProceduralCandidate:
    pattern_key: str
    content: str
    confidence: float = 0.68


@dataclass(frozen=True)
class MemoryScope:
    conversation_mode: str = "general"
    visibility_scope: str = "global"
    allowed_modes: tuple[str, ...] = ()
    restricted_reason: Optional[str] = None


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "so",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "was",
    "we",
    "with",
    "you",
    "your",
}


class LayeredMemoryService:
    def __init__(self) -> None:
        self.db = get_database()
        self.embeddings = EmbeddingClient()

    async def retrieve_context(
        self,
        user_id: str,
        query: str,
        limit: int = 6,
        assessment: Optional[Assessment] = None,
        conversation_mode: str = "general",
    ) -> List[RetrievedMemory]:
        current_mode = self._normalize_mode(conversation_mode)
        plan = self._build_retrieval_plan(query, assessment)
        query_vector = vector_literal(await self.embeddings.embed_text(query))
        results: List[RetrievedMemory] = []

        episodic = await self._retrieve_episodes(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            limit=plan.episodic_limit,
            include_archived=plan.include_archived,
            status_values=None,
            current_mode=current_mode,
        )
        semantic = await self._retrieve_semantic(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            limit=plan.semantic_limit,
            include_archived=plan.include_archived,
            status_values=None,
            current_mode=current_mode,
        )
        procedural = await self._retrieve_procedural(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            limit=plan.procedural_limit,
            include_archived=plan.include_archived,
            status_values=None,
            current_mode=current_mode,
        )
        graph = await self._retrieve_graph(
            user_id=user_id,
            query=query,
            limit=plan.graph_limit,
            current_mode=current_mode,
        )

        results.extend(self._rebalance_scores(episodic, plan.episodic_weight, query, assessment))
        results.extend(self._rebalance_scores(semantic, plan.semantic_weight, query, assessment))
        results.extend(self._rebalance_scores(procedural, plan.procedural_weight, query, assessment))
        results.extend(self._rebalance_scores(graph, plan.graph_weight, query, assessment))

        reactivated = await self._retrieve_reactivation_candidates(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            limit=plan.reactivation_limit,
            assessment=assessment,
            current_mode=current_mode,
        )
        results.extend(reactivated)

        results.sort(key=lambda item: item.score, reverse=True)

        deduped: List[RetrievedMemory] = []
        seen = set()
        for item in results:
            key = (item.kind, item.content)
            if key in seen or item.score <= 0:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= max(limit * 3, 12):
                break

        selected = self._select_memories_for_prompt(
            deduped,
            query=query,
            assessment=assessment,
            limit=limit,
        )

        await self._reactivate_memories(selected)
        await self._mark_recalled(selected)
        return selected

    async def store_interaction(
        self,
        user_id: str,
        user_input: str,
        agent_response: str,
        assessment: Assessment,
        input_mode: str = "voice",
        conversation_mode: str = "general",
        visibility_scope: Optional[str] = None,
        allowed_modes: Optional[Iterable[str]] = None,
    ) -> None:
        scope = self._resolve_memory_scope(
            user_input=user_input,
            conversation_mode=conversation_mode,
            visibility_scope=visibility_scope,
            allowed_modes=allowed_modes,
        )
        summary = self._build_summary(user_input, agent_response)
        salience = self._compute_salience(user_input, assessment)
        memory_status = "pinned" if self._should_pin(user_input) else "active"
        episode_embedding = vector_literal(await self.embeddings.embed_text(f"{user_input}\n{summary}"))

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO episodes (
                        user_id,
                        timestamp,
                        user_input,
                        agent_response,
                        summary,
                        emotional_tone,
                        salience,
                        memory_status,
                        input_mode,
                        conversation_mode,
                        visibility_scope,
                        allowed_modes,
                        restricted_reason,
                        dialogue_signals,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::vector)
                    RETURNING id::text
                    """,
                    (
                        user_id,
                        self._now(),
                        user_input,
                        agent_response,
                        summary,
                        assessment.emotional_tone,
                        salience,
                        memory_status,
                        input_mode,
                        scope.conversation_mode,
                        scope.visibility_scope,
                        list(scope.allowed_modes),
                        scope.restricted_reason,
                        json.dumps(assessment.dialogue_signals.model_dump()),
                        episode_embedding,
                    ),
                )
                row = await cur.fetchone()
                episode_id = str(row["id"])
            await conn.commit()

        semantic_candidates = self._extract_semantic_candidates(user_input, assessment)
        procedural_candidates = self._extract_procedural_candidates(user_input, assessment)
        graph_facts = self._extract_graph_facts(user_input, semantic_candidates)

        await self._upsert_semantic_candidates(user_id, semantic_candidates, episode_id, scope)
        await self._upsert_procedural_candidates(user_id, procedural_candidates, episode_id, scope)
        await self._update_graph(user_id, graph_facts, episode_id, scope)
        await self._update_dialogue_profile(user_id, episode_id, assessment)
        await self.consolidate_user(user_id)

    async def user_home_location(
        self,
        user_id: str,
        conversation_mode: str = "general",
    ) -> Optional[RetrievedMemory]:
        """Return the strongest current home-location memory, if one exists."""
        current_mode = self._normalize_mode(conversation_mode)
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        content,
                        confidence,
                        memory_status,
                        source_episode_ids,
                        valid_from,
                        valid_to,
                        superseded_by,
                        archive_reason,
                        conversation_mode,
                        visibility_scope,
                        allowed_modes
                    FROM semantic_memories
                    WHERE user_id = %s
                      AND fact_key = 'location:home'
                      AND memory_status IN ('active', 'pinned')
                      AND (
                        visibility_scope = 'global'
                        OR %s = ANY(allowed_modes)
                      )
                    ORDER BY
                        CASE WHEN memory_status = 'pinned' THEN 0 ELSE 1 END,
                        confidence DESC,
                        reinforcement_count DESC,
                        last_updated DESC
                    LIMIT 1
                    """,
                    (user_id, current_mode),
                )
                row = await cur.fetchone()

        if not row:
            return None

        return RetrievedMemory(
            kind="semantic",
            content=str(row["content"]),
            score=1.35,
            source_id=str(row["id"]),
            confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
            memory_status=str(row["memory_status"]) if row.get("memory_status") else None,
            source_episode_ids=[str(value) for value in list(row.get("source_episode_ids") or [])],
            valid_from=row["valid_from"].isoformat() if row.get("valid_from") else None,
            valid_to=row["valid_to"].isoformat() if row.get("valid_to") else None,
            superseded_by=str(row["superseded_by"]) if row.get("superseded_by") else None,
            archive_reason=str(row["archive_reason"]) if row.get("archive_reason") else None,
            conversation_mode=str(row.get("conversation_mode") or "general"),
            visibility_scope=str(row.get("visibility_scope") or "global"),
            allowed_modes=[str(value) for value in list(row.get("allowed_modes") or [])],
            use="silent",
            relevance_reason="identity/location memory for local context",
        )

    async def consolidate_user(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        user_input,
                        emotional_tone,
                        salience,
                        visibility_scope,
                        allowed_modes,
                        conversation_mode
                    FROM episodes
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT 20
                    """,
                    (user_id,),
                )
                recent_episodes = await cur.fetchall()

        if recent_episodes:
            await self._reinforce_recent_semantics(user_id, recent_episodes)
            await self._reinforce_recent_procedurals(user_id, recent_episodes)

        await self._normalize_legacy_semantic_keys(user_id)
        await self._fold_semantic_duplicate_families(user_id)
        await self._resolve_semantic_conflicts(user_id)
        await self._archive_stale_episodes(user_id)
        await self._archive_stale_semantics(user_id)
        await self._archive_stale_procedurals(user_id)
        await self._weaken_stale_graph_edges(user_id)

    async def backfill_semantics_from_episodes(self, user_id: str, limit: int = 80) -> dict[str, int]:
        """
        Re-run the current deterministic extractors against stored episodes.

        This is intentionally different from nightly consolidation: consolidation
        looks for repeated patterns, while backfill repairs facts we now know how
        to extract but may have missed when the episode was first stored.
        """
        capped_limit = max(1, min(int(limit), 500))
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        user_input,
                        emotional_tone,
                        dialogue_signals,
                        visibility_scope,
                        allowed_modes,
                        conversation_mode,
                        restricted_reason
                    FROM episodes
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (user_id, capped_limit),
                )
                episodes = await cur.fetchall()

        semantic_count = 0
        procedural_count = 0
        graph_count = 0

        for episode in episodes:
            assessment = Assessment(
                stakes="low",
                novelty="low",
                emotional_tone=str(episode.get("emotional_tone") or "neutral"),
                dialogue_signals=self._dialogue_signals_from_episode(episode.get("dialogue_signals")),
            )
            scope = MemoryScope(
                conversation_mode=str(episode.get("conversation_mode") or "general"),
                visibility_scope=str(episode.get("visibility_scope") or "global"),
                allowed_modes=tuple(str(mode) for mode in list(episode.get("allowed_modes") or [])),
                restricted_reason=episode.get("restricted_reason"),
            )
            user_input = str(episode.get("user_input") or "")
            episode_id = str(episode["id"])

            semantic_candidates = self._extract_semantic_candidates(user_input, assessment)
            procedural_candidates = self._extract_procedural_candidates(user_input, assessment)
            graph_facts = self._extract_graph_facts(user_input, semantic_candidates)

            await self._upsert_semantic_candidates(user_id, semantic_candidates, episode_id, scope)
            await self._upsert_procedural_candidates(user_id, procedural_candidates, episode_id, scope)
            await self._update_graph(user_id, graph_facts, episode_id, scope)

            semantic_count += len(semantic_candidates)
            procedural_count += len(procedural_candidates)
            graph_count += len(graph_facts)

        await self._normalize_legacy_semantic_keys(user_id)
        await self._fold_semantic_duplicate_families(user_id)
        await self._resolve_semantic_conflicts(user_id)

        return {
            "episodes_scanned": len(episodes),
            "semantic_candidates": semantic_count,
            "procedural_candidates": procedural_count,
            "graph_facts": graph_count,
        }

    async def _update_dialogue_profile(
        self,
        user_id: str,
        episode_id: str,
        assessment: Assessment,
    ) -> None:
        signals = assessment.dialogue_signals
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO dialogue_profiles (
                        user_id,
                        sample_count,
                        avg_words_per_turn,
                        hedging_score,
                        indirectness_score,
                        ramble_score,
                        disfluency_score,
                        filler_rate,
                        self_correction_rate,
                        pause_tolerance_seconds,
                        last_observed_episode_id,
                        last_updated
                    )
                    VALUES (%s, 1, %s, %s, %s, %s, %s, %s, %s, %s, %s::uuid, NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        avg_words_per_turn = (
                            (dialogue_profiles.avg_words_per_turn * dialogue_profiles.sample_count) + EXCLUDED.avg_words_per_turn
                        ) / (dialogue_profiles.sample_count + 1),
                        hedging_score = (dialogue_profiles.hedging_score * 0.8) + (EXCLUDED.hedging_score * 0.2),
                        indirectness_score = (dialogue_profiles.indirectness_score * 0.8) + (EXCLUDED.indirectness_score * 0.2),
                        ramble_score = (dialogue_profiles.ramble_score * 0.8) + (EXCLUDED.ramble_score * 0.2),
                        disfluency_score = (dialogue_profiles.disfluency_score * 0.8) + (EXCLUDED.disfluency_score * 0.2),
                        filler_rate = (dialogue_profiles.filler_rate * 0.8) + (EXCLUDED.filler_rate * 0.2),
                        self_correction_rate = (dialogue_profiles.self_correction_rate * 0.8) + (EXCLUDED.self_correction_rate * 0.2),
                        pause_tolerance_seconds = LEAST(
                            GREATEST(
                                (dialogue_profiles.pause_tolerance_seconds * 0.85) + (EXCLUDED.pause_tolerance_seconds * 0.15),
                                0.75
                            ),
                            1.9
                        ),
                        sample_count = dialogue_profiles.sample_count + 1,
                        last_observed_episode_id = EXCLUDED.last_observed_episode_id,
                        last_updated = NOW()
                    """,
                    (
                        user_id,
                        float(signals.word_count),
                        float(signals.hedging_score),
                        float(signals.indirectness_score),
                        float(signals.ramble_score),
                        float(signals.disfluency_score),
                        float(signals.filler_count) / max(float(signals.word_count), 1.0),
                        float(signals.self_correction_count) / max(float(signals.word_count), 1.0),
                        float(signals.pause_tolerance_seconds),
                        episode_id,
                    ),
                )
            await conn.commit()

    async def pin_memory(self, layer: str, memory_id: str) -> Optional[dict[str, object]]:
        table = self._table_for_layer(layer)
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                if table in {"semantic_memories", "procedural_memories"}:
                    await cur.execute(
                        f"""
                        UPDATE {table}
                        SET memory_status = 'pinned',
                            archive_reason = NULL,
                            archived_at = NULL,
                            valid_to = NULL
                        WHERE id = %s::uuid
                        RETURNING id::text AS id, content, memory_status
                        """,
                        (memory_id,),
                    )
                else:
                    await cur.execute(
                        f"""
                        UPDATE {table}
                        SET memory_status = 'pinned',
                            archive_reason = NULL,
                            archived_at = NULL
                        WHERE id = %s::uuid
                        RETURNING id::text AS id, summary AS content, memory_status
                        """,
                        (memory_id,),
                    )
                row = await cur.fetchone()
            await conn.commit()
        return row

    async def archive_memory(
        self,
        layer: str,
        memory_id: str,
        reason: str = "manual_archive",
    ) -> Optional[dict[str, object]]:
        table = self._table_for_layer(layer)
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                if table in {"semantic_memories", "procedural_memories"}:
                    await cur.execute(
                        f"""
                        UPDATE {table}
                        SET memory_status = 'archived',
                            archive_reason = %s,
                            archived_at = NOW(),
                            valid_to = COALESCE(valid_to, NOW())
                        WHERE id = %s::uuid
                        RETURNING id::text AS id, content, memory_status, archive_reason
                        """,
                        (reason, memory_id),
                    )
                else:
                    await cur.execute(
                        f"""
                        UPDATE {table}
                        SET memory_status = 'archived',
                            archive_reason = %s,
                            archived_at = NOW()
                        WHERE id = %s::uuid
                        RETURNING id::text AS id, summary AS content, memory_status, archive_reason
                        """,
                        (reason, memory_id),
                    )
                row = await cur.fetchone()
            await conn.commit()
        return row

    async def mark_memory_outdated(self, layer: str, memory_id: str) -> Optional[dict[str, object]]:
        return await self.archive_memory(layer=layer, memory_id=memory_id, reason="outdated")

    async def correct_memory(
        self,
        layer: str,
        memory_id: str,
        new_content: str,
        replacement_key: Optional[str] = None,
    ) -> Optional[dict[str, object]]:
        table = self._table_for_layer(layer)
        if table not in {"semantic_memories", "procedural_memories"}:
            raise ValueError("Corrections are only supported for semantic and procedural memory.")

        content_column = "content"
        key_column = "fact_key" if table == "semantic_memories" else "pattern_key"
        category_sql = "category," if table == "semantic_memories" else ""
        category_select = "category," if table == "semantic_memories" else ""
        category_values = "%s," if table == "semantic_memories" else ""

        embedding = vector_literal(await self.embeddings.embed_text(new_content))

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    SELECT
                        id::text AS id,
                        user_id,
                        {content_column} AS content,
                        {category_select}
                        {key_column},
                        confidence,
                        reinforcement_count,
                        recall_count,
                        memory_status,
                        source_episode_ids
                    FROM {table}
                    WHERE id = %s::uuid
                    """,
                    (memory_id,),
                )
                existing = await cur.fetchone()
                if not existing:
                    return None

                key_value = replacement_key or existing.get(key_column)
                insert_params: list[object] = [
                    existing["user_id"],
                    new_content,
                ]
                if table == "semantic_memories":
                    insert_params.append(existing["category"])
                insert_params.extend(
                    [
                        key_value,
                        max(float(existing["confidence"]), 0.84),
                        int(existing["reinforcement_count"]),
                        int(existing["recall_count"]),
                        list(existing.get("source_episode_ids") or []),
                        embedding,
                    ]
                )
                await cur.execute(
                    f"""
                    INSERT INTO {table} (
                        user_id,
                        content,
                        {category_sql}
                        {key_column},
                        confidence,
                        reinforcement_count,
                        recall_count,
                        memory_status,
                        archive_reason,
                        archived_at,
                        source_episode_ids,
                        valid_from,
                        valid_to,
                        superseded_by,
                        embedding
                    )
                    VALUES (
                        %s,
                        %s,
                        {category_values}
                        %s,
                        %s,
                        %s,
                        %s,
                        'active',
                        NULL,
                        NULL,
                        %s,
                        NOW(),
                        NULL,
                        NULL,
                        %s::vector
                    )
                    RETURNING id::text AS id, content, memory_status
                    """,
                    tuple(insert_params),
                )
                inserted = await cur.fetchone()

                await cur.execute(
                    f"""
                    UPDATE {table}
                    SET memory_status = 'archived',
                        archive_reason = 'corrected',
                        archived_at = NOW(),
                        valid_to = NOW(),
                        superseded_by = %s::uuid
                    WHERE id = %s::uuid
                    """,
                    (inserted["id"], memory_id),
                )
            await conn.commit()
        return inserted

    async def merge_memories(self, layer: str, source_id: str, target_id: str) -> Optional[dict[str, object]]:
        table = self._table_for_layer(layer)
        if table not in {"semantic_memories", "procedural_memories"}:
            raise ValueError("Merging is only supported for semantic and procedural memory.")

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    f"""
                    SELECT
                        id::text AS id,
                        content,
                        confidence,
                        reinforcement_count,
                        recall_count,
                        memory_status,
                        source_episode_ids
                    FROM {table}
                    WHERE id = ANY(%s::uuid[])
                    """,
                    ([source_id, target_id],),
                )
                rows = await cur.fetchall()
                by_id = {str(row["id"]): row for row in rows}
                source = by_id.get(source_id)
                target = by_id.get(target_id)
                if not source or not target:
                    return None

                combined_source_ids = sorted(
                    {
                        str(value)
                        for value in list(source.get("source_episode_ids") or []) + list(target.get("source_episode_ids") or [])
                    }
                )
                await cur.execute(
                    f"""
                    UPDATE {table}
                    SET confidence = GREATEST(confidence, %s),
                        reinforcement_count = reinforcement_count + %s,
                        recall_count = recall_count + %s,
                        memory_status = CASE
                            WHEN memory_status = 'pinned' OR %s = 'pinned' THEN 'pinned'
                            ELSE 'active'
                        END,
                        archive_reason = NULL,
                        archived_at = NULL,
                        valid_to = NULL,
                        source_episode_ids = %s,
                        last_updated = NOW()
                    WHERE id = %s::uuid
                    RETURNING id::text AS id, content, memory_status
                    """,
                    (
                        float(source["confidence"]),
                        int(source["reinforcement_count"]),
                        int(source["recall_count"]),
                        str(source["memory_status"]),
                        combined_source_ids,
                        target_id,
                    ),
                )
                updated = await cur.fetchone()

                await cur.execute(
                    f"""
                    UPDATE {table}
                    SET memory_status = 'archived',
                        archive_reason = 'merged',
                        archived_at = NOW(),
                        valid_to = NOW(),
                        superseded_by = %s::uuid
                    WHERE id = %s::uuid
                    """,
                    (target_id, source_id),
                )
            await conn.commit()
        return updated

    async def run_retrieval_evals(self, user_id: str) -> dict[str, object]:
        scenarios = [
            {
                "name": "goal-query",
                "query": "what is my main goal right now?",
                "assessment": Assessment(stakes="low", novelty="low", emotional_tone="neutral"),
                "check": lambda results: any(
                    memory.kind in {"semantic", "graph"}
                    and any(marker in memory.content.lower() for marker in ["goal", "wants to", "building", "working on"])
                    for memory in results[:3]
                ),
            },
            {
                "name": "stress-query",
                "query": "how should you respond when i am stressed?",
                "assessment": Assessment(stakes="low", novelty="low", emotional_tone="stressed"),
                "check": lambda results: any(
                    memory.kind in {"semantic", "procedural"}
                    and any(marker in memory.content.lower() for marker in ["stress", "grounding", "concise", "calm"])
                    for memory in results[:3]
                ),
            },
            {
                "name": "person-query",
                "query": "who am i connected to?",
                "assessment": Assessment(stakes="low", novelty="low", emotional_tone="neutral"),
                "check": lambda results: any(memory.kind == "graph" for memory in results[:3]),
            },
            {
                "name": "change-query",
                "query": "what changed about me recently?",
                "assessment": Assessment(stakes="low", novelty="medium", emotional_tone="neutral"),
                "check": lambda results: any(memory.memory_status == "archived" or memory.valid_to for memory in results[:4]),
            },
            {
                "name": "archive-recall",
                "query": "what did i tell you before that might matter again?",
                "assessment": Assessment(stakes="low", novelty="medium", emotional_tone="neutral"),
                "check": lambda results: any(memory.memory_status == "archived" or memory.valid_to for memory in results[:4]),
            },
        ]

        scenario_results: list[dict[str, object]] = []
        passed = 0
        for scenario in scenarios:
            results = await self.retrieve_context(
                user_id=user_id,
                query=str(scenario["query"]),
                limit=5,
                assessment=scenario["assessment"],
            )
            result_payload = [memory.model_dump() for memory in results[:4]]
            ok = bool(scenario["check"](results))
            if ok:
                passed += 1
            scenario_results.append(
                {
                    "name": scenario["name"],
                    "query": scenario["query"],
                    "passed": ok,
                    "top_results": result_payload,
                }
            )

        return {
            "user_id": user_id,
            "passed": passed,
            "total": len(scenarios),
            "results": scenario_results,
        }

    async def dialogue_profile(self, user_id: str) -> dict[str, object]:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        user_id,
                        sample_count,
                        avg_words_per_turn,
                        hedging_score,
                        indirectness_score,
                        ramble_score,
                        disfluency_score,
                        filler_rate,
                        self_correction_rate,
                        pause_tolerance_seconds,
                        last_observed_episode_id::text AS last_observed_episode_id,
                        last_updated
                    FROM dialogue_profiles
                    WHERE user_id = %s
                    """,
                        (user_id,),
                    )
                row = await cur.fetchone()

        if not row:
            return {
                "user_id": user_id,
                "sample_count": 0,
                "avg_words_per_turn": 0.0,
                "hedging_score": 0.0,
                "indirectness_score": 0.0,
                "ramble_score": 0.0,
                "disfluency_score": 0.0,
                "filler_rate": 0.0,
                "self_correction_rate": 0.0,
                "pause_tolerance_seconds": 0.9,
                "last_observed_episode_id": None,
                "last_updated": None,
            }

        return {
            "user_id": str(row["user_id"]),
            "sample_count": int(row["sample_count"]),
            "avg_words_per_turn": float(row["avg_words_per_turn"]),
            "hedging_score": float(row["hedging_score"]),
            "indirectness_score": float(row["indirectness_score"]),
            "ramble_score": float(row["ramble_score"]),
            "disfluency_score": float(row["disfluency_score"]),
            "filler_rate": float(row["filler_rate"]),
            "self_correction_rate": float(row["self_correction_rate"]),
            "pause_tolerance_seconds": float(row["pause_tolerance_seconds"]),
            "last_observed_episode_id": row["last_observed_episode_id"],
            "last_updated": row["last_updated"].isoformat() if row["last_updated"] else None,
        }

    def _dialogue_signals_from_episode(self, raw_signals: object) -> DialogueSignals:
        if isinstance(raw_signals, DialogueSignals):
            return raw_signals
        if isinstance(raw_signals, dict):
            return DialogueSignals.model_validate(raw_signals)
        if isinstance(raw_signals, str) and raw_signals:
            try:
                parsed = json.loads(raw_signals)
            except json.JSONDecodeError:
                return DialogueSignals()
            if isinstance(parsed, dict):
                return DialogueSignals.model_validate(parsed)
        return DialogueSignals()

    async def stats(self, user_id: str) -> dict[str, int]:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                tables = {
                    "episodes": "episodes",
                    "semantic": "semantic_memories",
                    "procedural": "procedural_memories",
                    "graph_nodes": "graph_nodes",
                    "graph_edges": "graph_edges",
                }
                counts = {}
                for key, table in tables.items():
                    await cur.execute(f"SELECT COUNT(*) AS total FROM {table} WHERE user_id = %s", (user_id,))
                    row = await cur.fetchone()
                    counts[key] = int(row["total"])
        return counts

    async def atlas_snapshot(self, user_id: str, conversation_mode: str = "general") -> dict[str, object]:
        current_mode = self._normalize_mode(conversation_mode)
        stats = await self.stats(user_id)
        dialogue_profile = await self.dialogue_profile(user_id)

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        content,
                        category,
                        fact_key,
                        confidence,
                        reinforcement_count,
                        recall_count,
                        memory_status,
                        archive_reason,
                        source_episode_ids,
                        valid_from,
                        valid_to,
                        superseded_by,
                        last_updated
                    FROM semantic_memories
                    WHERE user_id = %s
                      AND (
                        visibility_scope = 'global'
                        OR %s = ANY(allowed_modes)
                      )
                    ORDER BY
                        CASE
                            WHEN memory_status = 'pinned' THEN 0
                            WHEN memory_status = 'active' THEN 1
                            ELSE 2
                        END,
                        confidence DESC,
                        reinforcement_count DESC,
                        last_updated DESC
                    LIMIT 18
                    """,
                    (user_id, current_mode),
                )
                semantic_rows = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        content,
                        pattern_key,
                        confidence,
                        reinforcement_count,
                        recall_count,
                        memory_status,
                        archive_reason,
                        source_episode_ids,
                        valid_from,
                        valid_to,
                        superseded_by,
                        last_updated
                    FROM procedural_memories
                    WHERE user_id = %s
                      AND (
                        visibility_scope = 'global'
                        OR %s = ANY(allowed_modes)
                      )
                    ORDER BY
                        CASE
                            WHEN memory_status = 'pinned' THEN 0
                            WHEN memory_status = 'active' THEN 1
                            ELSE 2
                        END,
                        confidence DESC,
                        reinforcement_count DESC,
                        last_updated DESC
                    LIMIT 10
                    """,
                    (user_id, current_mode),
                )
                procedural_rows = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        timestamp,
                        user_input,
                        summary,
                        emotional_tone,
                        salience,
                        recall_count,
                        memory_status,
                        dialogue_signals
                    FROM episodes
                    WHERE user_id = %s
                      AND (
                        visibility_scope = 'global'
                        OR %s = ANY(allowed_modes)
                      )
                    ORDER BY timestamp DESC
                    LIMIT 14
                    """,
                    (user_id, current_mode),
                )
                episode_rows = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT
                        e.id::text AS id,
                        source.label AS source_label,
                        target.label AS target_label,
                        e.relation,
                        e.weight,
                        e.recall_count,
                        e.source_episode_ids,
                        e.edge_status,
                        e.valid_from,
                        e.valid_to,
                        e.created_at,
                        e.last_seen
                    FROM graph_edges e
                    JOIN graph_nodes source ON source.id = e.source_node_id
                    JOIN graph_nodes target ON target.id = e.target_node_id
                    WHERE e.user_id = %s
                      AND (
                        e.visibility_scope = 'global'
                        OR %s = ANY(e.allowed_modes)
                      )
                    ORDER BY e.weight DESC, e.last_seen DESC
                    LIMIT 12
                    """,
                    (user_id, current_mode),
                )
                relation_rows = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT memory_status, COUNT(*) AS total
                    FROM (
                        SELECT memory_status FROM episodes
                        WHERE user_id = %s AND (visibility_scope = 'global' OR %s = ANY(allowed_modes))
                        UNION ALL
                        SELECT memory_status FROM semantic_memories
                        WHERE user_id = %s AND (visibility_scope = 'global' OR %s = ANY(allowed_modes))
                        UNION ALL
                        SELECT memory_status FROM procedural_memories
                        WHERE user_id = %s AND (visibility_scope = 'global' OR %s = ANY(allowed_modes))
                    ) AS all_memories
                    GROUP BY memory_status
                    """,
                    (user_id, current_mode, user_id, current_mode, user_id, current_mode),
                )
                status_counts_rows = await cur.fetchall()

        evidence_rows = await self._load_evidence_episodes(semantic_rows, procedural_rows)
        nodes = self._build_atlas_nodes(semantic_rows, procedural_rows)
        evidence_by_memory = self._group_evidence_by_memory(semantic_rows, procedural_rows, evidence_rows)

        return {
            "user_id": user_id,
            "generated_at": self._now().isoformat(),
            "summary": {
                **stats,
                "dialogue_profile": dialogue_profile,
                "status_counts": {
                    str(row["memory_status"]): int(row["total"])
                    for row in status_counts_rows
                },
            },
            "map": {
                "nodes": nodes,
                "edges": self._build_atlas_edges(nodes),
                "relations": [
                    {
                        "id": str(row["id"]),
                        "source_label": str(row["source_label"]),
                        "target_label": str(row["target_label"]),
                        "relation": str(row["relation"]),
                        "weight": float(row["weight"]),
                        "recall_count": int(row["recall_count"]),
                        "source_episode_ids": [str(value) for value in list(row.get("source_episode_ids") or [])],
                        "status": str(row["edge_status"]),
                        "valid_from": row["valid_from"].isoformat() if row["valid_from"] else None,
                        "valid_to": row["valid_to"].isoformat() if row["valid_to"] else None,
                        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                        "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
                    }
                    for row in relation_rows
                ],
            },
            "timeline": [
                {
                    "id": str(row["id"]),
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "title": self._atlas_episode_title(str(row["user_input"])),
                    "summary": str(row["summary"]),
                    "emotional_tone": str(row["emotional_tone"]),
                    "salience": float(row["salience"]),
                    "recall_count": int(row["recall_count"]),
                    "memory_status": str(row["memory_status"]),
                    "dialogue_signals": row.get("dialogue_signals") or {},
                }
                for row in episode_rows
            ],
            "evidence": evidence_by_memory,
        }

    async def conversation_feed(
        self,
        user_id: str,
        limit: int = 40,
        conversation_mode: str = "general",
    ) -> dict[str, object]:
        safe_limit = max(1, min(limit, 200))
        current_mode = self._normalize_mode(conversation_mode)

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        timestamp,
                        user_input,
                        agent_response,
                        summary,
                        emotional_tone,
                        salience,
                        memory_status,
                        input_mode
                    FROM episodes
                    WHERE user_id = %s
                      AND (
                        visibility_scope = 'global'
                        OR %s = ANY(allowed_modes)
                      )
                    ORDER BY timestamp DESC
                    LIMIT %s
                    """,
                    (user_id, current_mode, safe_limit),
                )
                rows = await cur.fetchall()

        episodes = list(reversed(rows))
        turns: list[dict[str, object]] = []

        for row in episodes:
            episode_id = str(row["id"])
            timestamp = row["timestamp"].isoformat() if row["timestamp"] else None
            input_mode = str(row.get("input_mode") or "voice")

            turns.append(
                {
                    "id": f"{episode_id}:user",
                    "episode_id": episode_id,
                    "role": "user",
                    "input_mode": input_mode,
                    "text": str(row["user_input"] or ""),
                    "timestamp": timestamp,
                    "emotional_tone": str(row["emotional_tone"] or "neutral"),
                    "salience": float(row["salience"] or 0),
                    "memory_status": str(row["memory_status"] or "active"),
                    "summary": str(row["summary"] or ""),
                }
            )
            turns.append(
                {
                    "id": f"{episode_id}:assistant",
                    "episode_id": episode_id,
                    "role": "assistant",
                    "input_mode": input_mode,
                    "text": str(row["agent_response"] or ""),
                    "timestamp": timestamp,
                    "emotional_tone": str(row["emotional_tone"] or "neutral"),
                    "salience": float(row["salience"] or 0),
                    "memory_status": str(row["memory_status"] or "active"),
                    "summary": str(row["summary"] or ""),
                }
            )

        return {
            "user_id": user_id,
            "generated_at": self._now().isoformat(),
            "episodes": len(episodes),
            "turns": turns,
        }

    async def mutation_feed(
        self,
        user_id: str,
        limit: int = 80,
        conversation_mode: str = "general",
    ) -> dict[str, object]:
        safe_limit = max(1, min(limit, 300))
        current_mode = self._normalize_mode(conversation_mode)

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        memory_layer,
                        memory_id::text AS memory_id,
                        action,
                        reason,
                        source_episode_id,
                        from_status,
                        to_status,
                        conversation_mode,
                        visibility_scope,
                        allowed_modes,
                        metadata,
                        created_at
                    FROM memory_mutations
                    WHERE user_id = %s
                      AND (
                        visibility_scope = 'global'
                        OR %s = ANY(allowed_modes)
                      )
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (user_id, current_mode, safe_limit),
                )
                rows = await cur.fetchall()

        return {
            "user_id": user_id,
            "generated_at": self._now().isoformat(),
            "mutations": [
                {
                    "id": str(row["id"]),
                    "memory_layer": str(row["memory_layer"]),
                    "memory_id": str(row["memory_id"]) if row["memory_id"] else None,
                    "action": str(row["action"]),
                    "reason": str(row["reason"]) if row["reason"] else None,
                    "source_episode_id": str(row["source_episode_id"]) if row["source_episode_id"] else None,
                    "from_status": str(row["from_status"]) if row["from_status"] else None,
                    "to_status": str(row["to_status"]) if row["to_status"] else None,
                    "conversation_mode": str(row["conversation_mode"]),
                    "visibility_scope": str(row["visibility_scope"]),
                    "allowed_modes": [str(value) for value in list(row["allowed_modes"] or [])],
                    "metadata": row.get("metadata") or {},
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                }
                for row in rows
            ],
        }

    async def _retrieve_episodes(
        self,
        user_id: str,
        query: str,
        query_vector: Optional[str],
        limit: int,
        include_archived: bool,
        status_values: Optional[tuple[str, ...]],
        current_mode: str = "general",
    ) -> List[RetrievedMemory]:
        sql, params = self._hybrid_memory_query(
            table="episodes",
            content_column="summary",
            time_column="timestamp",
            base_where="user_id = %s",
            query=query,
            query_vector=query_vector,
            user_id=user_id,
            limit=limit,
            include_archived=include_archived,
            status_values=status_values,
            current_mode=current_mode,
            recency_window_days=21,
            recency_weight=0.12,
            extra_select="""
                salience AS confidence,
                memory_status,
                ARRAY[]::text[] AS source_episode_ids,
                timestamp AS valid_from,
                archived_at AS valid_to,
                NULL::uuid AS superseded_by,
                archive_reason,
                conversation_mode,
                visibility_scope,
                allowed_modes
            """,
            extra_score="""
                + salience * 0.14
                + CASE WHEN memory_status = 'pinned' THEN 0.22 ELSE 0 END
                + LEAST(stability / 16.0, 0.12)
                + LEAST(recall_count * 0.03, 0.14)
                + CASE WHEN memory_status = 'archived' THEN -0.12 ELSE 0 END
            """,
        )
        return await self._run_retrieval_query(sql, params, kind="episodic")

    async def _retrieve_semantic(
        self,
        user_id: str,
        query: str,
        query_vector: Optional[str],
        limit: int,
        include_archived: bool,
        status_values: Optional[tuple[str, ...]],
        current_mode: str = "general",
    ) -> List[RetrievedMemory]:
        sql, params = self._hybrid_memory_query(
            table="semantic_memories",
            content_column="content",
            time_column="last_updated",
            base_where="user_id = %s",
            query=query,
            query_vector=query_vector,
            user_id=user_id,
            limit=limit,
            include_archived=include_archived,
            status_values=status_values,
            current_mode=current_mode,
            recency_window_days=45,
            recency_weight=0.08,
            extra_select="""
                confidence,
                memory_status,
                source_episode_ids,
                valid_from,
                valid_to,
                superseded_by,
                archive_reason,
                conversation_mode,
                visibility_scope,
                allowed_modes
            """,
            extra_score="""
                + confidence * 0.18
                + LEAST(reinforcement_count * 0.04, 0.16)
                + LEAST(recall_count * 0.025, 0.12)
                + CASE WHEN memory_status = 'pinned' THEN 0.16 ELSE 0 END
                + CASE WHEN memory_status = 'archived' THEN -0.10 ELSE 0 END
            """,
        )
        return await self._run_retrieval_query(sql, params, kind="semantic")

    async def _retrieve_procedural(
        self,
        user_id: str,
        query: str,
        query_vector: Optional[str],
        limit: int,
        include_archived: bool,
        status_values: Optional[tuple[str, ...]],
        current_mode: str = "general",
    ) -> List[RetrievedMemory]:
        sql, params = self._hybrid_memory_query(
            table="procedural_memories",
            content_column="content",
            time_column="last_updated",
            base_where="user_id = %s",
            query=query,
            query_vector=query_vector,
            user_id=user_id,
            limit=limit,
            include_archived=include_archived,
            status_values=status_values,
            current_mode=current_mode,
            recency_window_days=60,
            recency_weight=0.07,
            extra_select="""
                confidence,
                memory_status,
                source_episode_ids,
                valid_from,
                valid_to,
                superseded_by,
                archive_reason,
                conversation_mode,
                visibility_scope,
                allowed_modes
            """,
            extra_score="""
                + confidence * 0.20
                + LEAST(reinforcement_count * 0.05, 0.18)
                + LEAST(recall_count * 0.03, 0.12)
                + CASE WHEN memory_status = 'pinned' THEN 0.14 ELSE 0 END
                + CASE WHEN memory_status = 'archived' THEN -0.08 ELSE 0 END
            """,
        )
        return await self._run_retrieval_query(sql, params, kind="procedural")

    async def _retrieve_graph(
        self,
        user_id: str,
        query: str,
        limit: int,
        current_mode: str = "general",
    ) -> List[RetrievedMemory]:
        query_pattern = f"%{query.lower()}%"
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        e.id::text AS id,
                        source.label || ' ' || e.relation || ' ' || target.label AS content,
                        e.weight,
                        e.recall_count,
                        e.source_episode_ids,
                        e.valid_from,
                        e.valid_to,
                        e.conversation_mode,
                        e.visibility_scope,
                        e.allowed_modes,
                        (
                            e.weight
                            + LEAST(e.recall_count * 0.03, 0.1)
                            + (
                                1.0 / (
                                    1.0 + GREATEST(EXTRACT(EPOCH FROM (NOW() - e.last_seen)) / 86400.0, 0) / 90.0
                                )
                              ) * 0.08
                            + CASE
                                WHEN lower(source.label) LIKE %s OR lower(target.label) LIKE %s
                                THEN 0.28
                                ELSE 0
                              END
                            + CASE
                                WHEN lower(e.relation) LIKE %s THEN 0.12
                                ELSE 0
                              END
                        ) AS score
                    FROM graph_edges e
                    JOIN graph_nodes source ON source.id = e.source_node_id
                    JOIN graph_nodes target ON target.id = e.target_node_id
                    WHERE e.user_id = %s
                      AND e.edge_status = 'active'
                      AND (
                        e.visibility_scope = 'global'
                        OR %s = ANY(e.allowed_modes)
                      )
                      AND (
                        lower(source.label) LIKE %s
                        OR lower(target.label) LIKE %s
                        OR lower(e.relation) LIKE %s
                      )
                    ORDER BY score DESC, e.last_seen DESC
                    LIMIT %s
                    """,
                    (
                        query_pattern,
                        query_pattern,
                        query_pattern,
                        user_id,
                        current_mode,
                        query_pattern,
                        query_pattern,
                        query_pattern,
                        limit,
                    ),
                )
                rows = await cur.fetchall()

        return [
            RetrievedMemory(
                kind="graph",
                content=row["content"],
                score=float(row["score"]),
                source_id=str(row["id"]),
                confidence=min(float(row["weight"]) + (int(row["recall_count"]) * 0.03), 1.0),
                memory_status="active",
                source_episode_ids=[str(value) for value in list(row.get("source_episode_ids") or [])],
                valid_from=row["valid_from"].isoformat() if row.get("valid_from") else None,
                valid_to=row["valid_to"].isoformat() if row.get("valid_to") else None,
                conversation_mode=str(row.get("conversation_mode") or "general"),
                visibility_scope=str(row.get("visibility_scope") or "global"),
                allowed_modes=[str(value) for value in list(row.get("allowed_modes") or [])],
            )
            for row in rows
            if float(row["score"]) > 0
        ]

    async def _run_retrieval_query(self, sql: str, params: tuple, kind: str) -> List[RetrievedMemory]:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()

        return [
            RetrievedMemory(
                kind=kind,
                content=row["content"],
                score=float(row["score"]),
                source_id=str(row["id"]),
                confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
                memory_status=str(row["memory_status"]) if row.get("memory_status") else None,
                source_episode_ids=[str(value) for value in list(row.get("source_episode_ids") or [])],
                valid_from=row["valid_from"].isoformat() if row.get("valid_from") else None,
                valid_to=row["valid_to"].isoformat() if row.get("valid_to") else None,
                superseded_by=str(row["superseded_by"]) if row.get("superseded_by") else None,
                archive_reason=str(row["archive_reason"]) if row.get("archive_reason") else None,
                conversation_mode=str(row.get("conversation_mode") or "general"),
                visibility_scope=str(row.get("visibility_scope") or "global"),
                allowed_modes=[str(value) for value in list(row.get("allowed_modes") or [])],
            )
            for row in rows
            if float(row["score"]) > 0
        ]

    def _hybrid_memory_query(
        self,
        table: str,
        content_column: str,
        time_column: str,
        base_where: str,
        query: str,
        query_vector: Optional[str],
        user_id: str,
        limit: int,
        include_archived: bool,
        status_values: Optional[tuple[str, ...]],
        recency_window_days: int,
        recency_weight: float,
        extra_select: str,
        extra_score: str,
        current_mode: str = "general",
    ) -> tuple:
        effective_status_values = status_values or (
            ("active", "pinned", "archived") if include_archived else ("active", "pinned")
        )
        recency_sql = f"""
            (
                1.0 / (
                    1.0 + GREATEST(EXTRACT(EPOCH FROM (NOW() - {time_column})) / 86400.0, 0) / {float(recency_window_days)}
                )
            ) * {float(recency_weight)}
        """

        if query_vector:
            sql = f"""
                SELECT
                    id::text AS id,
                    {content_column} AS content,
                    {extra_select},
                    (
                        CASE
                            WHEN embedding IS NOT NULL THEN (1 - (embedding <=> %s::vector)) * 0.56
                            ELSE 0
                        END
                        + ts_rank_cd(search_tsv, websearch_to_tsquery('english', %s)) * 0.18
                        + {recency_sql}
                        {extra_score}
                    ) AS score
                FROM {table}
                WHERE {base_where}
                  AND memory_status = ANY(%s)
                  AND (
                    visibility_scope = 'global'
                    OR %s = ANY(allowed_modes)
                  )
                ORDER BY score DESC
                LIMIT %s
            """
            params = (query_vector, query, user_id, list(effective_status_values), current_mode, limit)
        else:
            sql = f"""
                SELECT
                    id::text AS id,
                    {content_column} AS content,
                    {extra_select},
                    (
                        ts_rank_cd(search_tsv, websearch_to_tsquery('english', %s)) * 0.74
                        + {recency_sql}
                        {extra_score}
                    ) AS score
                FROM {table}
                WHERE {base_where}
                  AND memory_status = ANY(%s)
                  AND (
                    visibility_scope = 'global'
                    OR %s = ANY(allowed_modes)
                  )
                ORDER BY score DESC
                LIMIT %s
            """
            params = (query, user_id, list(effective_status_values), current_mode, limit)
        return sql, params

    async def _mark_recalled(self, memories: Iterable[RetrievedMemory]) -> None:
        episodic_ids = [memory.source_id for memory in memories if memory.kind == "episodic"]
        semantic_ids = [memory.source_id for memory in memories if memory.kind == "semantic"]
        procedural_ids = [memory.source_id for memory in memories if memory.kind == "procedural"]
        graph_ids = [memory.source_id for memory in memories if memory.kind == "graph"]

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                if episodic_ids:
                    await cur.execute(
                        """
                        UPDATE episodes
                        SET recall_count = recall_count + 1,
                            stability = LEAST(stability + 0.45, 10.0)
                        WHERE id = ANY(%s::uuid[])
                        """,
                        (episodic_ids,),
                    )
                if semantic_ids:
                    await cur.execute(
                        """
                        UPDATE semantic_memories
                        SET recall_count = recall_count + 1,
                            confidence = LEAST(confidence + 0.01, 0.99),
                            last_updated = NOW()
                        WHERE id = ANY(%s::uuid[])
                        """,
                        (semantic_ids,),
                    )
                if procedural_ids:
                    await cur.execute(
                        """
                        UPDATE procedural_memories
                        SET recall_count = recall_count + 1,
                            confidence = LEAST(confidence + 0.01, 0.98),
                            last_updated = NOW()
                        WHERE id = ANY(%s::uuid[])
                        """,
                        (procedural_ids,),
                    )
                if graph_ids:
                    await cur.execute(
                        """
                        UPDATE graph_edges
                        SET recall_count = recall_count + 1,
                            weight = LEAST(weight + 0.02, 1.0),
                            last_seen = NOW()
                        WHERE id = ANY(%s::uuid[])
                        """,
                        (graph_ids,),
                    )
            await conn.commit()

    async def _retrieve_reactivation_candidates(
        self,
        user_id: str,
        query: str,
        query_vector: Optional[str],
        limit: int,
        assessment: Optional[Assessment],
        current_mode: str = "general",
    ) -> List[RetrievedMemory]:
        if limit <= 0:
            return []

        if not assessment and not any(marker in query.lower() for marker in ["remember", "earlier", "before"]):
            return []

        emotional_reactivation = bool(
            assessment and assessment.emotional_tone in {"stressed", "grief", "frustrated", "sad"}
        )
        archived_semantic = await self._retrieve_semantic(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            limit=2,
            include_archived=True,
            status_values=("archived",),
            current_mode=current_mode,
        )
        archived_procedural = await self._retrieve_procedural(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            limit=2,
            include_archived=True,
            status_values=("archived",),
            current_mode=current_mode,
        )
        archived_episodic = await self._retrieve_episodes(
            user_id=user_id,
            query=query,
            query_vector=query_vector,
            limit=1,
            include_archived=True,
            status_values=("archived",),
            current_mode=current_mode,
        )

        candidates: list[RetrievedMemory] = []
        for memory in archived_semantic + archived_procedural + archived_episodic:
            if memory.archive_reason in {"superseded", "outdated", "wrong"}:
                continue
            threshold = 0.64
            if memory.kind in {"semantic", "procedural"} and emotional_reactivation:
                threshold = 0.56
            if memory.score < threshold:
                continue
            candidates.append(memory.model_copy(update={"score": memory.score + 0.06}))

        candidates.sort(key=lambda item: item.score, reverse=True)
        return candidates[:limit]

    async def _reactivate_memories(self, memories: Iterable[RetrievedMemory]) -> None:
        episodic_ids = [
            memory.source_id
            for memory in memories
            if memory.kind == "episodic" and memory.memory_status == "archived" and memory.archive_reason not in {"superseded", "outdated", "wrong"}
        ]
        semantic_ids = [
            memory.source_id
            for memory in memories
            if memory.kind == "semantic" and memory.memory_status == "archived" and memory.archive_reason not in {"superseded", "outdated", "wrong"}
        ]
        procedural_ids = [
            memory.source_id
            for memory in memories
            if memory.kind == "procedural" and memory.memory_status == "archived" and memory.archive_reason not in {"superseded", "outdated", "wrong"}
        ]

        if not any([episodic_ids, semantic_ids, procedural_ids]):
            return

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                if episodic_ids:
                    await cur.execute(
                        """
                        UPDATE episodes
                        SET memory_status = 'active',
                            archive_reason = NULL,
                            archived_at = NULL
                        WHERE id = ANY(%s::uuid[])
                        """,
                        (episodic_ids,),
                    )
                if semantic_ids:
                    await cur.execute(
                        """
                        UPDATE semantic_memories
                        SET memory_status = 'active',
                            archive_reason = NULL,
                            archived_at = NULL,
                            valid_to = NULL,
                            last_updated = NOW()
                        WHERE id = ANY(%s::uuid[])
                        """,
                        (semantic_ids,),
                    )
                if procedural_ids:
                    await cur.execute(
                        """
                        UPDATE procedural_memories
                        SET memory_status = 'active',
                            archive_reason = NULL,
                            archived_at = NULL,
                            valid_to = NULL,
                            last_updated = NOW()
                        WHERE id = ANY(%s::uuid[])
                        """,
                        (procedural_ids,),
                    )
            await conn.commit()

    async def _upsert_semantic_candidates(
        self,
        user_id: str,
        candidates: List[SemanticCandidate],
        episode_id: str,
        scope: MemoryScope,
    ) -> None:
        if not candidates:
            return

        candidates = [self._canonicalize_semantic_candidate(candidate) for candidate in candidates]

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                for candidate in candidates:
                    embedding = vector_literal(await self.embeddings.embed_text(candidate.content))
                    await cur.execute(
                        """
                        SELECT id::text AS id, content, memory_status, source_episode_ids, fact_key
                        FROM semantic_memories
                        WHERE user_id = %s
                          AND visibility_scope = %s
                          AND allowed_modes = %s::text[]
                          AND (
                            content = %s
                            OR (fact_key IS NOT NULL AND fact_key = %s)
                            OR lower(content) = lower(%s)
                          )
                        ORDER BY
                          CASE
                            WHEN fact_key IS NOT NULL AND fact_key = %s THEN 0
                            WHEN content = %s THEN 1
                            WHEN lower(content) = lower(%s) THEN 2
                            ELSE 3
                          END,
                          CASE WHEN memory_status = 'pinned' THEN 0 ELSE 1 END,
                          reinforcement_count DESC,
                          last_updated DESC
                        LIMIT 1
                        """,
                        (
                            user_id,
                            scope.visibility_scope,
                            list(scope.allowed_modes),
                            candidate.content,
                            candidate.fact_key,
                            candidate.content,
                            candidate.fact_key,
                            candidate.content,
                            candidate.content,
                        ),
                    )
                    existing = await cur.fetchone()
                    if existing and (
                        str(existing["content"]) == candidate.content
                        or str(existing.get("fact_key") or "") == candidate.fact_key
                    ):
                        source_ids = list(existing["source_episode_ids"] or [])
                        if episode_id not in source_ids:
                            source_ids.append(episode_id)
                        await cur.execute(
                            """
                            UPDATE semantic_memories
                            SET reinforcement_count = reinforcement_count + 1,
                                confidence = LEAST(confidence + 0.05, 0.99),
                                memory_status = CASE WHEN memory_status = 'pinned' THEN 'pinned' ELSE 'active' END,
                                source_episode_ids = %s,
                                conversation_mode = %s,
                                visibility_scope = %s,
                                allowed_modes = %s,
                                restricted_reason = %s,
                                fact_key = %s,
                                content = CASE WHEN memory_status = 'pinned' THEN content ELSE %s END,
                                category = %s,
                                archive_reason = NULL,
                                archived_at = NULL,
                                valid_to = NULL,
                                superseded_by = NULL,
                                last_updated = NOW(),
                                embedding = COALESCE(%s::vector, embedding)
                            WHERE id = %s::uuid
                            """,
                            (
                                source_ids,
                                scope.conversation_mode,
                                scope.visibility_scope,
                                list(scope.allowed_modes),
                                scope.restricted_reason,
                                candidate.fact_key,
                                candidate.content,
                                candidate.category,
                                embedding,
                                existing["id"],
                            ),
                        )
                        await self._log_memory_mutation_cur(
                            cur,
                            user_id=user_id,
                            memory_layer="semantic",
                            memory_id=str(existing["id"]),
                            action="reinforced",
                            reason="direct_scope_match",
                            source_episode_id=episode_id,
                            scope=scope,
                            metadata={"fact_key": candidate.fact_key},
                        )
                    else:
                        if existing and existing["memory_status"] == "pinned":
                            source_ids = list(existing["source_episode_ids"] or [])
                            if episode_id not in source_ids:
                                source_ids.append(episode_id)
                            await cur.execute(
                                """
                                UPDATE semantic_memories
                                SET content = %s,
                                    category = %s,
                                    confidence = GREATEST(confidence, %s),
                                    reinforcement_count = reinforcement_count + 1,
                                    source_episode_ids = %s,
                                    conversation_mode = %s,
                                    visibility_scope = %s,
                                    allowed_modes = %s,
                                    restricted_reason = %s,
                                    fact_key = COALESCE(%s, fact_key),
                                    archive_reason = NULL,
                                    archived_at = NULL,
                                    valid_to = NULL,
                                    superseded_by = NULL,
                                    last_updated = NOW(),
                                    embedding = COALESCE(%s::vector, embedding)
                                WHERE id = %s::uuid
                                """,
                                (
                                    candidate.content,
                                    candidate.category,
                                    candidate.confidence,
                                    source_ids,
                                    scope.conversation_mode,
                                    scope.visibility_scope,
                                    list(scope.allowed_modes),
                                    scope.restricted_reason,
                                    candidate.fact_key,
                                    embedding,
                                    existing["id"],
                                ),
                            )
                            await self._log_memory_mutation_cur(
                                cur,
                                user_id=user_id,
                                memory_layer="semantic",
                                memory_id=str(existing["id"]),
                                action="reinforced",
                                reason="pinned_scope_match",
                                source_episode_id=episode_id,
                                scope=scope,
                                metadata={"fact_key": candidate.fact_key},
                            )
                            continue

                        await cur.execute(
                            """
                            INSERT INTO semantic_memories (
                                user_id,
                                content,
                                category,
                                fact_key,
                                confidence,
                                reinforcement_count,
                                recall_count,
                                memory_status,
                                archive_reason,
                                archived_at,
                                source_episode_ids,
                                conversation_mode,
                                visibility_scope,
                                allowed_modes,
                                restricted_reason,
                                valid_from,
                                valid_to,
                                superseded_by,
                                embedding
                            )
                            VALUES (%s, %s, %s, %s, %s, 1, 0, 'active', NULL, NULL, %s, %s, %s, %s, %s, NOW(), NULL, NULL, %s::vector)
                            RETURNING id::text AS id
                            """,
                            (
                                user_id,
                                candidate.content,
                                candidate.category,
                                candidate.fact_key,
                                candidate.confidence,
                                [episode_id],
                                scope.conversation_mode,
                                scope.visibility_scope,
                                list(scope.allowed_modes),
                                scope.restricted_reason,
                                embedding,
                            ),
                        )
                        inserted = await cur.fetchone()
                        await self._log_memory_mutation_cur(
                            cur,
                            user_id=user_id,
                            memory_layer="semantic",
                            memory_id=str(inserted["id"]),
                            action="created",
                            reason="candidate_promoted",
                            source_episode_id=episode_id,
                            scope=scope,
                            metadata={"fact_key": candidate.fact_key, "category": candidate.category},
                        )
                        if existing and existing["memory_status"] != "pinned":
                            await cur.execute(
                                """
                                UPDATE semantic_memories
                                SET memory_status = 'archived',
                                    archive_reason = 'superseded',
                                    archived_at = NOW(),
                                    valid_to = NOW(),
                                    superseded_by = %s::uuid
                                WHERE id = %s::uuid
                                """,
                                (inserted["id"], existing["id"]),
                            )
                            await self._log_memory_mutation_cur(
                                cur,
                                user_id=user_id,
                                memory_layer="semantic",
                                memory_id=str(existing["id"]),
                                action="archived",
                                reason="superseded",
                                source_episode_id=episode_id,
                                scope=scope,
                                from_status=str(existing["memory_status"]),
                                to_status="archived",
                                metadata={"superseded_by": str(inserted["id"]), "fact_key": candidate.fact_key},
                            )
                    await self._maybe_reinforce_global_semantic_from_scoped(
                        cur,
                        user_id=user_id,
                        candidate=candidate,
                        episode_id=episode_id,
                        scope=scope,
                    )
            await conn.commit()

    async def _upsert_procedural_candidates(
        self,
        user_id: str,
        candidates: List[ProceduralCandidate],
        episode_id: str,
        scope: MemoryScope,
    ) -> None:
        if not candidates:
            return

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                for candidate in candidates:
                    embedding = vector_literal(await self.embeddings.embed_text(candidate.content))
                    await cur.execute(
                        """
                        SELECT id::text AS id, content, memory_status, source_episode_ids
                        FROM procedural_memories
                        WHERE user_id = %s
                          AND pattern_key = %s
                          AND visibility_scope = %s
                          AND allowed_modes = %s::text[]
                        ORDER BY
                          CASE WHEN memory_status = 'pinned' THEN 0 ELSE 1 END,
                          last_updated DESC
                        LIMIT 1
                        """,
                        (user_id, candidate.pattern_key, scope.visibility_scope, list(scope.allowed_modes)),
                    )
                    existing = await cur.fetchone()
                    if existing and str(existing["content"]) == candidate.content:
                        source_ids = list(existing["source_episode_ids"] or [])
                        if episode_id not in source_ids:
                            source_ids.append(episode_id)
                        await cur.execute(
                            """
                            UPDATE procedural_memories
                            SET content = %s,
                                reinforcement_count = reinforcement_count + 1,
                                confidence = LEAST(confidence + 0.04, 0.98),
                                memory_status = CASE WHEN memory_status = 'pinned' THEN 'pinned' ELSE 'active' END,
                                source_episode_ids = %s,
                                conversation_mode = %s,
                                visibility_scope = %s,
                                allowed_modes = %s,
                                restricted_reason = %s,
                                archive_reason = NULL,
                                archived_at = NULL,
                                valid_to = NULL,
                                superseded_by = NULL,
                                last_updated = NOW(),
                                embedding = COALESCE(%s::vector, embedding)
                            WHERE id = %s::uuid
                            """,
                            (
                                candidate.content,
                                source_ids,
                                scope.conversation_mode,
                                scope.visibility_scope,
                                list(scope.allowed_modes),
                                scope.restricted_reason,
                                embedding,
                                existing["id"],
                            ),
                        )
                        await self._log_memory_mutation_cur(
                            cur,
                            user_id=user_id,
                            memory_layer="procedural",
                            memory_id=str(existing["id"]),
                            action="reinforced",
                            reason="direct_scope_match",
                            source_episode_id=episode_id,
                            scope=scope,
                            metadata={"pattern_key": candidate.pattern_key},
                        )
                    else:
                        if existing and existing["memory_status"] == "pinned":
                            source_ids = list(existing["source_episode_ids"] or [])
                            if episode_id not in source_ids:
                                source_ids.append(episode_id)
                            await cur.execute(
                                """
                                UPDATE procedural_memories
                                SET content = %s,
                                    confidence = GREATEST(confidence, %s),
                                    reinforcement_count = reinforcement_count + 1,
                                    source_episode_ids = %s,
                                    conversation_mode = %s,
                                    visibility_scope = %s,
                                    allowed_modes = %s,
                                    restricted_reason = %s,
                                    archive_reason = NULL,
                                    archived_at = NULL,
                                    valid_to = NULL,
                                    superseded_by = NULL,
                                    last_updated = NOW(),
                                    embedding = COALESCE(%s::vector, embedding)
                                WHERE id = %s::uuid
                                """,
                                (
                                    candidate.content,
                                    candidate.confidence,
                                    source_ids,
                                    scope.conversation_mode,
                                    scope.visibility_scope,
                                    list(scope.allowed_modes),
                                    scope.restricted_reason,
                                    embedding,
                                    existing["id"],
                                ),
                            )
                            await self._log_memory_mutation_cur(
                                cur,
                                user_id=user_id,
                                memory_layer="procedural",
                                memory_id=str(existing["id"]),
                                action="reinforced",
                                reason="pinned_scope_match",
                                source_episode_id=episode_id,
                                scope=scope,
                                metadata={"pattern_key": candidate.pattern_key},
                            )
                            continue

                        await cur.execute(
                            """
                            INSERT INTO procedural_memories (
                                user_id,
                                content,
                                pattern_key,
                                confidence,
                                reinforcement_count,
                                recall_count,
                                memory_status,
                                archive_reason,
                                archived_at,
                                source_episode_ids,
                                conversation_mode,
                                visibility_scope,
                                allowed_modes,
                                restricted_reason,
                                valid_from,
                                valid_to,
                                superseded_by,
                                embedding
                            )
                            VALUES (%s, %s, %s, %s, 1, 0, 'active', NULL, NULL, %s, %s, %s, %s, %s, NOW(), NULL, NULL, %s::vector)
                            RETURNING id::text AS id
                            """,
                            (
                                user_id,
                                candidate.content,
                                candidate.pattern_key,
                                candidate.confidence,
                                [episode_id],
                                scope.conversation_mode,
                                scope.visibility_scope,
                                list(scope.allowed_modes),
                                scope.restricted_reason,
                                embedding,
                            ),
                        )
                        inserted = await cur.fetchone()
                        await self._log_memory_mutation_cur(
                            cur,
                            user_id=user_id,
                            memory_layer="procedural",
                            memory_id=str(inserted["id"]),
                            action="created",
                            reason="candidate_promoted",
                            source_episode_id=episode_id,
                            scope=scope,
                            metadata={"pattern_key": candidate.pattern_key},
                        )
                        if existing and existing["memory_status"] != "pinned":
                            await cur.execute(
                                """
                                UPDATE procedural_memories
                                SET memory_status = 'archived',
                                    archive_reason = 'superseded',
                                    archived_at = NOW(),
                                    valid_to = NOW(),
                                    superseded_by = %s::uuid
                                WHERE id = %s::uuid
                                """,
                                (inserted["id"], existing["id"]),
                            )
                            await self._log_memory_mutation_cur(
                                cur,
                                user_id=user_id,
                                memory_layer="procedural",
                                memory_id=str(existing["id"]),
                                action="archived",
                                reason="superseded",
                                source_episode_id=episode_id,
                                scope=scope,
                                from_status=str(existing["memory_status"]),
                                to_status="archived",
                                metadata={"superseded_by": str(inserted["id"]), "pattern_key": candidate.pattern_key},
                            )
                    await self._maybe_reinforce_global_procedural_from_scoped(
                        cur,
                        user_id=user_id,
                        candidate=candidate,
                        episode_id=episode_id,
                        scope=scope,
                    )
            await conn.commit()

    async def _maybe_reinforce_global_semantic_from_scoped(
        self,
        cur,
        *,
        user_id: str,
        candidate: SemanticCandidate,
        episode_id: Optional[str],
        scope: MemoryScope,
    ) -> None:
        """Private evidence may confirm an already-global belief, but never creates one."""
        if scope.visibility_scope == "global":
            return

        await cur.execute(
            """
            UPDATE semantic_memories
            SET reinforcement_count = reinforcement_count + 1,
                private_reinforcement_count = private_reinforcement_count + 1,
                confidence = LEAST(confidence + 0.015, 0.99),
                last_updated = NOW()
            WHERE user_id = %s
              AND visibility_scope = 'global'
              AND allowed_modes = '{}'::text[]
              AND memory_status IN ('active', 'pinned')
              AND (
                fact_key = %s
                OR lower(content) = lower(%s)
              )
            RETURNING id::text AS id
            """,
            (user_id, candidate.fact_key, candidate.content),
        )
        row = await cur.fetchone()
        if not row:
            return

        await self._log_memory_mutation_cur(
            cur,
            user_id=user_id,
            memory_layer="semantic",
            memory_id=str(row["id"]),
            action="reinforced",
            reason="scoped_confirmation_of_existing_global",
            source_episode_id=episode_id,
            scope=scope,
            metadata={
                "fact_key": candidate.fact_key,
                "source_visibility_scope": scope.visibility_scope,
                "source_allowed_modes": list(scope.allowed_modes),
                "private_source_not_added_to_global_provenance": True,
            },
        )

    async def _maybe_reinforce_global_procedural_from_scoped(
        self,
        cur,
        *,
        user_id: str,
        candidate: ProceduralCandidate,
        episode_id: Optional[str],
        scope: MemoryScope,
    ) -> None:
        """Private evidence can confirm an existing global procedure without leaking details."""
        if scope.visibility_scope == "global":
            return

        await cur.execute(
            """
            UPDATE procedural_memories
            SET reinforcement_count = reinforcement_count + 1,
                private_reinforcement_count = private_reinforcement_count + 1,
                confidence = LEAST(confidence + 0.012, 0.98),
                last_updated = NOW()
            WHERE user_id = %s
              AND visibility_scope = 'global'
              AND allowed_modes = '{}'::text[]
              AND memory_status IN ('active', 'pinned')
              AND (
                pattern_key = %s
                OR lower(content) = lower(%s)
              )
            RETURNING id::text AS id
            """,
            (user_id, candidate.pattern_key, candidate.content),
        )
        row = await cur.fetchone()
        if not row:
            return

        await self._log_memory_mutation_cur(
            cur,
            user_id=user_id,
            memory_layer="procedural",
            memory_id=str(row["id"]),
            action="reinforced",
            reason="scoped_confirmation_of_existing_global",
            source_episode_id=episode_id,
            scope=scope,
            metadata={
                "pattern_key": candidate.pattern_key,
                "source_visibility_scope": scope.visibility_scope,
                "source_allowed_modes": list(scope.allowed_modes),
                "private_source_not_added_to_global_provenance": True,
            },
        )

    async def _log_memory_mutation_cur(
        self,
        cur,
        *,
        user_id: str,
        memory_layer: str,
        memory_id: Optional[str],
        action: str,
        scope: MemoryScope,
        reason: Optional[str] = None,
        source_episode_id: Optional[str] = None,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        await cur.execute(
            """
            INSERT INTO memory_mutations (
                user_id,
                memory_layer,
                memory_id,
                action,
                reason,
                source_episode_id,
                from_status,
                to_status,
                conversation_mode,
                visibility_scope,
                allowed_modes,
                metadata
            )
            VALUES (%s, %s, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                user_id,
                memory_layer,
                memory_id,
                action,
                reason,
                source_episode_id,
                from_status,
                to_status,
                scope.conversation_mode,
                scope.visibility_scope,
                list(scope.allowed_modes),
                json.dumps(metadata or {}),
            ),
        )

    async def _update_graph(
        self,
        user_id: str,
        facts: List[GraphFact],
        episode_id: str,
        scope: MemoryScope,
    ) -> None:
        if not facts:
            return

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                for fact in facts:
                    source_id = await self._upsert_graph_node(
                        cur,
                        user_id,
                        fact.source_label,
                        fact.source_type,
                        scope,
                    )
                    target_id = await self._upsert_graph_node(
                        cur,
                        user_id,
                        fact.target_label,
                        fact.target_type,
                        scope,
                    )
                    await cur.execute(
                        """
                        SELECT id::text AS id, source_episode_ids
                        FROM graph_edges
                        WHERE user_id = %s
                          AND source_node_id = %s::uuid
                          AND target_node_id = %s::uuid
                          AND relation = %s
                          AND visibility_scope = %s
                          AND allowed_modes = %s::text[]
                        """,
                        (
                            user_id,
                            source_id,
                            target_id,
                            fact.relation,
                            scope.visibility_scope,
                            list(scope.allowed_modes),
                        ),
                    )
                    existing = await cur.fetchone()
                    if existing:
                        source_ids = list(existing["source_episode_ids"] or [])
                        if episode_id not in source_ids:
                            source_ids.append(episode_id)
                        await cur.execute(
                            """
                            UPDATE graph_edges
                            SET weight = LEAST(weight + 0.08, 1.0),
                                source_episode_ids = %s,
                                conversation_mode = %s,
                                visibility_scope = %s,
                                allowed_modes = %s,
                                restricted_reason = %s,
                                edge_status = 'active',
                                valid_to = NULL,
                                last_seen = NOW()
                            WHERE id = %s::uuid
                            """,
                            (
                                source_ids,
                                scope.conversation_mode,
                                scope.visibility_scope,
                                list(scope.allowed_modes),
                                scope.restricted_reason,
                                existing["id"],
                            ),
                        )
                    else:
                        await cur.execute(
                            """
                            INSERT INTO graph_edges (
                                user_id,
                                source_node_id,
                                target_node_id,
                                relation,
                                weight,
                                recall_count,
                                source_episode_ids,
                                conversation_mode,
                                visibility_scope,
                                allowed_modes,
                                restricted_reason,
                                edge_status,
                                valid_from,
                                valid_to,
                                created_at,
                                last_seen
                            )
                            VALUES (%s, %s::uuid, %s::uuid, %s, %s, 0, %s, %s, %s, %s, %s, 'active', NOW(), NULL, NOW(), NOW())
                            """,
                            (
                                user_id,
                                source_id,
                                target_id,
                                fact.relation,
                                fact.weight,
                                [episode_id],
                                scope.conversation_mode,
                                scope.visibility_scope,
                                list(scope.allowed_modes),
                                scope.restricted_reason,
                            ),
                        )
            await conn.commit()

    async def _upsert_graph_node(
        self,
        cur,
        user_id: str,
        label: str,
        node_type: str,
        scope: MemoryScope,
    ) -> str:
        await cur.execute(
            """
            INSERT INTO graph_nodes (
                user_id,
                label,
                node_type,
                properties,
                visibility_scope,
                allowed_modes,
                restricted_reason
            )
            VALUES (%s, %s, %s, '{}'::jsonb, %s, %s, %s)
            ON CONFLICT (user_id, label)
            DO UPDATE SET
                label = EXCLUDED.label,
                node_type = CASE
                    WHEN graph_nodes.node_type = 'concept' AND EXCLUDED.node_type <> 'concept' THEN EXCLUDED.node_type
                    ELSE graph_nodes.node_type
                END,
                visibility_scope = CASE
                    WHEN graph_nodes.visibility_scope = 'global' THEN 'global'
                    ELSE EXCLUDED.visibility_scope
                END,
                allowed_modes = CASE
                    WHEN graph_nodes.visibility_scope = 'global' THEN graph_nodes.allowed_modes
                    ELSE EXCLUDED.allowed_modes
                END,
                restricted_reason = COALESCE(graph_nodes.restricted_reason, EXCLUDED.restricted_reason)
            RETURNING id::text
            """,
            (
                user_id,
                label,
                node_type,
                scope.visibility_scope,
                list(scope.allowed_modes),
                scope.restricted_reason,
            ),
        )
        row = await cur.fetchone()
        return str(row["id"])

    async def _reinforce_recent_semantics(self, user_id: str, recent_episodes: List[dict]) -> None:
        seen: dict = {}
        candidates_by_key: dict = {}
        for episode in recent_episodes:
            scope_key = (
                str(episode.get("visibility_scope") or "global"),
                tuple(str(mode) for mode in list(episode.get("allowed_modes") or [])),
                str(episode.get("conversation_mode") or "general"),
            )
            for candidate in self._extract_semantic_candidates(
                str(episode["user_input"]),
                Assessment(stakes="low", novelty="low", emotional_tone=str(episode["emotional_tone"])),
            ):
                key = (*scope_key, candidate.fact_key)
                seen[key] = seen.get(key, 0) + 1
                candidates_by_key[key] = candidate

        repeated = [(key, count) for key, count in seen.items() if count > 1]
        if not repeated:
            return

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                for key, _count in repeated:
                    visibility_scope, allowed_modes, conversation_mode, fact_key = key
                    await cur.execute(
                        """
                        UPDATE semantic_memories
                        SET confidence = LEAST(confidence + 0.03, 0.99),
                            reinforcement_count = reinforcement_count + 1,
                            last_updated = NOW()
                        WHERE user_id = %s
                          AND fact_key = %s
                          AND visibility_scope = %s
                          AND allowed_modes = %s::text[]
                          AND memory_status IN ('active', 'pinned')
                        """,
                        (user_id, fact_key, visibility_scope, list(allowed_modes)),
                    )
                    await self._maybe_reinforce_global_semantic_from_scoped(
                        cur,
                        user_id=user_id,
                        candidate=candidates_by_key[key],
                        episode_id=None,
                        scope=MemoryScope(
                            conversation_mode=conversation_mode,
                            visibility_scope=visibility_scope,
                            allowed_modes=tuple(allowed_modes),
                            restricted_reason="nightly_scoped_consolidation",
                        ),
                    )
            await conn.commit()

    async def _reinforce_recent_procedurals(self, user_id: str, recent_episodes: List[dict]) -> None:
        seen: dict = {}
        candidates_by_key: dict = {}
        for episode in recent_episodes:
            scope_key = (
                str(episode.get("visibility_scope") or "global"),
                tuple(str(mode) for mode in list(episode.get("allowed_modes") or [])),
                str(episode.get("conversation_mode") or "general"),
            )
            assessment = Assessment(stakes="low", novelty="low", emotional_tone=str(episode["emotional_tone"]))
            for candidate in self._extract_procedural_candidates(str(episode["user_input"]), assessment):
                key = (*scope_key, candidate.pattern_key)
                seen[key] = seen.get(key, 0) + 1
                candidates_by_key[key] = candidate

        repeated = [(key, count) for key, count in seen.items() if count > 1]
        if not repeated:
            return

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                for key, _count in repeated:
                    visibility_scope, allowed_modes, conversation_mode, pattern_key = key
                    await cur.execute(
                        """
                        UPDATE procedural_memories
                        SET confidence = LEAST(confidence + 0.025, 0.98),
                            reinforcement_count = reinforcement_count + 1,
                            last_updated = NOW()
                        WHERE user_id = %s
                          AND pattern_key = %s
                          AND visibility_scope = %s
                          AND allowed_modes = %s::text[]
                          AND memory_status IN ('active', 'pinned')
                        """,
                        (user_id, pattern_key, visibility_scope, list(allowed_modes)),
                    )
                    await self._maybe_reinforce_global_procedural_from_scoped(
                        cur,
                        user_id=user_id,
                        candidate=candidates_by_key[key],
                        episode_id=None,
                        scope=MemoryScope(
                            conversation_mode=conversation_mode,
                            visibility_scope=visibility_scope,
                            allowed_modes=tuple(allowed_modes),
                            restricted_reason="nightly_scoped_consolidation",
                        ),
                    )
            await conn.commit()

    async def _resolve_semantic_conflicts(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    WITH ranked AS (
                        SELECT
                            id,
                            fact_key,
                            memory_status,
                            FIRST_VALUE(id) OVER (
                                PARTITION BY fact_key, visibility_scope, allowed_modes
                                ORDER BY
                                    CASE WHEN memory_status = 'pinned' THEN 0 ELSE 1 END,
                                    reinforcement_count DESC,
                                    recall_count DESC,
                                    last_updated DESC
                            ) AS winner_id,
                            ROW_NUMBER() OVER (
                                PARTITION BY fact_key, visibility_scope, allowed_modes
                                ORDER BY
                                    CASE WHEN memory_status = 'pinned' THEN 0 ELSE 1 END,
                                    reinforcement_count DESC,
                                    recall_count DESC,
                                    last_updated DESC
                            ) AS row_num
                        FROM semantic_memories
                        WHERE user_id = %s
                          AND fact_key IS NOT NULL
                          AND memory_status IN ('active', 'pinned')
                    )
                    UPDATE semantic_memories sm
                    SET memory_status = 'archived',
                        archive_reason = 'superseded',
                        archived_at = NOW(),
                        valid_to = NOW(),
                        superseded_by = r.winner_id
                    FROM ranked r
                    WHERE sm.id = r.id
                      AND r.row_num > 1
                      AND sm.memory_status <> 'pinned'
                    """,
                    (user_id,),
                )
            await conn.commit()

    async def _normalize_legacy_semantic_keys(self, user_id: str) -> None:
        mappings = [
            ("User's goal is to %", "goal:primary"),
            ("User wants to %", "goal:primary"),
            ("User is working on %", "project:primary"),
            ("User is building %", "project:primary"),
            ("User's name is %", "identity:name"),
        ]

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                for content_pattern, fact_key in mappings:
                    await cur.execute(
                        """
                        UPDATE semantic_memories
                        SET fact_key = %s,
                            last_updated = NOW()
                        WHERE user_id = %s
                          AND COALESCE(NULLIF(BTRIM(fact_key), ''), NULL) IS NULL
                          AND content LIKE %s
                        """,
                        (fact_key, user_id, content_pattern),
                    )

                for fact_key, family in SEMANTIC_CANONICAL_FAMILIES.items():
                    for keyword in family["keywords"]:
                        await cur.execute(
                            """
                            UPDATE semantic_memories
                            SET fact_key = %s,
                                content = CASE
                                    WHEN memory_status = 'pinned' THEN content
                                    ELSE %s
                                END,
                                category = %s,
                                last_updated = NOW()
                            WHERE user_id = %s
                              AND (
                                fact_key = %s
                                OR lower(content) LIKE %s
                              )
                            """,
                            (
                                fact_key,
                                family["content"],
                                family["category"],
                                user_id,
                                fact_key,
                                f"%{keyword}%",
                            ),
                        )

                await cur.execute(
                    """
                    UPDATE semantic_memories
                    SET fact_key = 'preference:communication_style',
                        last_updated = NOW()
                    WHERE user_id = %s
                      AND COALESCE(NULLIF(BTRIM(fact_key), ''), NULL) IS NULL
                      AND content = 'User prefers direct communication.'
                    """,
                    (user_id,),
                )
                await cur.execute(
                    """
                    UPDATE semantic_memories
                    SET fact_key = 'preference:stress_response_style',
                        last_updated = NOW()
                    WHERE user_id = %s
                      AND COALESCE(NULLIF(BTRIM(fact_key), ''), NULL) IS NULL
                      AND content = 'When the user is stressed, concise answers work best.'
                    """,
                    (user_id,),
                )
                await cur.execute(
                    """
                    UPDATE semantic_memories sm
                    SET memory_status = 'archived',
                        archive_reason = 'superseded',
                        archived_at = NOW()
                    WHERE sm.user_id = %s
                      AND sm.memory_status = 'active'
                      AND sm.fact_key LIKE 'preference:general:%%'
                      AND (
                        lower(sm.content) LIKE '%%direct communication%%'
                        OR lower(sm.content) LIKE '%%concise answers%%'
                      )
                      AND EXISTS (
                        SELECT 1
                        FROM semantic_memories precise
                        WHERE precise.user_id = sm.user_id
                          AND precise.memory_status IN ('active', 'pinned')
                          AND precise.fact_key IN (
                            'preference:communication_style',
                            'preference:stress_response_style'
                          )
                          AND precise.id <> sm.id
                          AND precise.visibility_scope = sm.visibility_scope
                          AND precise.allowed_modes = sm.allowed_modes
                      )
                    """,
                    (user_id,),
                )
            await conn.commit()

    async def _fold_semantic_duplicate_families(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        content,
                        category,
                        fact_key,
                        confidence,
                        reinforcement_count,
                        recall_count,
                        memory_status,
                        source_episode_ids,
                        visibility_scope,
                        allowed_modes,
                        last_updated
                    FROM semantic_memories
                    WHERE user_id = %s
                      AND fact_key IS NOT NULL
                      AND memory_status IN ('active', 'pinned')
                    ORDER BY
                        fact_key,
                        CASE WHEN memory_status = 'pinned' THEN 0 ELSE 1 END,
                        reinforcement_count DESC,
                        recall_count DESC,
                        last_updated DESC
                    """,
                    (user_id,),
                )
                rows = await cur.fetchall()

                rows_by_key: dict[tuple[str, str, tuple[str, ...]], list[dict]] = {}
                for row in rows:
                    scope_key = (
                        str(row["fact_key"]),
                        str(row.get("visibility_scope") or "global"),
                        tuple(str(mode) for mode in list(row.get("allowed_modes") or [])),
                    )
                    rows_by_key.setdefault(scope_key, []).append(row)

                for (fact_key, _visibility_scope, _allowed_modes), family_rows in rows_by_key.items():
                    if len(family_rows) < 2:
                        continue

                    winner = family_rows[0]
                    duplicates = family_rows[1:]
                    source_ids = {
                        str(source_id)
                        for row in family_rows
                        for source_id in list(row["source_episode_ids"] or [])
                    }
                    reinforcement_total = sum(int(row["reinforcement_count"]) for row in family_rows)
                    recall_total = sum(int(row["recall_count"]) for row in family_rows)
                    confidence = max(float(row["confidence"]) for row in family_rows)
                    duplicate_ids = [str(row["id"]) for row in duplicates if row["memory_status"] != "pinned"]

                    family = SEMANTIC_CANONICAL_FAMILIES.get(fact_key)
                    canonical_content = str(family["content"]) if family else str(winner["content"])
                    canonical_category = str(family["category"]) if family else str(winner["category"])

                    await cur.execute(
                        """
                        UPDATE semantic_memories
                        SET content = CASE
                                WHEN memory_status = 'pinned' THEN content
                                ELSE %s
                            END,
                            category = %s,
                            confidence = GREATEST(confidence, %s),
                            reinforcement_count = GREATEST(reinforcement_count, %s),
                            recall_count = GREATEST(recall_count, %s),
                            source_episode_ids = %s,
                            archive_reason = NULL,
                            archived_at = NULL,
                            valid_to = NULL,
                            superseded_by = NULL,
                            last_updated = NOW()
                        WHERE id = %s::uuid
                        """,
                        (
                            canonical_content,
                            canonical_category,
                            confidence,
                            reinforcement_total,
                            recall_total,
                            sorted(source_ids),
                            winner["id"],
                        ),
                    )

                    if duplicate_ids:
                        await cur.execute(
                            """
                            UPDATE semantic_memories
                            SET memory_status = 'archived',
                                archive_reason = 'reinforced_into_canonical',
                                archived_at = NOW(),
                                valid_to = NOW(),
                                superseded_by = %s::uuid,
                                last_updated = NOW()
                            WHERE id = ANY(%s::uuid[])
                            """,
                            (winner["id"], duplicate_ids),
                        )
            await conn.commit()

    async def _archive_stale_episodes(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    WITH ranked AS (
                        SELECT
                            id,
                            ROW_NUMBER() OVER (ORDER BY timestamp DESC) AS row_num
                        FROM episodes
                        WHERE user_id = %s
                          AND memory_status = 'active'
                    )
                    UPDATE episodes
                    SET memory_status = 'archived',
                        archive_reason = 'low_reinforcement',
                        archived_at = NOW()
                    WHERE id IN (
                        SELECT e.id
                        FROM episodes e
                        JOIN ranked r ON r.id = e.id
                        WHERE r.row_num > 60
                          AND e.salience < 0.8
                          AND e.stability < 4.0
                          AND e.recall_count <= 1
                    )
                    """,
                    (user_id,),
                )
            await conn.commit()

    async def _archive_stale_semantics(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE semantic_memories
                    SET memory_status = 'archived',
                        archive_reason = 'stale',
                        archived_at = NOW(),
                        valid_to = NOW()
                    WHERE user_id = %s
                      AND memory_status = 'active'
                      AND confidence < 0.83
                      AND recall_count = 0
                      AND reinforcement_count <= 1
                      AND last_updated < NOW() - INTERVAL '30 days'
                    """,
                    (user_id,),
                )
            await conn.commit()

    async def _archive_stale_procedurals(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE procedural_memories
                    SET memory_status = 'archived',
                        archive_reason = 'stale',
                        archived_at = NOW(),
                        valid_to = NOW()
                    WHERE user_id = %s
                      AND memory_status = 'active'
                      AND confidence < 0.82
                      AND recall_count = 0
                      AND reinforcement_count <= 1
                      AND last_updated < NOW() - INTERVAL '45 days'
                    """,
                    (user_id,),
                )
            await conn.commit()

    async def _weaken_stale_graph_edges(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE graph_edges
                    SET weight = GREATEST(weight - 0.06, 0.18),
                        edge_status = CASE
                            WHEN last_seen < NOW() - INTERVAL '90 days' AND weight < 0.42 THEN 'archived'
                            ELSE edge_status
                        END,
                        valid_to = CASE
                            WHEN last_seen < NOW() - INTERVAL '90 days' AND weight < 0.42
                            THEN COALESCE(valid_to, NOW())
                            ELSE valid_to
                        END
                    WHERE user_id = %s
                      AND last_seen < NOW() - INTERVAL '30 days'
                      AND edge_status = 'active'
                    """,
                    (user_id,),
                )
            await conn.commit()

    def _build_retrieval_plan(self, query: str, assessment: Optional[Assessment]) -> RetrievalPlan:
        lowered = query.lower()
        memory_lookup = any(
            marker in lowered
            for marker in [
                "remember",
                "what did i tell you",
                "what do you remember",
                "earlier",
                "last week",
                "last month",
                "before",
                "back when",
                "what changed",
                "changed recently",
            ]
        )
        self_model_lookup = any(
            marker in lowered
            for marker in [
                "prefer",
                "communication",
                "respond",
                "when i'm stressed",
                "when i am stressed",
                "how should you",
                "what works for me",
            ]
        )
        relationship_lookup = any(
            marker in lowered
            for marker in [
                "project",
                "goal",
                "building",
                "working on",
                "person",
                "relationship",
                "connected",
            ]
        )
        emotional_lookup = bool(
            assessment and assessment.emotional_tone in {"stressed", "grief", "frustrated", "sad"}
        )

        plan = RetrievalPlan(
            include_archived=memory_lookup or emotional_lookup,
            episodic_limit=5 if memory_lookup else 3,
            semantic_limit=4 if self_model_lookup else 3,
            procedural_limit=3 if self_model_lookup else 2,
            graph_limit=3 if relationship_lookup else 2,
            reactivation_limit=2 if (memory_lookup or emotional_lookup) else 0,
        )

        if memory_lookup and relationship_lookup:
            plan.graph_limit = 4
        if memory_lookup:
            plan.episodic_weight = 1.12
            plan.semantic_weight = 0.97
        if self_model_lookup:
            plan.episodic_limit = min(plan.episodic_limit, 1)
            plan.semantic_limit = max(plan.semantic_limit, 5)
            plan.procedural_limit = max(plan.procedural_limit, 4)
            plan.episodic_weight *= 0.68
            plan.semantic_weight *= 1.22
            plan.procedural_weight *= 1.12
        if relationship_lookup:
            plan.episodic_limit = min(plan.episodic_limit, 2)
            plan.semantic_limit = max(plan.semantic_limit, 4)
            plan.graph_limit = max(plan.graph_limit, 3)
            plan.episodic_weight *= 0.80
            plan.semantic_weight *= 1.10
            plan.graph_weight *= 1.12
        if emotional_lookup:
            plan.episodic_limit = min(plan.episodic_limit, 2)
            plan.semantic_limit = max(plan.semantic_limit, 4)
            plan.procedural_limit = max(plan.procedural_limit, 4)
            plan.episodic_weight *= 0.88
            plan.semantic_weight *= 1.16
            plan.procedural_weight *= 1.34
        return plan

    def _classify_retrieval_intent(self, query: str, assessment: Optional[Assessment]) -> RetrievalIntent:
        lowered = query.lower()

        if any(
            marker in lowered
            for marker in [
                "remember",
                "what did i tell you",
                "what did we talk about",
                "earlier",
                "last week",
                "last month",
                "before",
                "back when",
            ]
        ):
            return RetrievalIntent(
                name="episodic_recall",
                mention_kinds=("episodic", "semantic", "graph"),
                silent_kinds=("procedural",),
                mention_limit=5,
                silent_limit=2,
            )

        if any(
            marker in lowered
            for marker in ["what changed", "changed recently", "different now", "used to", "now i"]
        ):
            return RetrievalIntent(
                name="temporal_change",
                mention_kinds=("semantic", "episodic", "graph"),
                silent_kinds=("procedural",),
                mention_limit=5,
                silent_limit=2,
            )

        if any(
            marker in lowered
            for marker in [
                "prefer",
                "communication",
                "respond",
                "how should you",
                "what works for me",
                "how do i usually",
                "when i'm stressed",
                "when i am stressed",
            ]
        ):
            return RetrievalIntent(
                name="self_model",
                mention_kinds=("semantic", "procedural"),
                silent_kinds=("episodic", "graph"),
                mention_limit=4,
                silent_limit=3,
            )

        if any(
            marker in lowered
            for marker in ["person", "people", "relationship", "connected", "project", "goal", "investor", "client"]
        ):
            return RetrievalIntent(
                name="relationship_or_project",
                mention_kinds=("graph", "semantic", "episodic"),
                silent_kinds=("procedural",),
                mention_limit=4,
                silent_limit=3,
            )

        if assessment and assessment.emotional_tone in {"stressed", "grief", "frustrated", "sad"}:
            return RetrievalIntent(
                name="emotional_support",
                mention_kinds=("procedural", "semantic", "episodic"),
                silent_kinds=("procedural", "semantic"),
                mention_limit=3,
                silent_limit=4,
            )

        return RetrievalIntent(
            name="general",
            mention_kinds=("semantic", "episodic", "graph"),
            silent_kinds=("procedural", "semantic"),
            mention_limit=3,
            silent_limit=3,
        )

    def _select_memories_for_prompt(
        self,
        memories: List[RetrievedMemory],
        query: str,
        assessment: Optional[Assessment],
        limit: int,
    ) -> List[RetrievedMemory]:
        if not memories:
            return []

        intent = self._classify_retrieval_intent(query, assessment)
        query_terms = self._meaningful_terms(query)
        mention_candidates: list[tuple[float, RetrievedMemory]] = []
        silent_candidates: list[tuple[float, RetrievedMemory]] = []

        for memory in memories:
            use, reason, adjusted_score = self._judge_memory_use(memory, intent, query_terms, assessment)
            if use == "drop":
                continue

            judged = memory.model_copy(
                update={
                    "score": adjusted_score,
                    "use": use,
                    "relevance_reason": f"{intent.name}: {reason}",
                }
            )
            if use == "mention":
                mention_candidates.append((adjusted_score, judged))
            else:
                silent_candidates.append((adjusted_score, judged))

        mention_candidates.sort(key=lambda item: item[0], reverse=True)
        silent_candidates.sort(key=lambda item: item[0], reverse=True)

        mention_limit = min(intent.mention_limit, max(2, limit))
        silent_limit = min(intent.silent_limit, max(1, limit - min(len(mention_candidates), mention_limit)))

        selected = [
            memory
            for _score, memory in mention_candidates[:mention_limit]
        ]
        selected.extend(
            memory
            for _score, memory in silent_candidates[:silent_limit]
            if memory.content not in {selected_memory.content for selected_memory in selected}
        )

        if not selected and memories:
            best = memories[0]
            selected.append(
                best.model_copy(
                    update={
                        "use": "mention",
                        "relevance_reason": f"{intent.name}: strongest available memory",
                    }
                )
            )

        return selected[: max(limit, 1)]

    def _judge_memory_use(
        self,
        memory: RetrievedMemory,
        intent: RetrievalIntent,
        query_terms: set[str],
        assessment: Optional[Assessment],
    ) -> tuple[str, str, float]:
        lowered_content = memory.content.lower()
        overlap = len(query_terms.intersection(self._meaningful_terms(memory.content)))
        confidence = memory.confidence if memory.confidence is not None else 0.65
        score = memory.score

        if memory.memory_status == "pinned":
            score += 0.10
        if memory.memory_status == "archived":
            score -= 0.08

        if overlap:
            score += min(overlap * 0.045, 0.18)
        elif intent.name not in {"emotional_support", "general"}:
            score -= 0.06

        if memory.kind in intent.mention_kinds:
            score += 0.08
        if memory.kind in intent.silent_kinds:
            score += 0.04

        generic_preference = any(
            marker in lowered_content
            for marker in ["direct", "concise", "grounding", "calm", "respond", "communication"]
        )
        project_context = any(
            marker in lowered_content
            for marker in ["building", "working on", "goal", "project", "ai companion"]
        )
        emotional_context = any(
            marker in lowered_content
            for marker in ["stress", "stressed", "heavy", "overwhelmed", "grounding", "sad", "grief"]
        )

        if intent.name == "emotional_support":
            if emotional_context or memory.kind == "procedural":
                return "silent", "regulates tone or support strategy", score + 0.10
            if memory.kind == "episodic" and overlap:
                return "mention", "related past episode may ground the response", score

        if intent.name == "self_model":
            if memory.kind in {"semantic", "procedural"}:
                return "mention", "directly answers a self-model question", score + 0.06
            if generic_preference:
                return "silent", "use as response-style guidance", score

        if intent.name == "episodic_recall":
            if memory.kind == "episodic":
                return "mention", "the user is asking for remembered events", score + 0.10
            if overlap or memory.memory_status == "pinned":
                return "mention", "supports the recalled episode", score

        if intent.name == "temporal_change":
            if memory.valid_to or memory.memory_status == "archived":
                return "mention", "older state may help explain change", score + 0.08
            if memory.kind in {"semantic", "episodic"}:
                return "mention", "current or past belief may contrast over time", score

        if intent.name == "relationship_or_project":
            if memory.kind in {"graph", "episodic"} and (overlap or project_context):
                return "mention", "connected to the active person/project thread", score + 0.08
            if memory.kind == "semantic" and project_context:
                return "mention", "project/goal context is relevant", score + 0.05
            if memory.kind == "procedural":
                return "silent", "may shape practical next steps", score

        if memory.kind == "procedural":
            if generic_preference or emotional_context:
                return "silent", "procedural guidance should influence style, not be quoted", score
            if score >= 0.74:
                return "silent", "high-scoring procedure may guide response", score

        if memory.kind == "semantic" and generic_preference and intent.name == "general":
            return "silent", "general preference should shape tone quietly", score

        if overlap >= 2:
            return "mention", "specific term overlap with the current turn", score + 0.04
        if memory.memory_status == "pinned" and score >= 0.42:
            return "silent", "pinned but not directly worth mentioning", score
        if confidence >= 0.86 and score >= 0.62:
            return "silent", "reliable background context", score
        if score >= 0.70:
            return "mention", "high retrieval score", score

        return "drop", "too broad or weak for this turn", score

    def _meaningful_terms(self, text: str) -> set[str]:
        return {
            word
            for word in re.findall(r"\b[a-z][a-z0-9'-]{2,}\b", text.lower())
            if word not in STOPWORDS
        }

    def _rebalance_scores(
        self,
        memories: List[RetrievedMemory],
        weight: float,
        query: str,
        assessment: Optional[Assessment] = None,
    ) -> List[RetrievedMemory]:
        if weight == 1.0:
            return [
                memory.model_copy(update={"score": memory.score + self._intent_bonus(query, memory, assessment)})
                for memory in memories
            ]
        return [
            memory.model_copy(update={"score": (memory.score * weight) + self._intent_bonus(query, memory, assessment)})
            for memory in memories
        ]

    def _intent_bonus(
        self,
        query: str,
        memory: RetrievedMemory,
        assessment: Optional[Assessment],
    ) -> float:
        lowered_query = query.lower()
        lowered_content = memory.content.lower()
        bonus = 0.0

        goal_query = any(
            marker in lowered_query
            for marker in ["main goal", "my goal", "what is my goal", "what am i building", "vision"]
        )
        response_query = any(
            marker in lowered_query
            for marker in [
                "respond",
                "response",
                "stressed",
                "stress",
                "communication",
                "prefer",
                "what works for me",
                "grounding",
                "concise",
            ]
        )

        if goal_query:
            if any(marker in lowered_content for marker in ["goal is to", "wants to", "working on", "is building"]):
                bonus += 0.24
            if memory.kind == "episodic":
                bonus -= 0.06

        if response_query:
            if any(
                marker in lowered_content
                for marker in ["stressed", "stress", "direct communication", "concise", "grounding", "respond"]
            ):
                bonus += 0.22
            if any(marker in lowered_content for marker in ["goal is to", "wants to", "working on", "is building"]):
                bonus -= 0.10

        if assessment and assessment.emotional_tone in {"stressed", "grief", "frustrated", "sad"}:
            if memory.kind in {"semantic", "procedural"} and any(
                marker in lowered_content
                for marker in ["grounding", "concise", "direct communication", "stress", "calm", "shorter"]
            ):
                bonus += 0.20
            if memory.kind == "episodic" and any(
                marker in lowered_content
                for marker in ["overwhelmed", "stressed", "heavy", "ground"]
            ):
                bonus += 0.08

        return bonus

    def _canonicalize_semantic_candidate(self, candidate: SemanticCandidate) -> SemanticCandidate:
        normalized_content = self._normalize_semantic_text(candidate.content)

        if candidate.fact_key in SEMANTIC_CANONICAL_FAMILIES and SEMANTIC_CANONICAL_FAMILIES[candidate.fact_key].get("content"):
            family = SEMANTIC_CANONICAL_FAMILIES[candidate.fact_key]
            return SemanticCandidate(
                category=str(family["category"]),
                fact_key=candidate.fact_key,
                content=str(family["content"]),
                confidence=candidate.confidence,
            )

        for fact_key, family in SEMANTIC_CANONICAL_FAMILIES.items():
            if any(keyword in normalized_content for keyword in family["keywords"]):
                return SemanticCandidate(
                    category=str(family["category"]),
                    fact_key=fact_key,
                    content=str(family["content"]),
                    confidence=max(candidate.confidence, 0.78),
                )

        return candidate

    def _normalize_semantic_text(self, text: str) -> str:
        cleaned = re.sub(r"[^a-z0-9+ ]+", " ", text.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    def _extract_semantic_candidates(
        self,
        text: str,
        assessment: Assessment,
    ) -> List[SemanticCandidate]:
        lowered = text.lower()
        candidates: List[SemanticCandidate] = []
        home_location = self._extract_home_location(text)
        if home_location:
            candidates.append(
                SemanticCandidate(
                    category="location",
                    fact_key="location:home",
                    content=f"User lives in {home_location}.",
                    confidence=0.94,
                )
            )

        multi_patterns = [
            (r"\bmy name is ([a-z][a-z\s'-]+)", "identity", "identity:name", "User's name is {value}."),
            (r"\bi am working on ([^.?!]+)", "project", "project:primary", "User is working on {value}."),
            (r"\bi'm working on ([^.?!]+)", "project", "project:primary", "User is working on {value}."),
            (r"\bi am building ([^.?!]+)", "project", "project:primary", "User is building {value}."),
            (r"\bi'm building ([^.?!]+)", "project", "project:primary", "User is building {value}."),
            (r"\bmy goal is to ([^.?!]+)", "goal", "goal:primary", "User's goal is to {value}."),
            (r"\bi want to ([^.?!]+)", "goal", "goal:primary", "User wants to {value}."),
            (
                r"\bi prefer ([^.?!]+)",
                "preference",
                "preference:general:" ,
                "User prefers {value}.",
            ),
        ]

        for pattern, category, key_prefix, template in multi_patterns:
            for match in re.finditer(pattern, lowered):
                value = self._clean_fact_value(match.group(1))
                if not value:
                    continue
                if key_prefix == "preference:general:" and (
                    "direct communication" in value or "concise answers" in value
                ):
                    continue
                if key_prefix.endswith(":"):
                    fact_key = key_prefix + self._slug(value)
                else:
                    fact_key = key_prefix
                candidates.append(
                    SemanticCandidate(
                        category=category,
                        fact_key=fact_key,
                        content=template.format(value=value),
                        confidence=0.76 if category in {"goal", "project"} else 0.72,
                    )
                )

        if "direct communication" in lowered:
            candidates.append(
                SemanticCandidate(
                    category="preference",
                    fact_key="preference:communication_style",
                    content="User prefers direct communication.",
                    confidence=0.84,
                )
            )

        if "concise answers" in lowered and ("when i am stressed" in lowered or "when i'm stressed" in lowered):
            candidates.append(
                SemanticCandidate(
                    category="preference",
                    fact_key="preference:stress_response_style",
                    content="When the user is stressed, concise answers work best.",
                    confidence=0.88,
                )
            )

        if assessment.emotional_tone in {"stressed", "grief"}:
            candidates.append(
                SemanticCandidate(
                    category="state-pattern",
                    fact_key="pattern:recent_emotional_heaviness",
                    content="The user is showing recent emotional heaviness and benefits from grounding responses.",
                    confidence=0.66,
                )
            )

        if assessment.dialogue_signals.indirectness_score >= 0.55 or assessment.dialogue_signals.ramble_score >= 0.62:
            candidates.append(
                SemanticCandidate(
                    category="dialogue-pattern",
                    fact_key="dialogue:long_preamble",
                    content="The user sometimes takes a winding path before landing the main point.",
                    confidence=0.64,
                )
            )

        if assessment.dialogue_signals.hedging_score >= 0.48:
            candidates.append(
                SemanticCandidate(
                    category="dialogue-pattern",
                    fact_key="dialogue:softened_asks",
                    content="The user often softens or hedges requests before stating them directly.",
                    confidence=0.62,
                )
            )

        if assessment.dialogue_signals.disfluency_score >= 0.45:
            candidates.append(
                SemanticCandidate(
                    category="dialogue-pattern",
                    fact_key="dialogue:hesitation_or_self_correction",
                    content="The user can hesitate or self-correct while speaking and should not be rushed to the endpoint.",
                    confidence=0.68,
                )
            )

        return self._dedupe_semantic_candidates(candidates)

    def _extract_procedural_candidates(
        self,
        user_input: str,
        assessment: Assessment,
    ) -> List[ProceduralCandidate]:
        candidates: List[ProceduralCandidate] = []
        lowered = user_input.lower()

        if assessment.emotional_tone in {"stressed", "grief", "frustrated", "sad"}:
            candidates.append(
                ProceduralCandidate(
                    pattern_key="response:emotional_grounding",
                    content="When the user sounds stressed or emotionally heavy, respond with shorter, calmer, more grounding language first.",
                    confidence=0.80,
                )
            )
        if len(user_input.split()) > 80:
            candidates.append(
                ProceduralCandidate(
                    pattern_key="response:reflect_long_message",
                    content="When the user shares a long detailed message, reflect the core issue before offering advice.",
                    confidence=0.74,
                )
            )
        if "?" in user_input and len(user_input.split()) < 18:
            candidates.append(
                ProceduralCandidate(
                    pattern_key="response:direct_question_first",
                    content="When the user asks a direct question, answer clearly before expanding.",
                    confidence=0.76,
                )
            )
        if "direct communication" in lowered or "concise answers" in lowered:
            candidates.append(
                ProceduralCandidate(
                    pattern_key="style:direct_concise",
                    content="Default to direct, concise communication unless the user asks for more depth.",
                    confidence=0.86,
                )
            )
        if assessment.dialogue_signals.indirectness_score >= 0.55 or assessment.dialogue_signals.ramble_score >= 0.62:
            candidates.append(
                ProceduralCandidate(
                    pattern_key="dialogue:wait_for_the_point",
                    content="If the user circles toward a point or speaks in a longer preamble, let the thought land before reframing or summarizing.",
                    confidence=0.78,
                )
            )
        if assessment.dialogue_signals.disfluency_score >= 0.45:
            candidates.append(
                ProceduralCandidate(
                    pattern_key="dialogue:pause_tolerant_turn_taking",
                    content="If the user hesitates, self-corrects, or sounds disfluent, leave more space before assuming the turn is over.",
                    confidence=0.82,
                )
            )
        if assessment.dialogue_signals.hedging_score >= 0.48:
            candidates.append(
                ProceduralCandidate(
                    pattern_key="dialogue:gentle_intent_inference",
                    content="When the user hedges or softens a request, infer the likely intent gently without forcing them to be sharper than they naturally are.",
                    confidence=0.76,
                )
            )
        return self._dedupe_procedural_candidates(candidates)

    def _extract_graph_facts(
        self,
        text: str,
        semantic_candidates: List[SemanticCandidate],
    ) -> List[GraphFact]:
        facts: List[GraphFact] = []
        lowered = text.lower()

        for candidate in semantic_candidates:
            if candidate.fact_key.startswith("project:"):
                facts.append(
                    GraphFact(
                        source_label="User",
                        target_label=self._extract_fact_target(candidate.content),
                        relation="works_on",
                        source_type="person",
                        target_type="project",
                    )
                )
            elif candidate.fact_key.startswith("goal:"):
                facts.append(
                    GraphFact(
                        source_label="User",
                        target_label=self._extract_fact_target(candidate.content),
                        relation="pursues",
                        source_type="person",
                        target_type="goal",
                        weight=0.46,
                    )
                )
            elif candidate.fact_key == "preference:communication_style":
                facts.append(
                    GraphFact(
                        source_label="User",
                        target_label="Direct Communication",
                        relation="prefers",
                        source_type="person",
                        target_type="preference",
                        weight=0.54,
                    )
                )
            elif candidate.fact_key == "preference:stress_response_style":
                facts.append(
                    GraphFact(
                        source_label="User",
                        target_label="Concise Answers Under Stress",
                        relation="benefits_from",
                        source_type="person",
                        target_type="procedure",
                        weight=0.56,
                    )
                )
            elif candidate.fact_key == "location:home":
                facts.append(
                    GraphFact(
                        source_label="User",
                        target_label=self._extract_location_from_content(candidate.content) or self._extract_fact_target(candidate.content),
                        relation="lives_in",
                        source_type="person",
                        target_type="place",
                        weight=0.72,
                    )
                )

        for match in re.finditer(r"\b(?:with|met|talked to|speaking with|working with)\s+([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?)\b", text):
            facts.append(
                GraphFact(
                    source_label="User",
                    target_label=match.group(1).strip(),
                    relation="connected_to",
                    source_type="person",
                    target_type="person",
                )
            )

        for tool in ["Figma", "Notion", "Linear", "Cursor", "VSCode", "Slack", "Supabase", "Groq", "OpenAI", "Raycast"]:
            if tool.lower() in lowered:
                facts.append(
                    GraphFact(
                        source_label="User",
                        target_label=tool,
                        relation="uses_tool",
                        source_type="person",
                        target_type="tool",
                        weight=0.44,
                    )
                )

        recurring_problem = re.search(r"\b(?:keep struggling with|am stuck on|blocked by|recurring problem is)\s+([^.?!]+)", lowered)
        if recurring_problem:
            facts.append(
                GraphFact(
                    source_label="User",
                    target_label=self._normalize_graph_label(self._clean_fact_value(recurring_problem.group(1))),
                    relation="blocked_by",
                    source_type="person",
                    target_type="problem",
                    weight=0.48,
                )
            )

        habit_match = re.search(r"\b(?:every morning|every day|each day)\b", lowered)
        if habit_match and ("run" in lowered or "write" in lowered or "walk" in lowered):
            habit_label = "Daily Running" if "run" in lowered else "Daily Writing" if "write" in lowered else "Daily Walking"
            facts.append(
                GraphFact(
                    source_label="User",
                    target_label=habit_label,
                    relation="practices",
                    source_type="person",
                    target_type="habit",
                    weight=0.45,
                )
            )

        if "brain with superpowers" in lowered:
            facts.append(
                GraphFact(
                    source_label="User",
                    target_label="Brain With Superpowers",
                    relation="vision_for",
                    source_type="person",
                    target_type="concept",
                    weight=0.48,
                )
            )

        return self._dedupe_graph_facts(facts)

    def _dedupe_semantic_candidates(self, candidates: List[SemanticCandidate]) -> List[SemanticCandidate]:
        seen = {}
        for candidate in candidates:
            candidate = self._canonicalize_semantic_candidate(candidate)
            seen[candidate.fact_key] = candidate
        return list(seen.values())

    def _dedupe_procedural_candidates(self, candidates: List[ProceduralCandidate]) -> List[ProceduralCandidate]:
        seen = {}
        for candidate in candidates:
            seen[candidate.pattern_key] = candidate
        return list(seen.values())

    def _dedupe_graph_facts(self, facts: List[GraphFact]) -> List[GraphFact]:
        seen = {}
        for fact in facts:
            seen[(fact.source_label, fact.target_label, fact.relation)] = fact
        return list(seen.values())

    async def _load_evidence_episodes(self, semantic_rows: List[dict], procedural_rows: List[dict]) -> List[dict]:
        episode_ids = set()
        for row in list(semantic_rows) + list(procedural_rows):
            for episode_id in list(row.get("source_episode_ids") or []):
                episode_ids.add(str(episode_id))

        if not episode_ids:
            return []

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        timestamp,
                        summary,
                        emotional_tone,
                        salience,
                        memory_status,
                        dialogue_signals
                    FROM episodes
                    WHERE id = ANY(%s::uuid[])
                    ORDER BY timestamp DESC
                    """,
                    (list(episode_ids),),
                )
                return await cur.fetchall()

    def _group_evidence_by_memory(
        self,
        semantic_rows: List[dict],
        procedural_rows: List[dict],
        evidence_rows: List[dict],
    ) -> dict[str, list[dict[str, object]]]:
        evidence_lookup = {
            str(row["id"]): {
                "id": str(row["id"]),
                "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                "summary": str(row["summary"]),
                "emotional_tone": str(row["emotional_tone"]),
                "salience": float(row["salience"]),
                "memory_status": str(row["memory_status"]),
                "dialogue_signals": row.get("dialogue_signals") or {},
            }
            for row in evidence_rows
        }

        grouped = {}
        for layer_name, rows in (("semantic", semantic_rows), ("procedural", procedural_rows)):
            for row in rows:
                memory_id = f"{layer_name}:{row['id']}"
                grouped[memory_id] = [
                    evidence_lookup[str(episode_id)]
                    for episode_id in list(row.get("source_episode_ids") or [])
                    if str(episode_id) in evidence_lookup
                ]
        return grouped

    def _build_atlas_nodes(self, semantic_rows: List[dict], procedural_rows: List[dict]) -> List[dict[str, object]]:
        nodes = [
            {
                "id": "user",
                "label": "You",
                "layer": "core",
                "group": "core",
                "status": "pinned",
                "content": "The center of the memory atlas.",
                "strength": 1.0,
                "confidence": 1.0,
                "reinforcement_count": 0,
                "recall_count": 0,
                "updated_at": self._now().isoformat(),
            }
        ]

        for row in semantic_rows:
            if str(row["memory_status"]) not in {"active", "pinned"}:
                continue
            nodes.append(
                {
                    "id": f"semantic:{row['id']}",
                    "label": self._atlas_label(
                        content=str(row["content"]),
                        fact_key=str(row["fact_key"] or ""),
                        pattern_key="",
                    ),
                    "layer": "semantic",
                    "group": self._atlas_group(str(row["fact_key"] or ""), str(row["category"])),
                    "status": str(row["memory_status"]),
                    "content": str(row["content"]),
                    "strength": self._atlas_strength(
                        float(row["confidence"]),
                        int(row["reinforcement_count"]),
                        int(row["recall_count"]),
                    ),
                    "confidence": float(row["confidence"]),
                    "reinforcement_count": int(row["reinforcement_count"]),
                    "recall_count": int(row["recall_count"]),
                    "source_episode_ids": [str(value) for value in list(row.get("source_episode_ids") or [])],
                    "valid_from": row["valid_from"].isoformat() if row.get("valid_from") else None,
                    "valid_to": row["valid_to"].isoformat() if row.get("valid_to") else None,
                    "superseded_by": str(row["superseded_by"]) if row.get("superseded_by") else None,
                    "updated_at": row["last_updated"].isoformat() if row["last_updated"] else None,
                    "archive_reason": row["archive_reason"],
                }
            )

        for row in procedural_rows:
            if str(row["memory_status"]) not in {"active", "pinned"}:
                continue
            nodes.append(
                {
                    "id": f"procedural:{row['id']}",
                    "label": self._atlas_label(
                        content=str(row["content"]),
                        fact_key="",
                        pattern_key=str(row["pattern_key"] or ""),
                    ),
                    "layer": "procedural",
                    "group": "procedure",
                    "status": str(row["memory_status"]),
                    "content": str(row["content"]),
                    "strength": self._atlas_strength(
                        float(row["confidence"]),
                        int(row["reinforcement_count"]),
                        int(row["recall_count"]),
                    ),
                    "confidence": float(row["confidence"]),
                    "reinforcement_count": int(row["reinforcement_count"]),
                    "recall_count": int(row["recall_count"]),
                    "source_episode_ids": [str(value) for value in list(row.get("source_episode_ids") or [])],
                    "valid_from": row["valid_from"].isoformat() if row.get("valid_from") else None,
                    "valid_to": row["valid_to"].isoformat() if row.get("valid_to") else None,
                    "superseded_by": str(row["superseded_by"]) if row.get("superseded_by") else None,
                    "updated_at": row["last_updated"].isoformat() if row["last_updated"] else None,
                    "archive_reason": row["archive_reason"],
                }
            )

        return nodes

    def _build_atlas_edges(self, nodes: List[dict[str, object]]) -> List[dict[str, object]]:
        edges = []
        for node in nodes:
            if node["id"] == "user":
                continue
            edges.append(
                {
                    "id": f"edge:{node['id']}",
                    "source": "user",
                    "target": node["id"],
                    "weight": float(node["strength"]),
                    "relation": str(node["group"]),
                }
            )
        return edges

    def _atlas_label(self, content: str, fact_key: str, pattern_key: str) -> str:
        if fact_key == "goal:primary":
            return self._atlas_phrase_label(content, "User's goal is to ")
        if fact_key == "project:primary":
            return self._atlas_phrase_label(content, "User is building ", "User is working on ")
        if fact_key == "identity:name":
            return content.replace("User's name is ", "").rstrip(".")
        if fact_key == "location:home":
            return self._atlas_phrase_label(content, "User lives in ")
        if fact_key == "preference:communication_style":
            return "Direct Communication"
        if fact_key == "preference:stress_response_style":
            return "Concise Under Stress"
        if fact_key == "pattern:recent_emotional_heaviness":
            return "Grounding Support"

        if pattern_key == "response:emotional_grounding":
            return "Ground First"
        if pattern_key == "response:reflect_long_message":
            return "Reflect Before Advice"
        if pattern_key == "response:direct_question_first":
            return "Answer Directly First"
        if pattern_key == "style:direct_concise":
            return "Direct + Concise"

        trimmed = re.sub(r"^User (?:prefers|wants to|is working on|is building)\s+", "", content)
        trimmed = re.sub(r"^When the user is stressed,\s+", "", trimmed)
        return self._title_compact(trimmed.rstrip("."))

    def _atlas_group(self, fact_key: str, category: str) -> str:
        if fact_key.startswith("goal:"):
            return "goal"
        if fact_key.startswith("project:"):
            return "project"
        if fact_key.startswith("identity:"):
            return "identity"
        if fact_key.startswith("location:"):
            return "identity"
        if fact_key.startswith("preference:"):
            return "preference"
        if fact_key.startswith("pattern:") or category == "state-pattern":
            return "pattern"
        return "concept"

    def _atlas_phrase_label(self, content: str, *prefixes: str) -> str:
        trimmed = content
        for prefix in prefixes:
            trimmed = trimmed.replace(prefix, "")
        return self._title_compact(trimmed.rstrip("."))

    def _atlas_strength(self, confidence: float, reinforcement_count: int, recall_count: int) -> float:
        return min(confidence + (reinforcement_count * 0.035) + (recall_count * 0.025), 1.0)

    def _atlas_episode_title(self, user_input: str) -> str:
        compact = self._clean_sentence(user_input)
        if len(compact) <= 72:
            return compact
        return compact[:69].rstrip() + "..."

    def _title_compact(self, text: str) -> str:
        words = [word for word in re.split(r"\s+", text.strip()) if word]
        compact = " ".join(words[:6])
        if len(words) > 6:
            compact += "..."
        return compact.title() if compact.islower() else compact

    def _extract_fact_target(self, content: str) -> str:
        cleaned = re.sub(r"^User(?:'s goal is to| is (?:working on|building)| prefers| lives in)\s+", "", content)
        cleaned = re.sub(r"^When the user is stressed,\s+", "", cleaned)
        return self._normalize_graph_label(cleaned.rstrip("."))

    def _build_summary(self, user_input: str, agent_response: str) -> str:
        combined = f"User said: {self._clean_sentence(user_input)} Agent replied: {self._clean_sentence(agent_response)}"
        return combined[:500]

    def _resolve_memory_scope(
        self,
        user_input: str,
        conversation_mode: str,
        visibility_scope: Optional[str],
        allowed_modes: Optional[Iterable[str]],
    ) -> MemoryScope:
        normalized_mode = self._normalize_mode(conversation_mode)
        explicit_modes = tuple(self._normalize_mode(mode) for mode in (allowed_modes or []) if mode)
        requested_scope = self._normalize_visibility_scope(visibility_scope) if visibility_scope else None
        inferred_scope = self._infer_scope_from_text(user_input, normalized_mode)

        final_scope = requested_scope or inferred_scope.visibility_scope
        final_modes = explicit_modes or inferred_scope.allowed_modes
        reason = inferred_scope.restricted_reason

        if final_scope in {"restricted", "private"} and not final_modes:
            final_modes = (normalized_mode,)
            reason = reason or "restricted_to_current_mode"

        if final_scope == "global":
            final_modes = ()
            reason = None

        return MemoryScope(
            conversation_mode=normalized_mode,
            visibility_scope=final_scope,
            allowed_modes=tuple(dict.fromkeys(final_modes)),
            restricted_reason=reason,
        )

    def _infer_scope_from_text(self, text: str, current_mode: str) -> MemoryScope:
        lowered = text.lower()
        secrecy_markers = [
            "keep this secret",
            "keep it secret",
            "don't use this in",
            "do not use this in",
            "only use this in",
            "only remember this in",
            "only accessible",
            "between us",
        ]
        if not any(marker in lowered for marker in secrecy_markers):
            return MemoryScope(conversation_mode=current_mode)

        mentioned_modes = self._extract_modes_from_text(lowered)
        allowed_modes = tuple(mentioned_modes or [current_mode])
        return MemoryScope(
            conversation_mode=current_mode,
            visibility_scope="restricted",
            allowed_modes=allowed_modes,
            restricted_reason="user_requested_sealed_memory",
        )

    def _extract_modes_from_text(self, lowered_text: str) -> list[str]:
        aliases = {
            "friend": "friend",
            "close friend": "friend",
            "coach": "coach",
            "life coach": "coach",
            "strategy": "strategy",
            "strategist": "strategy",
            "support": "support",
            "emotional support": "support",
            "therapy": "support",
            "therapist": "support",
            "creative": "creative",
            "technical": "technical",
        }
        modes: list[str] = []
        for phrase, mode in aliases.items():
            if phrase in lowered_text and mode not in modes:
                modes.append(mode)
        return modes

    def _normalize_mode(self, value: str) -> str:
        normalized = self._slug(value or "general")
        return normalized or "general"

    def _normalize_visibility_scope(self, value: str) -> str:
        normalized = (value or "global").strip().lower()
        if normalized in {"restricted", "private", "global"}:
            return normalized
        return "global"

    def _compute_salience(self, user_input: str, assessment: Assessment) -> float:
        score = 0.42
        if assessment.stakes == "high":
            score += 0.25
        if assessment.emotional_tone != "neutral":
            score += 0.18
        if self._should_pin(user_input):
            score = 1.0
        elif self._looks_goal_related(user_input):
            score += 0.12
        if len(user_input.split()) > 50:
            score += 0.06
        return min(score, 1.0)

    def _should_pin(self, text: str) -> bool:
        lowered = text.lower()
        return "always remember" in lowered or "never forget" in lowered or "remember this" in lowered

    def _looks_goal_related(self, text: str) -> bool:
        lowered = text.lower()
        return any(
            marker in lowered
            for marker in ["goal", "working on", "building", "trying to", "want to", "vision", "north star"]
        )

    def _clean_fact_value(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip(" .,!?:;\"'")

    def _extract_home_location(self, text: str) -> Optional[str]:
        patterns = [
            r"\bi\s+(?:do\s+)?(?:currently\s+)?live\s+in\s+([^.!?]+?)(?:,\s*not\b|\s+not\b|[.!?]|$)",
            r"\bmy\s+(?:current\s+)?location\s+is\s+([^.!?]+?)(?:,\s*not\b|\s+not\b|[.!?]|$)",
            r"\bmy\s+home\s+is\s+in\s+([^.!?]+?)(?:,\s*not\b|\s+not\b|[.!?]|$)",
            r"\bi(?:'m| am)\s+based\s+in\s+([^.!?]+?)(?:,\s*not\b|\s+not\b|[.!?]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            location = self._normalize_location(match.group(1))
            if self._looks_like_location(location):
                return location
        return None

    def _normalize_location(self, value: str) -> str:
        cleaned = self._clean_fact_value(value)
        cleaned = re.sub(r"\b(?:actually|currently|right now)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
        parts = [part.strip() for part in cleaned.split(",") if part.strip()]
        if not parts:
            return ""
        normalized_parts = []
        for part in parts[:3]:
            if len(part) <= 3 and part.isupper():
                normalized_parts.append(part)
            else:
                normalized_parts.append(part.title() if part.islower() else part)
        return ", ".join(normalized_parts)

    def _looks_like_location(self, value: str) -> bool:
        if not value or len(value) < 3:
            return False
        lowered = value.lower()
        if "," in value:
            return True
        location_terms = {
            "california", "pleasanton", "new york", "texas", "florida", "washington",
            "oregon", "nevada", "arizona", "colorado", "massachusetts", "illinois",
            "canada", "brazil", "portugal", "london", "paris", "berlin", "tokyo",
        }
        return any(term in lowered for term in location_terms)

    def _extract_location_from_content(self, content: str) -> Optional[str]:
        match = re.search(r"^User lives in (.+?)\.$", content)
        if not match:
            return None
        return self._normalize_location(match.group(1))

    def _clean_sentence(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _normalize_graph_label(self, text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip(" .,!?:;\"'")
        return cleaned.title() if cleaned.islower() else cleaned

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    def _table_for_layer(self, layer: str) -> str:
        normalized = layer.strip().lower()
        mapping = {
            "episodic": "episodes",
            "episode": "episodes",
            "episodes": "episodes",
            "semantic": "semantic_memories",
            "semantics": "semantic_memories",
            "procedural": "procedural_memories",
            "procedure": "procedural_memories",
            "procedures": "procedural_memories",
        }
        if normalized not in mapping:
            raise ValueError(f"Unsupported memory layer: {layer}")
        return mapping[normalized]

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)


@lru_cache
def get_memory_service() -> LayeredMemoryService:
    return LayeredMemoryService()
