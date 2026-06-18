"""
security.py — JWT decoding, role/tenant/carrier scope enforcement.

Phase 2: Live Keycloak RS256 JWT verification via KeycloakAdminService.
  - SKIP_JWT_VERIFICATION=true is still honoured for local dev without Keycloak.
  - JWKS is fetched from Keycloak and cached in Redis (TTL 1 hour).
  - Role claim is a SINGLE string ``role`` (V9 convention — NOT an array).
  - Tenant identifier is ``tenant_slug`` (NOT ``tenant`` as in prototype).
"""
from __future__ import annotations

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.schemas.auth import Role, TokenPayload

logger = structlog.get_logger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# JWT token decoding / validation
# ---------------------------------------------------------------------------


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> TokenPayload:
    """
    FastAPI dependency: decodes the Bearer JWT and returns a TokenPayload.

    Phase 1 (SKIP_JWT_VERIFICATION=true):
      Decodes the JWT without RS256 signature verification.
      Accepts any well-formed JWT, including unsigned dev tokens.
      If no token is present, returns a mock REVIEWER token for the demo tenant.

    Phase 2 (SKIP_JWT_VERIFICATION=false):
      Fetches JWKS from Keycloak (Redis-cached, TTL 3600s) and verifies the
      RS256 signature before trusting any claim.
      Role claim is a single string ``role`` (V9 — not an array).
      Tenant identifier is ``tenant_slug`` (V9 — not ``tenant``).
    """
    settings = get_settings()

    if settings.SKIP_JWT_VERIFICATION:
        return await _decode_dev_token(credentials)

    # Phase 2: live RS256 verification
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials are missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from app.services.keycloak_admin_service import get_keycloak_admin_service

    keycloak = get_keycloak_admin_service()
    payload = await keycloak.verify_token(credentials.credentials)

    try:
        # Prefer V9 single-string claim; fall back to Keycloak native realm_access.roles
        raw_role = payload.get("role")
        if not raw_role:
            realm_roles = payload.get("realm_access", {}).get("roles", [])
            known = {"super_admin", "tenant_admin", "auditor", "reviewer"}
            matched = [r for r in realm_roles if r.lower() in known]
            raw_role = matched[0].upper() if matched else None
        if not raw_role:
            raise KeyError("role")
        return TokenPayload(
            sub=payload["sub"],
            email=payload.get("email", ""),
            role=Role(raw_role.upper()),
            tenant_slug=payload.get("tenant_slug"),  # None for SUPER_ADMIN
        )
    except (KeyError, ValueError) as exc:
        logger.warning("security.token_payload.invalid", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token contains invalid or missing claims.",
        ) from exc


async def _decode_dev_token(
    credentials: HTTPAuthorizationCredentials | None,
) -> TokenPayload:
    """
    Phase 1 / dev-mode path: decodes without RS256 signature verification.
    Falls back to a mock REVIEWER token when no credentials are supplied.
    """
    if credentials is None:
        logger.debug("security.mock_token.used")
        return TokenPayload(
            sub="dev-sub",
            email="dev@demo.example.com",
            role=Role.REVIEWER,
            tenant_slug="demo",
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            key="",
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_aud": False,
            },
            algorithms=["HS256", "RS256"],
        )
        return TokenPayload(
            sub=payload.get("sub", "dev-sub"),
            email=payload.get("email", "dev@demo.example.com"),
            role=Role(payload.get("role", Role.REVIEWER)),
            tenant_slug=payload.get("tenant_slug"),
        )
    except (JWTError, ValueError) as exc:
        logger.warning("security.jwt_decode_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format.",
        ) from exc


# ---------------------------------------------------------------------------
# Role verification
# ---------------------------------------------------------------------------


def verify_role(required: Role, token: TokenPayload) -> None:
    """
    Raises HTTP 403 if the token's role does not meet the minimum required.
    Must be called before any await to a service — it is synchronous.
    """
    if not token.role.has_at_least(required):
        logger.warning(
            "security.role.denied",
            required=required,
            actual=token.role,
            sub=token.sub,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{token.role}' does not have permission. Required: '{required}'.",
        )


# ---------------------------------------------------------------------------
# Tenant scope verification
# ---------------------------------------------------------------------------


def verify_tenant(request: Request, token: TokenPayload) -> None:
    """
    Raises HTTP 403 if the JWT tenant_slug does not match the resolved tenant.
    SUPER_ADMIN bypasses this check — operates across all tenants.
    """
    if token.role == Role.SUPER_ADMIN:
        return

    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No tenant context resolved for this request.",
        )

    if token.tenant_slug != tenant.slug:
        logger.warning(
            "security.tenant.mismatch",
            jwt_slug=token.tenant_slug,
            resolved_slug=tenant.slug,
            sub=token.sub,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="JWT tenant does not match the request tenant.",
        )


# ---------------------------------------------------------------------------
# Carrier scope verification
# ---------------------------------------------------------------------------


async def verify_carrier_scope(
    carrier_id: int,
    token: TokenPayload,
    db: AsyncSession,
) -> None:
    """
    Raises HTTP 403 if the carrier is not linked to the current tenant.
    Queries tenant_carriers in the current session (already schema-scoped by get_db).
    SUPER_ADMIN bypasses this check.
    """
    if token.role == Role.SUPER_ADMIN:
        return

    result = await db.execute(
        text(
            "SELECT COUNT(*) FROM tenant_carriers "
            "WHERE carrier_id = :cid AND is_active = TRUE"
        ),
        {"cid": carrier_id},
    )
    count: int = result.scalar_one()

    if count == 0:
        logger.warning(
            "security.carrier_scope.denied",
            carrier_id=carrier_id,
            sub=token.sub,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Carrier {carrier_id} is not accessible for this tenant.",
        )


# ---------------------------------------------------------------------------
# Convenience dependency — require SUPER_ADMIN role
# ---------------------------------------------------------------------------


async def require_super_admin(
    request: Request,
    token: TokenPayload = Depends(get_current_user),
) -> TokenPayload:
    """
    FastAPI dependency that enforces SUPER_ADMIN role on any /platform/* endpoint.
    Returns the validated TokenPayload for use downstream.
    """
    verify_role(Role.SUPER_ADMIN, token)
    return token
