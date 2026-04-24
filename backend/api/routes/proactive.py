from __future__ import annotations

from fastapi import APIRouter, HTTPException

from proactive.service import get_proactive_service

router = APIRouter(prefix="/proactive", tags=["proactive"])


@router.get("/insights/{user_id}")
async def proactive_insights(user_id: str) -> dict[str, object]:
    service = get_proactive_service()
    insights = await service.list_insights(user_id=user_id, limit=12)
    return {
        "user_id": user_id,
        "insights": [insight.model_dump() for insight in insights],
    }


@router.get("/latest/{user_id}")
async def proactive_latest(user_id: str) -> dict[str, object]:
    service = get_proactive_service()
    insight = await service.latest_pending_insight(user_id=user_id)
    return {
        "user_id": user_id,
        "insight": insight.model_dump() if insight else None,
    }


@router.post("/scan/{user_id}")
async def proactive_scan(user_id: str) -> dict[str, object]:
    service = get_proactive_service()
    created = await service.scan_user(user_id=user_id)
    latest = await service.latest_pending_insight(user_id=user_id)
    return {
        "user_id": user_id,
        "insights_created": created,
        "latest": latest.model_dump() if latest else None,
    }


@router.post("/insights/{insight_id}/dismiss")
async def proactive_dismiss(insight_id: str) -> dict[str, object]:
    service = get_proactive_service()
    insight = await service.dismiss_insight(insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"insight": insight.model_dump()}


@router.post("/insights/{insight_id}/delivered")
async def proactive_delivered(insight_id: str) -> dict[str, object]:
    service = get_proactive_service()
    insight = await service.mark_delivered(insight_id)
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    return {"insight": insight.model_dump()}
