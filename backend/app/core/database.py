# from __future__ import annotations

# from collections.abc import AsyncGenerator
# from typing import TYPE_CHECKING
# from contextlib import asynccontextmanager
# import structlog
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import (
#     AsyncEngine,
#     AsyncSession,
#     async_sessionmaker,
#     create_async_engine,
# )
# from sqlalchemy.orm import DeclarativeBase

# from app.core.config import get_settings

# if TYPE_CHECKING:
#     from starlette.requests import Request

# logger = structlog.get_logger(__name__)

# # ---------------------------------------------------------------------------
# # Declarative base — all ORM models inherit from this.
# # ---------------------------------------------------------------------------


# class Base(DeclarativeBase):
#     """
#     Shared declarative base for all SQLAlchemy 2.0 ORM models.
#     No legacy Column() usage permitted — Mapped[T] + mapped_column() only.
#     """


# # ---------------------------------------------------------------------------
# # Async engine — created once at application startup via lifespan.
# # ---------------------------------------------------------------------------

# _engine: AsyncEngine | None = None
# _AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None

# # A separate session factory bound to the PUBLIC schema only.
# # Used by TenantMiddleware to resolve tenants without contaminating
# # the per-request tenant session.
# _AsyncPublicSessionLocal: async_sessionmaker[AsyncSession] | None = None


# def build_engine() -> AsyncEngine:
#     """
#     Creates the async SQLAlchemy engine from settings.
#     Must be called once during application startup (lifespan).
#     """
#     settings = get_settings()
#     engine = create_async_engine(
#         settings.DATABASE_URL,
#         echo=settings.is_development,
#         pool_size=10,
#         max_overflow=20,
#         pool_pre_ping=True,
#         pool_recycle=3600,
#         # Set search_path at the PostgreSQL connection level via asyncpg's
#         # server_settings. This persists across all commits on the connection
#         # and eliminates the need to re-assert SET search_path after every
#         # db.commit() call. Individual requests override this via get_db().
#         connect_args={
#             "server_settings": {
#                 "search_path": "public"
#             }
#         },
#     )
#     return engine


# def build_tenant_engine(schema_name: str) -> AsyncEngine:
#     """
#     Creates a short-lived async engine scoped to a specific tenant schema.
#     The search_path is set at the asyncpg connection level via server_settings,
#     so it persists across all db.commit() calls without manual re-assertion.

#     Used exclusively by background tasks (approve_mapping pipeline) where
#     no HTTP Request object is available to drive the TenantMiddleware.
#     """
#     settings = get_settings()
#     return create_async_engine(
#         settings.DATABASE_URL,
#         echo=False,
#         pool_size=2,
#         max_overflow=2,
#         pool_pre_ping=True,
#         connect_args={
#             "server_settings": {
#                 "search_path": f'"{schema_name}",public'
#             }
#         },
#     )

# def initialise_db() -> None:
#     """
#     Initialises the module-level engine and session factories.
#     Called once from the FastAPI lifespan context manager.
#     """
#     global _engine, _AsyncSessionLocal, _AsyncPublicSessionLocal

#     _engine = build_engine()

#     _AsyncSessionLocal = async_sessionmaker(
#         bind=_engine,
#         class_=AsyncSession,
#         expire_on_commit=False,
#         autoflush=False,
#         autocommit=False,
#     )

#     # Public-schema session factory — TenantMiddleware only.
#     _AsyncPublicSessionLocal = async_sessionmaker(
#         bind=_engine,
#         class_=AsyncSession,
#         expire_on_commit=False,
#         autoflush=False,
#         autocommit=False,
#     )

#     logger.info("database.initialised", pool_size=10, max_overflow=20)


# async def dispose_db() -> None:
#     """
#     Disposes the engine and closes all pooled connections.
#     Called from the FastAPI lifespan context manager on shutdown.
#     """
#     global _engine
#     if _engine is not None:
#         await _engine.dispose()
#         logger.info("database.disposed")


# def get_engine() -> AsyncEngine:
#     if _engine is None:
#         raise RuntimeError(
#             "Database engine not initialised. "
#             "Ensure initialise_db() was called in the application lifespan."
#         )
#     return _engine


# # ---------------------------------------------------------------------------
# # Public-schema session — used by TenantMiddleware only.
# # ---------------------------------------------------------------------------

# class AsyncPublicSession:
#     """
#     Async context manager that yields a session scoped to the public schema.
#     """

#     async def __aenter__(self) -> AsyncSession:
#         if _AsyncPublicSessionLocal is None:
#             raise RuntimeError("Database not initialised.")
#         self._session = _AsyncPublicSessionLocal()
#         # Clear any aborted transaction state from the pooled connection
#         try:
#             await self._session.execute(text("ROLLBACK"))
#         except Exception:
#             pass
#         await self._session.execute(text("SET search_path TO public"))
#         return self._session

#     async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
#         try:
#             if exc_type is not None:
#                 await self._session.rollback()
#         finally:
#             await self._session.close()
# # ---------------------------------------------------------------------------
# # Per-request session dependency — injected into every protected endpoint.
# # search_path is set to the resolved tenant schema so all ORM queries are
# # automatically scoped to the correct tenant — zero cross-tenant leakage.
# # ---------------------------------------------------------------------------


# async def get_db(request: "Request") -> AsyncGenerator[AsyncSession, None]:
#     """
#     FastAPI dependency that yields a tenant-scoped async database session.

#     Guarantees a clean transaction state before setting the search_path.
#     This prevents the asyncpg InFailedSQLTransactionError that occurs when
#     a pooled connection is reused after a prior request's transaction was
#     aborted without a full rollback.
#     """
#     if _AsyncSessionLocal is None:
#         raise RuntimeError(
#             "Database engine not initialised. "
#             "Ensure initialise_db() was called in the application lifespan."
#         )

#     tenant = getattr(request.state, "tenant", None)
#     schema: str = tenant.schema_name if tenant else "public"

#     async with _AsyncSessionLocal() as session:
#         # Roll back any aborted transaction left on this pooled connection
#         # before attempting to set the search_path. asyncpg marks a connection
#         # as "in failed transaction" if any previous statement raised an error
#         # without a full ROLLBACK — this guarantees a clean slate.
#         try:
#             await session.execute(text("ROLLBACK"))
#         except Exception:
#             pass  # Safe to ignore — connection may already be clean

#         try:
#             await session.execute(
#                 text(f'SET search_path TO "{schema}", public')
#             )
#         except Exception as exc:
#             logger.error(
#                 "database.search_path.failed",
#                 schema=schema,
#                 error=str(exc),
#             )
#             raise

#         logger.debug("database.session.opened", schema=schema)
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             logger.debug("database.session.closed", schema=schema)


# @asynccontextmanager
# async def get_tenant_db_context(schema_name: str) -> AsyncGenerator[AsyncSession, None]:
#     """
#     Async context manager that yields a tenant-scoped session for use in
#     background tasks where no HTTP Request object is available.

#     Uses the engine's raw connection to execute SET search_path OUTSIDE of
#     any implicit transaction so it takes effect as a true session-level
#     setting before any DML runs.

#     Usage:
#         async with get_tenant_db_context("tenant_demo") as db:
#             await db.execute(text("SELECT 1"))
#     """
#     if _AsyncSessionLocal is None:
#         raise RuntimeError("Database not initialised.")

#     async with _AsyncSessionLocal() as session:
#         # Execute SET search_path via the underlying raw asyncpg connection,
#         # outside SQLAlchemy's transaction wrapper, so it persists as a
#         # session-level setting for the lifetime of this connection.
#         async with session.bind.connect() as raw_conn:  # type: ignore[union-attr]
#             await raw_conn.execute(text(f'SET search_path TO "{schema_name}", public'))
#             await raw_conn.commit()

#         # Now set it again on the session itself for SQLAlchemy's awareness
#         await session.execute(text(f'SET search_path TO "{schema_name}", public'))

#         logger.debug("database.background_session.opened", schema=schema_name)
#         try:
#             yield session
#         except Exception:
#             await session.rollback()
#             raise
#         finally:
#             logger.debug("database.background_session.closed", schema=schema_name)


from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING
from contextlib import asynccontextmanager
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

if TYPE_CHECKING:
    from starlette.requests import Request

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy 2.0 ORM models.
    No legacy Column() usage permitted — Mapped[T] + mapped_column() only.
    """


_engine: AsyncEngine | None = None
_AsyncSessionLocal: async_sessionmaker[AsyncSession] | None = None
_AsyncPublicSessionLocal: async_sessionmaker[AsyncSession] | None = None


def build_engine() -> AsyncEngine:
    """
    Creates the async SQLAlchemy engine from settings.
    Must be called once during application startup (lifespan).
    """
    settings = get_settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.is_development,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    return engine


def build_tenant_engine(schema_name: str) -> AsyncEngine:
    """
    Creates a short-lived async engine scoped to a specific tenant schema.

    The search_path is set at the asyncpg connection level via server_settings,
    so it persists across ALL db.commit() calls without any manual re-assertion.
    This eliminates the 'relation does not exist' errors that occur when
    asyncpg resets search_path to the server default after every commit.

    Used exclusively by background tasks (approve_mapping pipeline) where
    no HTTP Request object is available to drive the TenantMiddleware.
    Call dispose() on the returned engine when the task completes.
    """
    settings = get_settings()
    return create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=2,
        max_overflow=2,
        pool_pre_ping=True,
        connect_args={
            "server_settings": {
                "search_path": f'"{schema_name}",public',
            }
        },
    )


def initialise_db() -> None:
    """
    Initialises the module-level engine and session factories.
    Called once from the FastAPI lifespan context manager.
    """
    global _engine, _AsyncSessionLocal, _AsyncPublicSessionLocal

    _engine = build_engine()

    _AsyncSessionLocal = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    _AsyncPublicSessionLocal = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )

    logger.info("database.initialised", pool_size=10, max_overflow=20)


async def dispose_db() -> None:
    """
    Disposes the engine and closes all pooled connections.
    Called from the FastAPI lifespan context manager on shutdown.
    """
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("database.disposed")


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError(
            "Database engine not initialised. "
            "Ensure initialise_db() was called in the application lifespan."
        )
    return _engine


class AsyncPublicSession:
    """
    Async context manager that yields a session scoped to the public schema.
    Used by TenantMiddleware only.
    """

    async def __aenter__(self) -> AsyncSession:
        if _AsyncPublicSessionLocal is None:
            raise RuntimeError("Database not initialised.")
        self._session = _AsyncPublicSessionLocal()
        try:
            await self._session.execute(text("ROLLBACK"))
        except Exception:
            pass
        await self._session.execute(text("SET search_path TO public"))
        return self._session

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()


class _TenantScopedSession(AsyncSession):
    """
    AsyncSession subclass that re-asserts search_path after every commit.

    asyncpg resets SET search_path to the server default (public) after each
    transaction commit when the connection is returned to or reused from the
    pool without a baked-in server_settings search_path. This subclass
    overrides commit() to immediately re-assert the correct search_path
    so that any query following a commit() in an endpoint body resolves
    tenant-schema tables correctly.
    """

    _tenant_schema: str = "public"

    async def commit(self) -> None:
        await super().commit()
        # Re-assert immediately after the commit so the next statement
        # on this connection sees the correct search_path.
        await super().execute(
            text(f'SET search_path TO "{self._tenant_schema}", public')
        )


async def get_db(request: "Request") -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a tenant-scoped async database session.

    Uses _TenantScopedSession which re-asserts search_path after every
    commit(), preventing the asyncpg post-commit reset from silently
    switching the session back to the public schema.
    """
    if _AsyncSessionLocal is None:
        raise RuntimeError(
            "Database engine not initialised. "
            "Ensure initialise_db() was called in the application lifespan."
        )

    tenant = getattr(request.state, "tenant", None)
    schema: str = tenant.schema_name if tenant else "public"

    # Build a session using our schema-aware subclass
    session = _TenantScopedSession(bind=_engine, expire_on_commit=False, autoflush=False)
    session._tenant_schema = schema

    try:
        # Clear any aborted transaction left on this pooled connection.
        try:
            await session.execute(text("ROLLBACK"))
        except Exception:
            pass

        # Assert search_path for this request.
        try:
            await session.execute(
                text(f'SET search_path TO "{schema}", public')
            )
        except Exception as exc:
            logger.error("database.search_path.failed", schema=schema, error=str(exc))
            raise

        logger.debug("database.session.opened", schema=schema)
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
        logger.debug("database.session.closed", schema=schema)