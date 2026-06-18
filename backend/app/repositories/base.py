from __future__ import annotations

"""
BaseRepository — typed foundation for all data-access objects.

Every repository:
  - Takes an AsyncSession injected at construction time.
  - Filters by carrier_id on every query (enforced by the abstract guard).
  - Never crosses tenant boundaries (search_path is set by get_db()).
  - Uses SQLAlchemy 2.0 select() — no legacy Query API.
"""

from typing import Generic, TypeVar

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelT = TypeVar("ModelT", bound=Base)  # type: ignore[type-arg]


class BaseRepository(Generic[ModelT]):
    """
    Abstract base for all tenant-scoped repositories.

    Subclasses must set `model` to the SQLAlchemy ORM class they manage
    and must include `carrier_id` in every query that touches carrier-scoped data.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _assert_carrier_accessible(self, carrier_id: int) -> None:
        """
        Verifies that the carrier is linked to the current tenant schema.
        Raises ValueError (not HTTPException — repositories are infrastructure)
        when the carrier is not found in tenant_carriers.

        API-layer security.verify_carrier_scope() runs this check first;
        repositories run it as a defence-in-depth invariant.
        """
        result = await self._db.execute(
            text(
                "SELECT COUNT(*) FROM tenant_carriers "
                "WHERE carrier_id = :cid AND is_active = TRUE"
            ),
            {"cid": carrier_id},
        )
        count: int = result.scalar_one()
        if count == 0:
            raise ValueError(f"Carrier {carrier_id} is not accessible in this tenant.")
