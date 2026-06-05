from __future__ import annotations

import structlog
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.database import AsyncPublicSession
from app.schemas.tenant import TenantRecord

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Paths that do not require tenant resolution.
# TenantMiddleware returns early for these — no subdomain check, no DB query.
# ---------------------------------------------------------------------------
_EXEMPT_PATH_PREFIXES: frozenset[str] = frozenset(
    {
        # Infrastructure / docs
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        # Auth endpoints
        "/auth/login",
        "/auth/callback",
        # All /platform/* endpoints — SUPER_ADMIN only, no tenant context needed.
        # A single prefix covers /platform/tenants, /platform/carriers,
        # /platform/tenant-carriers, /platform/users, and any future additions.
        "/platform",
    }
)

# ---------------------------------------------------------------------------
# Subdomains that are reserved for platform-level routing.
# A request arriving on one of these never maps to a tenant.
# ---------------------------------------------------------------------------
_RESERVED_SUBDOMAINS: frozenset[str] = frozenset(
    {
        "www",
        "api",
        "app",
        "admin",
        "platform",
        "mail",
        "auth",
        "health",
        "docs",
        "redoc",
        "cdn",
        "assets",
        "static",
    }
)


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Resolves the tenant for every non-exempt inbound request.

    Subdomain resolution order:
      1. Production: extracts subdomain from Host header (acme.example.com → "acme").
      2. Development (localhost / 127.0.0.1): reads X-Tenant-Slug header.

    On success: sets request.state.tenant (TenantRecord).
    On failure: returns JSON 400 / 404 / 403 immediately.

    The resolved tenant is consumed by:
      - get_db() in database.py — to set the PostgreSQL search_path.
      - verify_tenant() in security.py — to validate JWT tenant_slug matches.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: object) -> Response:
        # Exempt paths skip all middleware logic — return immediately
        if self._is_exempt(request.url.path):
            return await call_next(request)  # type: ignore[operator]

        # Extract subdomain (or dev header)
        subdomain = self._extract_subdomain(request)
        if subdomain is None:
            return JSONResponse(
                status_code=400,
                content={"detail": "Tenant could not be identified from the request."},
            )

        # Resolve tenant from public.tenants
        tenant = await self._resolve_tenant(subdomain)
        if tenant is None:
            return JSONResponse(
                status_code=404,
                content={"detail": f"Unknown tenant: '{subdomain}'."},
            )

        if not tenant.is_active:
            return JSONResponse(
                status_code=403,
                content={"detail": "Tenant account is not active."},
            )

        request.state.tenant = tenant
        logger.debug("tenant.resolved", slug=tenant.slug, schema=tenant.schema_name)

        return await call_next(request)  # type: ignore[operator]

    # ── Private helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _is_exempt(path: str) -> bool:
        """Returns True if the path starts with any exempt prefix."""
        return any(path.startswith(prefix) for prefix in _EXEMPT_PATH_PREFIXES)

    def _extract_subdomain(self, request: Request) -> str | None:
        """
        Extracts the tenant slug from the Host header.

        On localhost/127.0.0.1 (dev), falls back to the X-Tenant-Slug header.
        Logs a DEBUG warning when the dev fallback path is taken.
        """
        host = request.headers.get("host", "")
        # Strip port if present (e.g. localhost:8000)
        hostname = host.split(":")[0]

        # ── Dev fallback ──────────────────────────────────────────────────────
        # if hostname in ("localhost", "127.0.0.1", "backend"):
        if hostname in ("localhost", "127.0.0.1", "backend", "testserver"):
            slug = request.headers.get("X-Tenant-Slug")
            if slug:
                logger.debug(
                    "tenant.middleware.dev_fallback",
                    slug=slug,
                    message=(
                        "X-Tenant-Slug header used for tenant resolution. "
                        "This path is only valid in local development."
                    ),
                )
                return slug.lower().strip()
            # No header and no subdomain on localhost — exempt health probes return early,
            # but other routes need a tenant.  Return None to trigger 400.
            return None

        # ── Subdomain extraction ──────────────────────────────────────────────
        parts = hostname.split(".")
        if len(parts) < 3:
            # No subdomain (e.g. "example.com" or "localhost")
            return None

        subdomain = parts[0].lower().strip()

        if subdomain in _RESERVED_SUBDOMAINS:
            logger.debug("tenant.middleware.reserved_subdomain", subdomain=subdomain)
            return None

        return subdomain

    @staticmethod
    async def _resolve_tenant(slug: str) -> TenantRecord | None:
        """
        Opens a short-lived public-schema session and queries public.tenants.
        Returns TenantRecord on match; None if not found.

        This uses AsyncPublicSession — intentionally isolated from the
        per-request tenant session managed by get_db().
        """
        async with AsyncPublicSession() as session:
            result = await session.execute(
                text(
                    "SELECT slug, schema_name, name, status "
                    "FROM public.tenants "
                    "WHERE slug = :slug AND deleted_at IS NULL"
                ),
                {"slug": slug},
            )
            row = result.fetchone()

        if row is None:
            return None

        return TenantRecord(
            slug=row[0],
            schema_name=row[1],
            name=row[2],
            status=row[3],
        )
