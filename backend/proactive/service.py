from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from db.postgres import get_database
from models.proactive import ProactiveInsight


MIN_SURFACE_IMPORTANCE = 0.86


@dataclass
class InsightCandidate:
    insight_key: str
    category: str
    title: str
    content: str
    importance: float
    source_memory_ids: list[str]
    cooldown_hours: int = 24
    expires_after_hours: int = 72


class ProactiveService:
    def __init__(self) -> None:
        self.db = get_database()

    async def list_user_ids(self) -> list[str]:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT DISTINCT user_id
                    FROM (
                        SELECT user_id FROM episodes
                        UNION
                        SELECT user_id FROM semantic_memories
                        UNION
                        SELECT user_id FROM procedural_memories
                        UNION
                        SELECT user_id FROM graph_nodes
                    ) AS known_users
                    ORDER BY user_id
                    """
                )
                rows = await cur.fetchall()
        return [str(row["user_id"]) for row in rows if row["user_id"]]

    async def list_insights(
        self,
        user_id: str,
        status: Optional[str] = None,
        limit: int = 10,
    ) -> list[ProactiveInsight]:
        sql = """
            SELECT
                id::text AS id,
                user_id,
                insight_key,
                category,
                title,
                content,
                importance,
                status,
                source_memory_ids,
                metadata,
                created_at,
                updated_at,
                expires_at
            FROM proactive_insights
            WHERE user_id = %s
        """
        params: list[object] = [user_id]
        if status:
            sql += " AND status = %s"
            params.append(status)

        sql += " ORDER BY importance DESC, created_at DESC LIMIT %s"
        params.append(limit)

        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, params)
                rows = await cur.fetchall()

        return [self._row_to_insight(row) for row in rows]

    async def latest_pending_insight(self, user_id: str) -> Optional[ProactiveInsight]:
        await self._expire_low_value_pending(user_id)
        insights = await self.list_insights(user_id=user_id, status="pending", limit=1)
        surfaceable = [insight for insight in insights if insight.importance >= MIN_SURFACE_IMPORTANCE]
        return surfaceable[0] if surfaceable else None

    async def dismiss_insight(self, insight_id: str) -> Optional[ProactiveInsight]:
        return await self._set_insight_status(insight_id=insight_id, status="dismissed")

    async def mark_delivered(self, insight_id: str) -> Optional[ProactiveInsight]:
        return await self._set_insight_status(insight_id=insight_id, status="delivered")

    async def scan_all_users(self) -> dict[str, int]:
        users = await self.list_user_ids()
        created = 0
        for user_id in users:
            created += await self.scan_user(user_id)
        return {"users_scanned": len(users), "insights_created": created}

    async def scan_user(self, user_id: str) -> int:
        await self._expire_stale_insights(user_id)
        context = await self._load_user_context(user_id)
        candidates = self._build_candidates(context)
        created = 0

        for candidate in candidates:
            if candidate.importance < MIN_SURFACE_IMPORTANCE:
                continue
            if await self._should_skip_candidate(user_id, candidate):
                continue
            await self._insert_candidate(user_id, candidate)
            created += 1

        return created

    async def _load_user_context(self, user_id: str) -> dict[str, object]:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        content,
                        fact_key,
                        category,
                        confidence,
                        reinforcement_count,
                        recall_count,
                        memory_status,
                        last_updated
                    FROM semantic_memories
                    WHERE user_id = %s
                      AND memory_status IN ('active', 'pinned')
                      AND visibility_scope = 'global'
                    ORDER BY confidence DESC, reinforcement_count DESC, last_updated DESC
                    """,
                    (user_id,),
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
                        last_updated
                    FROM procedural_memories
                    WHERE user_id = %s
                      AND memory_status IN ('active', 'pinned')
                      AND visibility_scope = 'global'
                    ORDER BY confidence DESC, reinforcement_count DESC, last_updated DESC
                    """,
                    (user_id,),
                )
                procedural_rows = await cur.fetchall()

                await cur.execute(
                    """
                    SELECT
                        id::text AS id,
                        timestamp,
                        emotional_tone,
                        salience,
                        summary
                    FROM episodes
                    WHERE user_id = %s
                      AND visibility_scope = 'global'
                    ORDER BY timestamp DESC
                    LIMIT 12
                    """,
                    (user_id,),
                )
                recent_episodes = await cur.fetchall()

        return {
            "semantic": semantic_rows,
            "procedural": procedural_rows,
            "episodes": recent_episodes,
        }

    def _build_candidates(self, context: dict[str, object]) -> list[InsightCandidate]:
        semantic_rows = list(context["semantic"])
        procedural_rows = list(context["procedural"])
        recent_episodes = list(context["episodes"])

        semantic_by_key = {
            str(row["fact_key"]): row
            for row in semantic_rows
            if row.get("fact_key")
        }
        procedural_by_key = {
            str(row["pattern_key"]): row
            for row in procedural_rows
            if row.get("pattern_key")
        }

        candidates: list[InsightCandidate] = []

        goal_row = semantic_by_key.get("goal:primary")
        if goal_row:
            goal_phrase = self._strip_prefixes(
                str(goal_row["content"]),
                "User's goal is to ",
                "User wants to ",
            ).rstrip(".")
            candidates.append(
                InsightCandidate(
                    insight_key="goal:primary:focus",
                    category="goal",
                    title="Keep the north star concrete",
                    content=(
                        f"Your main goal is still to {goal_phrase}. "
                        "The strongest next move is to turn that into one concrete milestone for today."
                    ),
                    importance=0.78,
                    source_memory_ids=[str(goal_row["id"])],
                    cooldown_hours=18,
                )
            )

        recent_stress = [
            row
            for row in recent_episodes
            if str(row["emotional_tone"]) in {"stressed", "grief", "frustrated", "sad"}
        ]
        stress_pref = semantic_by_key.get("preference:stress_response_style")
        grounding_pattern = semantic_by_key.get("pattern:recent_emotional_heaviness")
        grounding_procedure = procedural_by_key.get("response:emotional_grounding")

        grounding_evidence = [stress_pref, grounding_pattern, grounding_procedure]
        if recent_stress and any(row is not None for row in grounding_evidence):
            source_ids = [
                str(row["id"])
                for row in [*recent_stress[:3], *grounding_evidence]
                if row is not None
            ]
            candidates.append(
                InsightCandidate(
                    insight_key="support:grounding",
                    category="support",
                    title="I can keep this lighter",
                    content=(
                        "This feels like a moment where less may help more. "
                        "I can keep the next exchange short, calm, and practical instead of adding more noise."
                    ),
                    importance=0.9,
                    source_memory_ids=source_ids,
                    cooldown_hours=10,
                    expires_after_hours=24,
                )
            )

        communication_pref = semantic_by_key.get("preference:communication_style")
        direct_style = procedural_by_key.get("style:direct_concise")
        if communication_pref and direct_style:
            candidates.append(
                InsightCandidate(
                    insight_key="relationship:communication-calibration",
                    category="relationship",
                    title="Communication style is calibrated",
                    content=(
                        "The companion has a stable read on your style: direct by default, concise unless you ask for more depth."
                    ),
                    importance=0.58,
                    source_memory_ids=[str(communication_pref["id"]), str(direct_style["id"])],
                    cooldown_hours=36,
                    expires_after_hours=72,
                )
            )

        return candidates

    async def _should_skip_candidate(self, user_id: str, candidate: InsightCandidate) -> bool:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    SELECT
                        id,
                        status,
                        created_at
                    FROM proactive_insights
                    WHERE user_id = %s
                      AND insight_key = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (user_id, candidate.insight_key),
                )
                existing = await cur.fetchone()

        if not existing:
            return False

        created_at = existing["created_at"]
        if existing["status"] == "pending":
            return True
        if created_at and created_at > self._now() - timedelta(hours=candidate.cooldown_hours):
            return True
        return False

    async def _insert_candidate(self, user_id: str, candidate: InsightCandidate) -> None:
        expires_at = self._now() + timedelta(hours=candidate.expires_after_hours)
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO proactive_insights (
                        user_id,
                        insight_key,
                        category,
                        title,
                        content,
                        importance,
                        status,
                        source_memory_ids,
                        metadata,
                        expires_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, '{}'::jsonb, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        user_id,
                        candidate.insight_key,
                        candidate.category,
                        candidate.title,
                        candidate.content,
                        candidate.importance,
                        candidate.source_memory_ids,
                        expires_at,
                    ),
                )
            await conn.commit()

    async def _expire_stale_insights(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE proactive_insights
                    SET status = 'expired',
                        updated_at = NOW()
                    WHERE user_id = %s
                      AND status = 'pending'
                      AND expires_at IS NOT NULL
                      AND expires_at < NOW()
                    """,
                    (user_id,),
                )
            await conn.commit()

    async def _expire_low_value_pending(self, user_id: str) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE proactive_insights
                    SET status = 'expired',
                        updated_at = NOW()
                    WHERE user_id = %s
                      AND status = 'pending'
                      AND importance < %s
                    """,
                    (user_id, MIN_SURFACE_IMPORTANCE),
                )
            await conn.commit()

    async def _set_insight_status(self, insight_id: str, status: str) -> Optional[ProactiveInsight]:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE proactive_insights
                    SET status = %s,
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    RETURNING
                        id::text AS id,
                        user_id,
                        insight_key,
                        category,
                        title,
                        content,
                        importance,
                        status,
                        source_memory_ids,
                        metadata,
                        created_at,
                        updated_at,
                        expires_at
                    """,
                    (status, insight_id),
                )
                row = await cur.fetchone()
            await conn.commit()
        return self._row_to_insight(row) if row else None

    def _row_to_insight(self, row: dict) -> ProactiveInsight:
        return ProactiveInsight(
            id=str(row["id"]),
            user_id=str(row["user_id"]),
            insight_key=str(row["insight_key"]),
            category=str(row["category"]),
            title=str(row["title"]),
            content=str(row["content"]),
            importance=float(row["importance"]),
            status=str(row["status"]),
            created_at=row["created_at"].isoformat() if row["created_at"] else None,
            updated_at=row["updated_at"].isoformat() if row["updated_at"] else None,
            expires_at=row["expires_at"].isoformat() if row["expires_at"] else None,
            source_memory_ids=[str(item) for item in list(row["source_memory_ids"] or [])],
            metadata=dict(row["metadata"] or {}),
        )

    def _strip_prefixes(self, text: str, *prefixes: str) -> str:
        stripped = text
        for prefix in prefixes:
            stripped = stripped.replace(prefix, "")
        return stripped

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)


_service: Optional[ProactiveService] = None


def get_proactive_service() -> ProactiveService:
    global _service
    if _service is None:
        _service = ProactiveService()
    return _service
