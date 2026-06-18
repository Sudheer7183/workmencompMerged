from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TenantRecord(BaseModel):
    """
    Lightweight tenant record used by TenantMiddleware.
    Populated from public.tenants and stored in request.state.tenant.
    Not a full ORM model — only the fields needed for middleware decisions.
    """

    model_config = ConfigDict(from_attributes=True)

    slug: str
    schema_name: str
    name: str
    status: str

    @property
    def is_active(self) -> bool:
        return self.status == "ACTIVE"


class CarrierRecord(BaseModel):
    """Lightweight carrier record for dependency injection."""

    model_config = ConfigDict(from_attributes=True)

    carrier_id: int
    name: str
    slug: str
    ai_narrative_enabled: bool
