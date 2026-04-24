from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from memory.service import get_memory_service

router = APIRouter(prefix="/memory", tags=["memory"])


class CorrectMemoryRequest(BaseModel):
    content: str
    replacement_key: Optional[str] = None


class ArchiveMemoryRequest(BaseModel):
    reason: str = "manual_archive"


class MergeMemoryRequest(BaseModel):
    source_id: str
    target_id: str


@router.get("/stats/{user_id}")
async def memory_stats(user_id: str) -> dict[str, object]:
    memory = get_memory_service()
    return {
        "user_id": user_id,
        "layers": await memory.stats(user_id),
    }


@router.get("/search/{user_id}")
async def memory_search(user_id: str, q: str) -> dict[str, object]:
    memory = get_memory_service()
    results = await memory.retrieve_context(user_id=user_id, query=q)
    return {
        "user_id": user_id,
        "query": q,
        "results": [result.model_dump() for result in results],
    }


@router.get("/atlas/{user_id}")
async def memory_atlas(user_id: str) -> dict[str, object]:
    memory = get_memory_service()
    return await memory.atlas_snapshot(user_id)


@router.get("/conversation/{user_id}")
async def memory_conversation(user_id: str, limit: int = 40) -> dict[str, object]:
    memory = get_memory_service()
    return await memory.conversation_feed(user_id=user_id, limit=limit)


@router.post("/consolidate/{user_id}")
async def memory_consolidate(user_id: str) -> dict[str, object]:
    memory = get_memory_service()
    await memory.consolidate_user(user_id)
    return {
        "user_id": user_id,
        "status": "ok",
        "layers": await memory.stats(user_id),
    }


@router.get("/evals/{user_id}")
async def memory_evals(user_id: str) -> dict[str, object]:
    memory = get_memory_service()
    return await memory.run_retrieval_evals(user_id)


@router.get("/dialogue-profile/{user_id}")
async def memory_dialogue_profile(user_id: str) -> dict[str, object]:
    memory = get_memory_service()
    return await memory.dialogue_profile(user_id)


@router.post("/{layer}/{memory_id}/pin")
async def memory_pin(layer: str, memory_id: str) -> dict[str, object]:
    memory = get_memory_service()
    try:
        row = await memory.pin_memory(layer=layer, memory_id=memory_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"memory": row}


@router.post("/{layer}/{memory_id}/archive")
async def memory_archive(layer: str, memory_id: str, payload: ArchiveMemoryRequest) -> dict[str, object]:
    memory = get_memory_service()
    try:
        row = await memory.archive_memory(layer=layer, memory_id=memory_id, reason=payload.reason)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"memory": row}


@router.post("/{layer}/{memory_id}/outdated")
async def memory_outdated(layer: str, memory_id: str) -> dict[str, object]:
    memory = get_memory_service()
    try:
        row = await memory.mark_memory_outdated(layer=layer, memory_id=memory_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"memory": row}


@router.post("/{layer}/{memory_id}/correct")
async def memory_correct(layer: str, memory_id: str, payload: CorrectMemoryRequest) -> dict[str, object]:
    memory = get_memory_service()
    try:
        row = await memory.correct_memory(
            layer=layer,
            memory_id=memory_id,
            new_content=payload.content,
            replacement_key=payload.replacement_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"memory": row}


@router.post("/{layer}/merge")
async def memory_merge(layer: str, payload: MergeMemoryRequest) -> dict[str, object]:
    memory = get_memory_service()
    try:
        row = await memory.merge_memories(layer=layer, source_id=payload.source_id, target_id=payload.target_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"memory": row}
