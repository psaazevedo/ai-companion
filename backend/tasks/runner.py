from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Awaitable, Callable, Optional

from config import get_settings
from db.postgres import get_database
from tasks.jobs import run_consolidation_cycle, run_proactive_scan_cycle


class BackgroundRunner:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.db = get_database()
        self._tasks: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started or not self.settings.background_runner_enabled:
            return

        self._started = True
        self._tasks = [
            asyncio.create_task(
                self._loop(
                    job_name="memory-consolidation",
                    interval_seconds=self.settings.consolidation_interval_seconds,
                    job=run_consolidation_cycle,
                ),
                name="memory-consolidation",
            ),
            asyncio.create_task(
                self._loop(
                    job_name="proactive-scan",
                    interval_seconds=self.settings.proactive_scan_interval_seconds,
                    job=run_proactive_scan_cycle,
                ),
                name="proactive-scan",
            ),
        ]

    async def stop(self) -> None:
        if not self._started:
            return

        self._started = False
        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def _loop(
        self,
        job_name: str,
        interval_seconds: int,
        job: Callable[[], Awaitable[dict[str, int]]],
    ) -> None:
        try:
            while True:
                await self._run_job(job_name, job)
                await asyncio.sleep(max(interval_seconds, 30))
        except asyncio.CancelledError:
            raise

    async def _run_job(
        self,
        job_name: str,
        job: Callable[[], Awaitable[dict[str, int]]],
    ) -> None:
        lock_key = self._lock_key(job_name)
        if not await self._try_acquire_lock(lock_key):
            return

        run_id: Optional[str] = None
        try:
            run_id = await self._record_start(job_name)
            details = await job()
            await self._record_finish(run_id, status="ok", details=details)
        except asyncio.CancelledError:
            if run_id:
                await self._record_finish(run_id, status="cancelled", details={})
            raise
        except Exception as exc:
            if run_id:
                await self._record_finish(
                    run_id,
                    status="failed",
                    details={"error": str(exc)},
                )
        finally:
            await self._release_lock(lock_key)

    async def _try_acquire_lock(self, lock_key: int) -> bool:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT pg_try_advisory_lock(%s) AS locked", (lock_key,))
                row = await cur.fetchone()
        return bool(row["locked"]) if row else False

    async def _release_lock(self, lock_key: int) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))

    async def _record_start(self, job_name: str) -> str:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO background_job_runs (job_name, scope, status, details)
                    VALUES (%s, 'global', 'running', '{}'::jsonb)
                    RETURNING id::text AS id
                    """,
                    (job_name,),
                )
                row = await cur.fetchone()
            await conn.commit()
        return str(row["id"])

    async def _record_finish(self, run_id: str, status: str, details: dict[str, object]) -> None:
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    UPDATE background_job_runs
                    SET status = %s,
                        details = %s::jsonb,
                        finished_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (status, json.dumps(details), run_id),
                )
            await conn.commit()

    def _lock_key(self, job_name: str) -> int:
        digest = hashlib.sha1(job_name.encode("utf-8")).hexdigest()
        return int(digest[:15], 16)


_runner: Optional[BackgroundRunner] = None


def get_background_runner() -> BackgroundRunner:
    global _runner
    if _runner is None:
        _runner = BackgroundRunner()
    return _runner
