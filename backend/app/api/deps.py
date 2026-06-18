from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncPublicSession, get_db as _get_db_from_core
from app.core.redis import get_redis


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a tenant-scoped async database session.
    search_path is set to the resolved tenant schema by the core implementation.
    Re-exported here so route files import from a single stable location.
    """
    async for session in _get_db_from_core(request):
        yield session


async def get_public_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a public-schema database session.
    Used by all /platform/* endpoints which operate only on public schema tables.
    No tenant context is required.
    """
    async with AsyncPublicSession() as session:
        await session.execute(text("SET search_path TO public"))
        yield session


def get_redis_dep() -> Redis:  # type: ignore[type-arg]
    """
    FastAPI dependency — returns the shared Redis client.
    Routes that need Redis (e.g. dashboard cache, rate limiting) use this.
    The client is initialised once at startup in core.redis.
    """
    return get_redis()
