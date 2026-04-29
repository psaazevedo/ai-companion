from __future__ import annotations

from fastapi import APIRouter

from evals.retrieval import RetrievalEvalRunner
from core.agent import get_agent

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/context-preview/{user_id}")
async def context_preview(user_id: str, q: str, mode: str = "general") -> dict[str, object]:
    agent = get_agent()
    return await agent.preview_context(
        user_id=user_id,
        user_input=q,
        conversation_mode=mode,
    )


@router.get("/modes")
async def agent_modes() -> dict[str, object]:
    agent = get_agent()
    return {"modes": agent.available_modes()}


@router.get("/retrieval-evals/{user_id}")
async def retrieval_evals(user_id: str) -> dict[str, object]:
    agent = get_agent()
    runner = RetrievalEvalRunner(agent)
    return await runner.run(user_id=user_id)
