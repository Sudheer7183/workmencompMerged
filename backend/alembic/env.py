# from __future__ import annotations

# """
# Alembic environment for the WC Premium Audit Platform.

# Migration strategy
# ──────────────────
# 1. Migrate the `public` schema first.
# 2. Query `public.tenants WHERE status = 'ACTIVE'` to discover all active tenant slugs.
# 3. Migrate each `tenant_{slug}` schema in turn.

# The `_s()` helper returns the schema currently being migrated so migration scripts
# can use `if _s() == 'public':` guards to distinguish public-only DDL from tenant DDL.

# Adapted from App 1's multi-schema Alembic pattern.  Re-written for async SQLAlchemy 2.0.
# """

# import asyncio
# import os
# from logging.config import fileConfig
# from typing import Any

# from alembic import context
# from sqlalchemy import engine_from_config, pool, text
# from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# # The alembic `Config` object exposes the .ini-file values.
# config = context.config

# # Log configuration from alembic.ini
# if config.config_file_name is not None:
#     fileConfig(config.config_file_name)

# # ---------------------------------------------------------------------------
# # Override sqlalchemy.url from the application Settings so the database URL
# # is never duplicated between alembic.ini and .env.
# # ---------------------------------------------------------------------------
# # pylint: disable=wrong-import-position
# import sys
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# from app.core.config import get_settings  # noqa: E402
# from app.core.database import Base  # noqa: E402

# settings = get_settings()
# config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# target_metadata = Base.metadata


# # ---------------------------------------------------------------------------
# # Helper — returns the schema being migrated in the current Alembic context.
# # ---------------------------------------------------------------------------


# def _s() -> str:
#     """Return the schema for the currently-running migration context."""
#     version_table_schema = context.get_context().version_table_schema
#     return version_table_schema or "public"


# # ---------------------------------------------------------------------------
# # Offline migrations (rare — only for generating SQL scripts)
# # ---------------------------------------------------------------------------


# def run_migrations_offline() -> None:
#     """
#     Run migrations in 'offline' mode — generates SQL without a live DB connection.
#     Only the public schema is targeted in offline mode.
#     """
#     url = config.get_main_option("sqlalchemy.url")
#     context.configure(
#         url=url,
#         target_metadata=target_metadata,
#         literal_binds=True,
#         dialect_opts={"paramstyle": "named"},
#         version_table_schema="public",
#         include_schemas=True,
#     )
#     with context.begin_transaction():
#         context.run_migrations()


# # ---------------------------------------------------------------------------
# # Online migrations (standard development and CI usage)
# # ---------------------------------------------------------------------------


# async def run_migrations_online() -> None:
#     """
#     Run migrations online against a live PostgreSQL database.

#     Execution order
#     ───────────────
#     1. Migrate public schema.
#     2. Discover all active tenant slugs from public.tenants.
#     3. Migrate each tenant_{slug} schema.

#     Each schema gets its own `alembic_version` table so versions are tracked
#     independently (public.alembic_version, tenant_demo.alembic_version, etc.).
#     """
#     engine = create_async_engine(settings.DATABASE_URL, echo=False)

#     async with engine.begin() as conn:
#         # ── Step 1: migrate public schema ────────────────────────────────────
#         await _migrate_schema(conn, "public")

#         # ── Step 2: discover active tenants ──────────────────────────────────
#         result = await conn.execute(
#             text("SELECT slug FROM public.tenants WHERE status = 'ACTIVE' AND deleted_at IS NULL")
#         )
#         tenant_slugs = [row[0] for row in result.fetchall()]

#         # ── Step 3: migrate each tenant schema ───────────────────────────────
#         for slug in tenant_slugs:
#             schema_name = f"tenant_{slug.replace('-', '_')}"
#             # Ensure the schema exists (it may have been created by
#             # TenantProvisioningService — we never create it here)
#             await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
#             await _migrate_schema(conn, schema_name)

#     await engine.dispose()


# async def _migrate_schema(conn: Any, schema_name: str) -> None:
#     """
#     Run all pending Alembic migrations for a specific schema.

#     The version table is placed within the schema being migrated so each
#     schema tracks its own migration head independently.
#     """

#     def do_migrate(sync_conn: Any) -> None:
#         context.configure(
#             connection=sync_conn,
#             target_metadata=target_metadata,
#             version_table="alembic_version",
#             version_table_schema=schema_name,
#             include_schemas=True,
#             # Filter so only tables belonging to this schema are considered.
#             include_object=_make_include_object_filter(schema_name),
#         )
#         with context.begin_transaction():
#             context.run_migrations()

#     await conn.run_sync(do_migrate)


