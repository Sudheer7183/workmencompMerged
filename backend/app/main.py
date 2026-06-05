from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import initialise_db, dispose_db
from app.core.redis import initialise_redis, dispose_redis
from app.tenancy.middleware import TenantMiddleware
from app.api.v1 import dashboard, policies, ingestion, platform, tenant_admin, carrier_config


# ---------------------------------------------------------------------------
# Structured logging setup
# ---------------------------------------------------------------------------

def configure_logging(log_level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    shared_processors: list[structlog.types.Processor] = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.ExtraAdder(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.dev.ConsoleRenderer()
            if log_level == "DEBUG"
            else structlog.processors.JSONRenderer(),
        ],
    )

    root_handler = logging.root.handlers[0] if logging.root.handlers else logging.StreamHandler()
    root_handler.setFormatter(formatter)
    if not logging.root.handlers:
        logging.root.addHandler(root_handler)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    logger = structlog.get_logger(__name__)

    configure_logging(settings.LOG_LEVEL)

    if settings.SKIP_JWT_VERIFICATION and settings.is_production:
        logger.warning(
            "security.jwt_verification_disabled",
            environment=settings.ENVIRONMENT,
            message="SKIP_JWT_VERIFICATION=true must never be used in production.",
        )

    logger.info(
        "platform.startup",
        environment=settings.ENVIRONMENT,
        skip_jwt=settings.SKIP_JWT_VERIFICATION,
        phase="2",
    )

    initialise_db()
    initialise_redis()

    logger.info("platform.ready")

    yield

    logger.info("platform.shutdown")
    await dispose_db()
    await dispose_redis()
    logger.info("platform.shutdown.complete")


# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="WC Premium Audit Platform",
        version="2.0.0",
        description=(
            "Workers Compensation Premium Audit Platform — "
            "schema-per-tenant multi-tenancy with carrier-scoped RBAC. "
            "Phase 2: live Keycloak RS256 auth, tenant provisioning, SUPER_ADMIN & TENANT_ADMIN APIs."
        ),
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS — must be registered before TenantMiddleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Tenant resolution middleware
    application.add_middleware(TenantMiddleware)

    # ── Phase 1 API routers ───────────────────────────────────────────────
    application.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
    application.include_router(policies.router, prefix="/api/v1", tags=["Policies"])
    application.include_router(ingestion.router, prefix="/api/v1", tags=["Ingestion"])

    # ── Phase 2 API routers ───────────────────────────────────────────────
    # /platform/* — SUPER_ADMIN only, TenantMiddleware-exempt
    application.include_router(platform.router)
    # /api/v1/tenant/* — TENANT_ADMIN & REVIEWER
    application.include_router(tenant_admin.router)

    # Phase 3 API routers
    application.include_router(carrier_config.router, tags=["Carrier Config"])

    # ── Health endpoint ───────────────────────────────────────────────────
    @application.get("/health", tags=["Health"], include_in_schema=False)
    async def health_check(request: Request) -> JSONResponse:
        tenant = getattr(request.state, "tenant", None)
        return JSONResponse(
            content={
                "status": "ok",
                "schema": tenant.schema_name if tenant else None,
                "phase": "3",
            }
        )

    return application


# Module-level app instance
app: FastAPI = create_app()
