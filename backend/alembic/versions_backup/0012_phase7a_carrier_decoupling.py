"""phase7a_carrier_decoupling

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-12

Phase 7A — No schema changes required for carrier decoupling.
The tenant_carriers table already supports zero-carrier tenants.
The only enforcement of "minimum 1 carrier" was at the application layer.

This migration is a no-op placeholder documenting the Phase 7A boundary.
It ensures alembic version tracking is consistent across deployments.
"""
from __future__ import annotations

from alembic import op

revision = "0012"
down_revision = "0011_seed_tenant_themes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No schema changes — carrier decoupling was an application-layer concern.
    # tenant_carriers already supports zero rows per tenant.
    pass


def downgrade() -> None:
    pass
