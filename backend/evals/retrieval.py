from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from core.agent import AgentOrchestrator
from models.memory import RetrievedMemory


@dataclass(frozen=True)
class RetrievalEvalScenario:
    key: str
    query: str
    mode: str = "general"
    expected_kinds: tuple[str, ...] = ()
    expected_terms: tuple[str, ...] = ()
    forbidden_scopes: tuple[str, ...] = ()
    minimum_memories: int = 1
    require_mention: bool = True


DEFAULT_RETRIEVAL_EVALS: tuple[RetrievalEvalScenario, ...] = (
    RetrievalEvalScenario(
        key="stress_support",
        query="How should you respond when I am stressed or overwhelmed?",
        expected_kinds=("semantic", "procedural"),
        expected_terms=("stressed", "overwhelmed", "grounding", "calm", "short", "direct"),
    ),
    RetrievalEvalScenario(
        key="primary_goal",
        query="What is my main goal with this AI companion project?",
        expected_kinds=("semantic", "graph", "episodic"),
        expected_terms=("goal", "ai companion", "memory", "building", "project"),
    ),
    RetrievalEvalScenario(
        key="communication_style",
        query="What communication style usually works best for me?",
        expected_kinds=("semantic", "procedural"),
        expected_terms=("direct", "concise", "communication", "depth"),
    ),
    RetrievalEvalScenario(
        key="remembered_location_for_weather",
        query="What's the weather outside?",
        expected_kinds=("semantic",),
        expected_terms=("pleasanton", "california"),
    ),
    RetrievalEvalScenario(
        key="archive_recall",
        query="What did I tell you before about the companion feeling like a brain with superpowers?",
        expected_kinds=("episodic", "semantic"),
        expected_terms=("brain", "superpowers", "companion", "memory"),
    ),
    RetrievalEvalScenario(
        key="scoped_mode_guard",
        query="In coach mode, what should you know about me?",
        mode="coach",
        expected_kinds=("semantic", "procedural", "episodic"),
        forbidden_scopes=("private",),
        minimum_memories=0,
        require_mention=False,
    ),
)


@dataclass
class RetrievalEvalResult:
    key: str
    query: str
    mode: str
    passed: bool
    score: float
    checks: dict[str, bool]
    memory_count: int
    top_memories: list[dict[str, object]] = field(default_factory=list)


class RetrievalEvalRunner:
    def __init__(self, agent: AgentOrchestrator) -> None:
        self.agent = agent

    async def run(
        self,
        user_id: str,
        scenarios: Optional[tuple[RetrievalEvalScenario, ...]] = None,
    ) -> dict[str, object]:
        selected = scenarios or DEFAULT_RETRIEVAL_EVALS
        results = [
            await self._run_scenario(user_id=user_id, scenario=scenario)
            for scenario in selected
        ]
        passed = sum(1 for result in results if result.passed)
        return {
            "user_id": user_id,
            "passed": passed,
            "total": len(results),
            "pass_rate": round(passed / max(len(results), 1), 3),
            "results": [asdict(result) for result in results],
        }

    async def _run_scenario(
        self,
        user_id: str,
        scenario: RetrievalEvalScenario,
    ) -> RetrievalEvalResult:
        preview = await self.agent.preview_context(
            user_id=user_id,
            user_input=scenario.query,
            conversation_mode=scenario.mode,
        )
        memories = [
            RetrievedMemory.model_validate(memory)
            for memory in list(preview.get("memories") or [])
        ]
        content_blob = " ".join(memory.content.lower() for memory in memories)
        kinds = {memory.kind for memory in memories}
        scopes = {memory.visibility_scope for memory in memories}
        mention_count = sum(1 for memory in memories if memory.use == "mention")

        checks = {
            "minimum_memories": len(memories) >= scenario.minimum_memories,
            "expected_kind": not scenario.expected_kinds or bool(kinds.intersection(scenario.expected_kinds)),
            "expected_terms": not scenario.expected_terms or any(term in content_blob for term in scenario.expected_terms),
            "no_forbidden_scopes": not bool(scopes.intersection(scenario.forbidden_scopes)),
            "has_mention": (mention_count > 0) if scenario.require_mention else True,
        }
        score = sum(1 for passed in checks.values() if passed) / max(len(checks), 1)

        return RetrievalEvalResult(
            key=scenario.key,
            query=scenario.query,
            mode=scenario.mode,
            passed=all(checks.values()),
            score=round(score, 3),
            checks=checks,
            memory_count=len(memories),
            top_memories=[
                {
                    "kind": memory.kind,
                    "use": memory.use,
                    "scope": memory.visibility_scope,
                    "score": round(memory.score, 3),
                    "confidence": memory.confidence,
                    "content": self._truncate(memory.content),
                }
                for memory in memories[:5]
            ],
        )

    def _truncate(self, text: str, limit: int = 220) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "..."
