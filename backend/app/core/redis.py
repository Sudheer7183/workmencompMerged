from __future__ import annotations

import structlog
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Module-level pool — created once at startup, shared across all requests.
# ---------------------------------------------------------------------------

_redis_pool: ConnectionPool | None = None
_redis_client: Redis | None = None  # type: ignore[type-arg]


def initialise_redis() -> None:
    """
    Creates the Redis connection pool and client.
    Called once from the FastAPI lifespan context manager.
    """
    global _redis_pool, _redis_client

    settings = get_settings()

    _redis_pool = ConnectionPool.from_url(
        settings.REDIS_URL,
        max_connections=20,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )

    _redis_client = Redis(connection_pool=_redis_pool)
    logger.info("redis.initialised", url=settings.REDIS_URL)


async def dispose_redis() -> None:
    """
    Closes all Redis connections in the pool.
    Called from the FastAPI lifespan context manager on shutdown.
    """
    global _redis_pool, _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        logger.info("redis.disposed")
    if _redis_pool is not None:
        await _redis_pool.aclose()


def get_redis() -> Redis:  # type: ignore[type-arg]
    """
    Returns the shared Redis client.
    Raises RuntimeError if called before initialise_redis().

    Phase 1 note: Redis is wired but endpoints return live DB data.
    Caching is activated in Phase 2+.
    """
    if _redis_client is None:
        raise RuntimeError(
            "Redis client not initialised. "
            "Ensure initialise_redis() was called in the application lifespan."
        )
    return _redis_client


async def redis_health_check() -> bool:
    """
    Pings Redis to verify connectivity.
    Used by the /health endpoint.
    """
    try:
        client = get_redis()
        await client.ping()
        return True
    except RedisError as exc:
        logger.warning("redis.health_check.failed", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# FastAPI dependency — injects the shared Redis client into route handlers.
# ---------------------------------------------------------------------------


def get_redis_dep() -> Redis:  # type: ignore[type-arg]
    """
    FastAPI dependency for injecting the Redis client.
    Usage: redis: Redis = Depends(get_redis_dep)
    """
    return get_redis()

# ---------------------------------------------------------------------------
# Alias — Phase 2 services import get_redis_client by convention.
# Both names refer to the same underlying function.
# ---------------------------------------------------------------------------

get_redis_client = get_redis_dep