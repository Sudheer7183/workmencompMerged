from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    """
    Platform RBAC roles in ascending privilege order.
    Use StrEnum so role comparisons work with plain strings from JWT claims.
    No raw string literals in role comparisons — always use Role.REVIEWER etc.
    """

    REVIEWER = "REVIEWER"
    AUDITOR = "AUDITOR"
    TENANT_ADMIN = "TENANT_ADMIN"
    SUPER_ADMIN = "SUPER_ADMIN"

    @property
    def privilege_level(self) -> int:
        """
        Numeric representation for >= comparisons.
        Higher = more privileged.
        """
        return {
            Role.REVIEWER: 1,
            Role.AUDITOR: 2,
            Role.TENANT_ADMIN: 3,
            Role.SUPER_ADMIN: 4,
        }[self]

    def has_at_least(self, required: Role) -> bool:
        """Returns True if this role has at least the privilege of `required`."""
        return self.privilege_level >= required.privilege_level


class TokenPayload(BaseModel):
    """
    Decoded JWT payload. Passed to every protected endpoint via Depends(get_current_user).
    tenant_slug is None for SUPER_ADMIN — they operate across all tenants.
    """

    model_config = ConfigDict(from_attributes=True)

    sub: str
    email: str
    role: Role
    tenant_slug: Optional[str] = None