# def _make_include_object_filter(target_schema: str):
#     """
#     Returns an include_object callback that restricts Alembic autogenerate
#     to tables/indexes in `target_schema` only.

#     Without this filter, Alembic would attempt to create all schemas' tables
#     every time it runs for any given schema — causing spurious diffs.
#     """
#     def include_object(obj: Any, name: str, type_: str, reflected: bool, compare_to: Any) -> bool:
#         if type_ == "table":
#             obj_schema = getattr(obj, "schema", None)
#             if obj_schema is None:
#                 # Un-schemed tables belong to the current search_path — treat
#                 # them as belonging to the target schema.
#                 return True
#             return obj_schema == target_schema
#         return True

#     return include_object


# # ---------------------------------------------------------------------------
# # Entry point selected by Alembic
# # ---------------------------------------------------------------------------

# if context.is_offline_mode():
#     run_migrations_offline()
# else:
#     asyncio.run(run_migrations_online())

from __future__ import annotations

"""
Alembic environment for the WC Premium Audit Platform.

Migration strategy
──────────────────
A.  Called by TenantProvisioningService (subprocess with ALEMBIC_TARGET_SCHEMA env var set):
      Migrates ONLY the specified tenant schema.
      The schema already exists (created by _create_schema); status is still
      'PROVISIONING' so the tenant-discovery query would miss it.

B.  Called without ALEMBIC_TARGET_SCHEMA (normal `alembic upgrade head` on startup):
      1. Migrates the `public` schema.
      2. Queries `public.tenants WHERE status = 'ACTIVE'` for all tenant slugs.
      3. Migrates each `tenant_{slug}` schema in turn.

Each schema gets its own `alembic_version` table so versions are tracked
independently (public.alembic_version, tenant_demo.alembic_version, …).
"""

import asyncio
import os
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base        # noqa: E402

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Helper — returns the schema tracked by the current Alembic context.
# Called from inside 0001_initial_schema.py upgrade/downgrade functions.
# ---------------------------------------------------------------------------

def _s() -> str:
    version_table_schema = context.get_context().version_table_schema
    return version_table_schema or "public"


# ---------------------------------------------------------------------------
# Offline migrations
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="public",
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migrations
# ---------------------------------------------------------------------------

async def run_migrations_online() -> None:
    """
    Run all pending migrations online.

    When ALEMBIC_TARGET_SCHEMA env var is set (TenantProvisioningService),
    migrate ONLY that schema and exit.

    Without the env var, migrate public + all ACTIVE tenant schemas.
    """
    # Read target schema from environment variable — reliable across all
    # execution contexts including asyncio subprocesses.
    single_schema: str | None = os.environ.get("ALEMBIC_TARGET_SCHEMA") or None

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        if single_schema:
            # ── Provisioning path: migrate only the specified tenant schema ──
            # The schema was already CREATEd by TenantProvisioningService._create_schema()
            # before this subprocess was launched. We just need to create the tables.
            await _migrate_schema(conn, single_schema)
        else:
            # ── Standard startup path: public first, then all active tenants ──
            await _migrate_schema(conn, "public")

            result = await conn.execute(
                text(
                    "SELECT slug FROM public.tenants "
                    "WHERE status = 'ACTIVE' AND deleted_at IS NULL"
                )
            )
            tenant_slugs = [row[0] for row in result.fetchall()]

            for slug in tenant_slugs:
                schema_name = f"tenant_{slug.replace('-', '_')}"
                await conn.execute(
                    text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
                )
                await _migrate_schema(conn, schema_name)

    await engine.dispose()


async def _migrate_schema(conn: Any, schema_name: str) -> None:
    """
    Apply all pending Alembic migrations to a single schema.

    The alembic_version table is placed inside the schema itself so each
    schema tracks its own migration head independently.
    """

    def do_migrate(sync_conn: Any) -> None:
        context.configure(
            connection=sync_conn,
            target_metadata=target_metadata,
            version_table="alembic_version",
            version_table_schema=schema_name,
            include_schemas=True,
            include_object=_make_include_object_filter(schema_name),
        )
        with context.begin_transaction():
            context.run_migrations()

    await conn.run_sync(do_migrate)


def _make_include_object_filter(target_schema: str):
    """
    Returns an include_object callback that restricts Alembic autogenerate
    to tables/indexes belonging to `target_schema` only.
    """
    def include_object(
        obj: Any, name: str, type_: str, reflected: bool, compare_to: Any
    ) -> bool:
        if type_ == "table":
            obj_schema = getattr(obj, "schema", None)
            if obj_schema is None:
                return True
            return obj_schema == target_schema
        return True

    return include_object


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
