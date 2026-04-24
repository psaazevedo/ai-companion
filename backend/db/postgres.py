from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from config import get_settings


class PostgresDatabase:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.pool = AsyncConnectionPool(
            conninfo=self.settings.database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={
                "row_factory": dict_row,
                "autocommit": False,
            },
        )

    async def open(self) -> None:
        await self.pool.open()
        await self.pool.wait()
        await self.initialize_schema()

    async def close(self) -> None:
        await self.pool.close()

    @asynccontextmanager
    async def connection(self):
        async with self.pool.connection() as conn:
            yield conn

    async def initialize_schema(self) -> None:
        schema_path = Path(__file__).with_name("schema.sql")
        schema_sql = schema_path.read_text(encoding="utf-8").replace(
            "__EMBEDDING_DIMENSIONS__",
            str(self.settings.embedding_dimensions),
        )
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(schema_sql)
            await conn.commit()


_database: Optional[PostgresDatabase] = None


def get_database() -> PostgresDatabase:
    global _database
    if _database is None:
        _database = PostgresDatabase()
    return _database
