from __future__ import annotations

from memory.service import get_memory_service
from proactive.service import get_proactive_service


async def run_consolidation_cycle() -> dict[str, int]:
    proactive = get_proactive_service()
    memory = get_memory_service()
    users = await proactive.list_user_ids()

    consolidated = 0
    for user_id in users:
        await memory.consolidate_user(user_id)
        consolidated += 1

    return {
        "users_scanned": len(users),
        "users_consolidated": consolidated,
    }


async def run_proactive_scan_cycle() -> dict[str, int]:
    proactive = get_proactive_service()
    return await proactive.scan_all_users()
