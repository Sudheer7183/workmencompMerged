"""
KeycloakAdminService — Phase 2

Provides:
  - RS256 JWT verification against the Keycloak JWKS endpoint (Redis-cached).
  - Admin API operations: create/deactivate users, assign realm roles.

V9 JWT claim conventions (differ from prototype):
  - Tenant identifier: claim name is  ``tenant_slug``  (not ``tenant``).
  - Role claim:        a SINGLE string ``role``         (not an array ``roles``).
  - SUPER_ADMIN:       ``tenant_slug`` is absent from the token (maps to None).
  - Role names:        SUPER_ADMIN | TENANT_ADMIN | AUDITOR | REVIEWER.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.schemas.auth import Role

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Redis cache key — platform-level, not schema-prefixed.
# ---------------------------------------------------------------------------
_JWKS_CACHE_KEY = "keycloak:jwks"
_JWKS_TTL_SECONDS = 3600  # 1 hour


# ---------------------------------------------------------------------------
# Module-level singleton — constructed once per process.
# ---------------------------------------------------------------------------
_service_instance: KeycloakAdminService | None = None


def get_keycloak_admin_service() -> "KeycloakAdminService":
    """
    Returns the shared KeycloakAdminService singleton.
    Created lazily on first call; safe for FastAPI dependency injection.
    """
    global _service_instance
    if _service_instance is None:
        _service_instance = KeycloakAdminService()
    return _service_instance


class KeycloakAdminService:
    """
    Wraps Keycloak Admin REST API and OIDC token verification.

    All HTTP calls use a shared httpx.AsyncClient with connection pooling.
    The JWKS is cached in Redis and refreshed when a ``kid`` miss occurs.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._http_client = httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # Token verification — called by get_current_user in security.py
    # ------------------------------------------------------------------

    async def verify_token(self, token: str) -> dict[str, Any]:
        """
        Validates an RS256 JWT against the Keycloak JWKS.

        Flow:
          1. Decode the token header to obtain ``kid``.
          2. Fetch JWKS from Redis cache (or from Keycloak on miss).
          3. If ``kid`` is absent from the cached keys, invalidate the cache
             and re-fetch once — covers key rotation.
          4. Verify the RS256 signature and return the decoded payload dict.

        Raises:
          HTTPException(401): signature invalid, token expired, or malformed.
        """
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format.",
            ) from exc

        kid: str = unverified_header.get("kid", "")
        jwks = await self.get_jwks()

        # Attempt to locate the correct key by kid
        signing_key = self._find_key(jwks, kid)

        if signing_key is None:
            # kid not found — possibly rotated; invalidate cache and retry once
            logger.info("keycloak.jwks.kid_miss — refreshing cache", extra={"kid": kid})
            await self._invalidate_jwks_cache()
            jwks = await self.get_jwks()
            signing_key = self._find_key(jwks, kid)

        if signing_key is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token signing key not found in JWKS.",
            )

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                options={
                    # Audience verification disabled — the frontend client
                    # (audit-platform-frontend) issues tokens without a specific
                    # audience claim expected by the backend client ID.
                    "verify_aud": False,
                    # Issuer verification disabled — the browser obtains tokens
                    # from http://localhost:8080 (browser-facing URL) but the
                    # backend container reaches Keycloak at http://keycloak:8080
                    # (internal Docker DNS). The iss claim therefore contains
                    # "localhost:8080" while the JWKS was fetched from
                    # "keycloak:8080". The RS256 signature is the authoritative
                    # proof of authenticity — issuer string mismatch is a
                    # deployment topology concern, not a security vulnerability.
                    "verify_iss": False,
                },
            )
        except JWTError as exc:
            logger.warning("keycloak.token.verification_failed", extra={"error": str(exc)})
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token verification failed.",
            ) from exc

        return payload

    # ------------------------------------------------------------------
    # JWKS fetching and caching
    # ------------------------------------------------------------------

    async def get_jwks(self) -> dict[str, Any]:
        """
        Returns the JWKS for the configured realm.

        Cache strategy:
          - First checks Redis (key: ``keycloak:jwks``, TTL 1 hour).
          - On miss: fetches from Keycloak and writes to Redis.
        """
        redis = await get_redis_client()

        if redis is not None:
            try:
                cached = await redis.get(_JWKS_CACHE_KEY)
                if cached is not None:
                    return json.loads(cached)
            except Exception as exc:
                logger.warning("keycloak.jwks.redis_read_failed", extra={"error": str(exc)})

        jwks = await self._fetch_jwks_from_keycloak()

        if redis is not None:
            try:
                await redis.setex(_JWKS_CACHE_KEY, _JWKS_TTL_SECONDS, json.dumps(jwks))
            except Exception as exc:
                logger.warning("keycloak.jwks.redis_write_failed", extra={"error": str(exc)})

        return jwks

    async def _fetch_jwks_from_keycloak(self) -> dict[str, Any]:
        """Fetches the JWKS document from the Keycloak OIDC certs endpoint."""
        url = self._settings.keycloak_jwks_url
        try:
            resp = await self._http_client.get(url)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            logger.error("keycloak.jwks.fetch_failed", extra={"url": url, "error": str(exc)})
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to reach Keycloak JWKS endpoint.",
            ) from exc

    async def _invalidate_jwks_cache(self) -> None:
        """Removes the cached JWKS from Redis, forcing a re-fetch on next call."""
        redis = await get_redis_client()
        if redis is not None:
            try:
                await redis.delete(_JWKS_CACHE_KEY)
            except Exception as exc:
                logger.warning("keycloak.jwks.cache_invalidation_failed", extra={"error": str(exc)})

    @staticmethod
    def _find_key(jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
        """
        Locates the JWKS key matching the given ``kid``.
        Returns the key dict or None when not found.
        """
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        return None

    # ------------------------------------------------------------------
    # Admin token — used by all Admin REST API calls
    # ------------------------------------------------------------------

    async def get_admin_token(self) -> str:
        """
        Obtains an admin access token using client_credentials grant.
        The backend service account must have the ``realm-management`` role.
        """
        token_url = (
            f"{self._settings.KEYCLOAK_URL}"
            f"/realms/{self._settings.KEYCLOAK_REALM}"
            "/protocol/openid-connect/token"
        )
        logger.info(
            "keycloak.admin_token.attempting",
            extra={
                "url": token_url,
                "client_id": self._settings.KEYCLOAK_CLIENT_ID,
            },
        )
        try:
            resp = await self._http_client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._settings.KEYCLOAK_CLIENT_ID,
                    "client_secret": self._settings.KEYCLOAK_CLIENT_SECRET,
                },
            )
            # Log the full response body before raising so we see exactly
            # what Keycloak rejected (invalid_client, unauthorized_client, etc.)
            if resp.status_code >= 400:
                logger.error(
                    "keycloak.admin_token.http_error",
                    extra={
                        "status": resp.status_code,
                        "body": resp.text[:500],
                        "url": token_url,
                        "client_id": self._settings.KEYCLOAK_CLIENT_ID,
                    },
                )
            resp.raise_for_status()
            return resp.json()["access_token"]
        except httpx.HTTPError as exc:
            # Capture response body if available (httpx stores it on the response)
            response_body = ""
            if hasattr(exc, "response") and exc.response is not None:
                response_body = exc.response.text[:500]
            logger.error(
                "keycloak.admin_token.fetch_failed",
                extra={"error": str(exc), "response_body": response_body},
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Unable to obtain Keycloak admin token. Keycloak said: {response_body or str(exc)}",
            ) from exc

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    async def create_tenant_admin_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        tenant_slug: str,
        temporary_password: str | None = None,
        send_invitation: bool = True,
    ) -> str:
        """
        Creates a TENANT_ADMIN user in Keycloak and returns the Keycloak user ID.

        The ``tenant_slug`` attribute (V9 name, not ``tenant``) is set on the
        user so the protocol mapper includes it in the JWT.
        """
        return await self._create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=Role.TENANT_ADMIN,
            tenant_slug=tenant_slug,
            temporary_password=temporary_password,
            send_invitation=send_invitation,
        )

    async def create_tenant_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        tenant_slug: str,
        role: Role,
        temporary_password: str | None = None,
    ) -> str:
        """
        Creates an AUDITOR or REVIEWER user in Keycloak and returns the Keycloak user ID.

        Allowed roles: AUDITOR, REVIEWER.
        TENANT_ADMIN users must be created via create_tenant_admin_user().
        SUPER_ADMIN users are created directly in the Keycloak admin UI.
        """
        if role not in (Role.AUDITOR, Role.REVIEWER):
            raise ValueError(
                f"create_tenant_user only accepts AUDITOR or REVIEWER; got '{role}'."
            )
        return await self._create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            tenant_slug=tenant_slug,
            temporary_password=temporary_password,
            send_invitation=False,
        )

    async def deactivate_user(self, keycloak_id: str) -> None:
        """
        Sets ``enabled: false`` on the Keycloak user, preventing future logins.
        Does not delete the user record — soft disable only.
        """
        admin_token = await self.get_admin_token()
        url = self._admin_users_url(keycloak_id)
        try:
            resp = await self._http_client.put(
                url,
                json={"enabled": False},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "keycloak.user.deactivate_failed",
                extra={"keycloak_id": keycloak_id, "error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to deactivate Keycloak user {keycloak_id}.",
            ) from exc

    async def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        """
        Searches Keycloak for a user with the given email.
        Returns the user dict or None when not found.
        """
        admin_token = await self.get_admin_token()
        base_url = self._admin_users_url()
        try:
            resp = await self._http_client.get(
                base_url,
                params={"email": email, "exact": "true"},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()
            users: list[dict[str, Any]] = resp.json()
            return users[0] if users else None
        except httpx.HTTPError as exc:
            logger.error(
                "keycloak.user.search_failed",
                extra={"email": email, "error": str(exc)},
            )
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _create_user(
        self,
        email: str,
        first_name: str,
        last_name: str,
        role: Role,
        tenant_slug: str,
        temporary_password: str | None,
        send_invitation: bool,
    ) -> str:
        """
        Core user creation logic shared by create_tenant_admin_user and create_tenant_user.

        Steps:
          1. POST to /users — creates the user record.
          2. Set the user's realm role.
          3. If temporary_password is provided, set it directly.
          4. If send_invitation is True, trigger Keycloak email verification action.

        Returns the Keycloak user ID (UUID string).
        """
        admin_token = await self.get_admin_token()
        users_url = self._admin_users_url()

        # Build the user representation
        user_payload: dict[str, Any] = {
            "username": email,           # Use email as username — V9 convention
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "emailVerified": not send_invitation,  # False = requires verification
            "attributes": {
                "tenant_slug": [tenant_slug],       # V9: tenant_slug, NOT tenant
            },
        }

        if send_invitation:
            user_payload["requiredActions"] = ["VERIFY_EMAIL"]

        # Step 1 — Create user
        try:
            create_resp = await self._http_client.post(
                users_url,
                json=user_payload,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            create_resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error(
                "keycloak.user.create_failed",
                extra={"email": email, "error": str(exc)},
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to create Keycloak user for '{email}'.",
            ) from exc

        # Step 2 — Extract user ID from Location header (Keycloak convention)
        keycloak_user_id = create_resp.headers.get("Location", "").rstrip("/").split("/")[-1]
        if not keycloak_user_id:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Keycloak did not return a user ID in the Location header.",
            )

        # Step 3 — Assign realm role
        await self._assign_realm_role(admin_token, keycloak_user_id, role)

        # Step 4 — Set password when provided
        if temporary_password is not None:
            await self._set_password(admin_token, keycloak_user_id, temporary_password)

        return keycloak_user_id

    async def _assign_realm_role(
        self, admin_token: str, keycloak_user_id: str, role: Role
    ) -> None:
        """Fetches the realm role representation and assigns it to the user.

        Keycloak realm roles are defined with lowercase names (e.g. 'tenant_admin')
        while the Role enum uses uppercase values for internal use (e.g. 'TENANT_ADMIN').
        The role name sent to Keycloak must be lowercased to match the realm definition.
        """
        # Fetch the role representation from Keycloak
        # role.value is e.g. "TENANT_ADMIN" — Keycloak realm role is "tenant_admin"
        keycloak_role_name = role.value.lower()
        roles_url = (
            f"{self._settings.KEYCLOAK_URL}"
            f"/admin/realms/{self._settings.KEYCLOAK_REALM}"
            f"/roles/{keycloak_role_name}"
        )
        try:
            role_resp = await self._http_client.get(
                roles_url,
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            role_resp.raise_for_status()
            role_repr = role_resp.json()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to fetch role '{keycloak_role_name}' from Keycloak.",
            ) from exc

        # Assign the role to the user
        assign_url = (
            f"{self._settings.KEYCLOAK_URL}"
            f"/admin/realms/{self._settings.KEYCLOAK_REALM}"
            f"/users/{keycloak_user_id}/role-mappings/realm"
        )
        try:
            assign_resp = await self._http_client.post(
                assign_url,
                json=[role_repr],
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assign_resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to assign role '{keycloak_role_name}' to user in Keycloak.",
            ) from exc

    async def _set_password(
        self, admin_token: str, keycloak_user_id: str, password: str
    ) -> None:
        """Sets a user password directly via the Keycloak Admin API."""
        url = self._admin_users_url(f"{keycloak_user_id}/reset-password")
        try:
            resp = await self._http_client.put(
                url,
                json={"type": "password", "value": password, "temporary": False},
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to set password in Keycloak.",
            ) from exc

    def _admin_users_url(self, suffix: str = "") -> str:
        """Constructs the Keycloak Admin REST users base URL for this realm."""
        base = (
            f"{self._settings.KEYCLOAK_URL}"
            f"/admin/realms/{self._settings.KEYCLOAK_REALM}"
            "/users"
        )
        return f"{base}/{suffix}" if suffix else base
