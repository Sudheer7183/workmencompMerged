"""
API v1 — Phase 2 routers.

Phase 1 routers (unchanged):   dashboard, policies, ingestion
Phase 2 routers (new):          platform, tenant_admin
"""
from app.api.v1 import dashboard, ingestion, platform, policies, tenant_admin

__all__ = ["dashboard", "ingestion", "platform", "policies", "tenant_admin"]
