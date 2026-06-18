"""
TenantProvisioningService — Phase 7A (V9 S5.2 — Carrier Decoupling)

Phase 7A Change: Carrier assignment is decoupled from tenant provisioning.
  - provision_tenant() no longer requires carrier_ids.
  - A new add_carrier_to_tenant() method encapsulates all carrier seeding logic.
  - add_carrier_to_tenant() is idempotent: re-adding a soft-deleted carrier
    re-activates the link without re-seeding calc rules.
  - The original seeding loop is removed from _seed_tenant_schema().

Provisioning sequence (unchanged except step 4):
  1. Insert a PROVISIONING tenant record in public.tenants.
  2. Create the PostgreSQL schema via an autocommit connection.
  3. Run Alembic migrations via subprocess.
  4. Seed the new schema (tenant_calc_config only — no carrier rows).
  5. Create the TENANT_ADMIN user in Keycloak.
  6. Mark the tenant ACTIVE.

On any failure after schema creation: DROP SCHEMA CASCADE and soft-delete the
public.tenants record before re-raising to the caller.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from typing import Any

import asyncpg
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.keycloak_admin_service import KeycloakAdminService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default calculation rules seeded per carrier — V9 S18.3
# 22 rules matching the system defaults set in Phase 1 alembic seed.
# ---------------------------------------------------------------------------
_DEFAULT_CALC_RULES: list[dict[str, Any]] = [
    {"rule_key": "variance_amount",       "rule_label": "Premium Variance Amount",          "rule_description": "Actual premium minus estimated premium.",                                        "expression": "actual_premium - est_premium_end",                                   "is_editable": False},
    {"rule_key": "reported_over_under",   "rule_label": "Reported Over / Under",            "rule_description": "Actual reported payroll minus estimated payroll.",                              "expression": "actual_payroll_reported - est_payroll",                               "is_editable": False},
    {"rule_key": "classified_over_under", "rule_label": "Classified Over / Under",          "rule_description": "Actual classified payroll minus estimated payroll.",                           "expression": "actual_payroll_classified - est_payroll",                             "is_editable": False},
    {"rule_key": "variance_pct",          "rule_label": "Premium Variance %",               "rule_description": "Variance as a % of estimated premium. None when est = 0.",                   "expression": "variance_amount / est_premium_end if est_premium_end != 0 else None", "is_editable": True},
    {"rule_key": "reported_pct",          "rule_label": "Actual Reported % of Estimated",   "rule_description": "Actual reported payroll as a % of estimated payroll.",                        "expression": "actual_payroll_reported / est_payroll if est_payroll != 0 else None", "is_editable": True},
    {"rule_key": "classified_pct",        "rule_label": "Actual Classified % of Estimated", "rule_description": "Actual classified payroll as a % of estimated payroll.",                      "expression": "actual_payroll_classified / est_payroll if est_payroll != 0 else None","is_editable": True},
    {"rule_key": "class_reported_pct",    "rule_label": "Class Reported % of Estimated",    "rule_description": "Class-code actual reported as a % of estimated.",                             "expression": "actual_reported / est_payroll if est_payroll != 0 else None",         "is_editable": True},
    {"rule_key": "class_classified_pct",  "rule_label": "Class Classified % of Estimated",  "rule_description": "Class-code actual classified as a % of estimated.",                           "expression": "actual_classified / est_payroll if est_payroll != 0 else None",       "is_editable": True},
    {"rule_key": "completion_ratio",      "rule_label": "Policy Completion Ratio",          "rule_description": "Days elapsed as a proportion of total policy term.",                          "expression": "days_elapsed / policy_days",                                          "is_editable": True},
    {"rule_key": "expected_submissions",  "rule_label": "Expected Submissions",             "rule_description": "Expected number of payroll submissions for the policy term.",                  "expression": "policy_days / cycle_days",                                            "is_editable": True},
    {"rule_key": "submission_rate",       "rule_label": "Submission Rate %",                "rule_description": "Actual submissions as a % of expected.",                                      "expression": "submitted_count / expected_submissions * 100",                        "is_editable": True},
    {"rule_key": "risk_threshold_high",   "rule_label": "High Risk Rule",                   "rule_description": "High risk when variance > 30% AND missing payrolls exist.",                   "expression": "abs(variance_pct) > 30 and missing_payrolls > 0",                     "is_editable": True},
    {"rule_key": "risk_threshold_medium", "rule_label": "Medium Risk Rule",                 "rule_description": "Medium risk when variance > 30% OR missing payrolls exist.",                  "expression": "abs(variance_pct) > 30 or missing_payrolls > 0",                      "is_editable": True},
    {"rule_key": "risk_threshold_target", "rule_label": "Target Variance Threshold",        "rule_description": "Variance % threshold shown on the dashboard target widget.",                  "expression": "30",                                                                  "is_editable": True},
    {"rule_key": "officer_max_payroll",   "rule_label": "Officer Max Inclusion Payroll",    "rule_description": "Maximum officer payroll included in WC premium calculation.",                  "expression": "52000",                                                               "is_editable": True},
    {"rule_key": "officer_min_payroll",   "rule_label": "Officer Min Inclusion Payroll",    "rule_description": "Minimum officer payroll included in WC premium calculation.",                  "expression": "15600",                                                               "is_editable": True},
    {"rule_key": "zero_payroll_flag",     "rule_label": "Zero Payroll Detection",           "rule_description": "Flags a payroll submission where reported wages equal zero.",                  "expression": "wages == 0.0",                                                        "is_editable": True},
    {"rule_key": "missing_payroll_flag",  "rule_label": "Missing Payroll Detection",        "rule_description": "Flags a gap greater than 1.5x the expected submission cycle.",               "expression": "days_since_last_run > cycle_days * 1.5",                              "is_editable": True},
    {"rule_key": "freq_cycle_weekly",     "rule_label": "Weekly Cycle Days",                "rule_description": "Number of days in a weekly payroll cycle.",                                    "expression": "7",                                                                   "is_editable": True},
    {"rule_key": "freq_cycle_biweekly",   "rule_label": "Bi-Weekly Cycle Days",             "rule_description": "Number of days in a bi-weekly payroll cycle.",                                "expression": "14",                                                                  "is_editable": True},
    {"rule_key": "freq_cycle_semimonthly","rule_label": "Semi-Monthly Cycle Days",          "rule_description": "Number of days in a semi-monthly payroll cycle.",                             "expression": "15",                                                                  "is_editable": True},
    {"rule_key": "freq_cycle_monthly",    "rule_label": "Monthly Cycle Days",               "rule_description": "Number of days in a monthly payroll cycle.",                                   "expression": "30",                                                                  "is_editable": True},
]


class TenantProvisioningService:
    """
    Orchestrates end-to-end tenant provisioning.

    Phase 7A: Carrier assignment is removed from the provisioning flow.
    Carriers are added post-provisioning by TENANT_ADMIN via add_carrier_to_tenant().
    """

    def __init__(self, keycloak_service: KeycloakAdminService) -> None:
        self._keycloak = keycloak_service
        self._settings = get_settings()

    async def provision_tenant(
        self,
        *,
        tenant_name: str,
        tenant_slug: str,
        tenant_type: str,
        carrier_ids: list[int],  # Accepted for backward-compat but no longer required
        admin_email: str,
        admin_first_name: str,
        admin_last_name: str,
        temporary_password: str | None,
        send_invitation: bool,
        db: AsyncSession,
    ) -> str:
        """
        Provisions a complete tenant without requiring carrier assignment.

        carrier_ids is accepted for backward-compatibility; if provided, each
        carrier is seeded via add_carrier_to_tenant() after schema creation.

        Returns: the new tenant's slug.
        Raises HTTPException on any unrecoverable failure after rollback.
        """
        schema_name = f"tenant_{tenant_slug}"

        # Step 1 — Insert provisioning record
        await db.execute(
            text(
                "INSERT INTO public.tenants "
                "(slug, schema_name, name, tenant_type, status) "
                "VALUES (:slug, :schema, :name, :type, 'PROVISIONING')"
            ),
            {
                "slug": tenant_slug,
                "schema": schema_name,
                "name": tenant_name,
                "type": tenant_type,
            },
        )
        await db.commit()
        logger.info("provisioning.tenant_record_created", extra={"slug": tenant_slug})

        try:
            # Step 2 — Create schema (autocommit — DDL cannot run in a transaction)
            await self._create_schema(schema_name)
            logger.info("provisioning.schema_created", extra={"schema": schema_name})

            # Step 3 — Run Alembic migrations via subprocess
            await self._run_alembic_migration(schema_name)
            logger.info("provisioning.migrations_applied", extra={"schema": schema_name})

            # Step 4 — Seed the new schema (no carriers required)
            await self._seed_tenant_schema(schema_name, db)
            logger.info("provisioning.schema_seeded", extra={"schema": schema_name})

            # Step 4b — Optionally seed any carriers provided at provisioning time
            # This preserves backward-compat for existing tests and any callers
            # that still pass carrier_ids (e.g. migration scripts).
            for carrier_id in carrier_ids:
                await self.add_carrier_to_tenant(
                    schema_name=schema_name,
                    carrier_id=carrier_id,
                    db=db,
                )
            if carrier_ids:
                logger.info(
                    "provisioning.carriers_seeded",
                    extra={"schema": schema_name, "count": len(carrier_ids)},
                )

            # Step 5 — Create TENANT_ADMIN user in Keycloak
            keycloak_id = await self._keycloak.create_tenant_admin_user(
                email=admin_email,
                first_name=admin_first_name,
                last_name=admin_last_name,
                tenant_slug=tenant_slug,
                temporary_password=temporary_password,
                send_invitation=send_invitation,
            )
            logger.info(
                "provisioning.keycloak_user_created",
                extra={"slug": tenant_slug, "keycloak_id": keycloak_id},
            )

            # Step 6 — Mark ACTIVE and write keycloak_id
            await db.execute(
                text("UPDATE public.tenants SET status = 'ACTIVE' WHERE slug = :slug"),
                {"slug": tenant_slug},
            )
            await db.execute(text(f"SET search_path TO {schema_name}, public"))
            await db.execute(
                text(
                    "INSERT INTO users (keycloak_id, email, first_name, last_name, role, onboarding_completed) "
                    "VALUES (:kid, :email, :first, :last, 'TENANT_ADMIN', FALSE)"
                ),
                {
                    "kid": keycloak_id,
                    "email": admin_email,
                    "first": admin_first_name,
                    "last": admin_last_name,
                },
            )
            await db.execute(text("SET search_path TO public"))
            await db.commit()
            logger.info("provisioning.completed", extra={"slug": tenant_slug})

        except Exception as exc:
            logger.error(
                "provisioning.failed_rolling_back",
                extra={"slug": tenant_slug, "error": str(exc)},
            )
            await self._drop_schema(schema_name)
            await db.rollback()
            await db.execute(
                text(
                    "UPDATE public.tenants SET status = 'DELETED', deleted_at = now() "
                    "WHERE slug = :slug"
                ),
                {"slug": tenant_slug},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tenant provisioning failed and was rolled back: {exc}",
            ) from exc

        return tenant_slug

    # ------------------------------------------------------------------
    # Phase 7A — Carrier management (post-provisioning)
    # ------------------------------------------------------------------

    async def add_carrier_to_tenant(
        self,
        *,
        schema_name: str,
        carrier_id: int,
        db: AsyncSession,
    ) -> None:
        """
        Associates a carrier with a tenant and seeds all required carrier-level
        configuration. This is the single authoritative implementation of
        carrier seeding — called both at provisioning (if carrier_ids provided)
        and via the TENANT_ADMIN POST /api/v1/admin/carriers endpoint.

        Idempotency rules:
          - If the tenant_carriers row does not exist, it is created (is_active=TRUE).
          - If the row exists but is_active=FALSE, it is re-activated.
          - In both cases, carrier_calc_config and carrier_theme_config are
            inserted with ON CONFLICT DO NOTHING (preserving any existing config).
          - Calc rules are inserted with ON CONFLICT DO NOTHING — never re-seeded,
            never duplicated. Existing rule edits are preserved.

        All operations run within the caller's db session/transaction.
        """
        await db.execute(text(f"SET search_path TO {schema_name}, public"))

        # Upsert tenant_carriers — re-activate if previously soft-deleted
        existing = await db.execute(
            text("SELECT is_active FROM tenant_carriers WHERE carrier_id = :cid"),
            {"cid": carrier_id},
        )
        row = existing.fetchone()

        if row is None:
            await db.execute(
                text(
                    "INSERT INTO tenant_carriers (carrier_id, is_active) "
                    "VALUES (:cid, TRUE)"
                ),
                {"cid": carrier_id},
            )
            logger.info(
                "carrier_seeding.tenant_carrier_created",
                extra={"schema": schema_name, "carrier_id": carrier_id},
            )
        elif not row[0]:
            await db.execute(
                text(
                    "UPDATE tenant_carriers SET is_active = TRUE "
                    "WHERE carrier_id = :cid"
                ),
                {"cid": carrier_id},
            )
            logger.info(
                "carrier_seeding.tenant_carrier_reactivated",
                extra={"schema": schema_name, "carrier_id": carrier_id},
            )
        else:
            # Already active — idempotent no-op for the junction row
            logger.info(
                "carrier_seeding.tenant_carrier_already_active",
                extra={"schema": schema_name, "carrier_id": carrier_id},
            )

        # carrier_calc_config — ON CONFLICT DO NOTHING preserves existing config
        await db.execute(
            text(
                "INSERT INTO carrier_calc_config (carrier_id, use_calculation_engine) "
                "VALUES (:cid, TRUE) ON CONFLICT DO NOTHING"
            ),
            {"cid": carrier_id},
        )

        # 22 default calculation rules — ON CONFLICT DO NOTHING preserves edits
        for rule in _DEFAULT_CALC_RULES:
            await db.execute(
                text(
                    "INSERT INTO carrier_calc_rules "
                    "(carrier_id, rule_key, rule_label, rule_description, "
                    "expression, is_editable, rule_status) "
                    "VALUES (:cid, :rule_key, :rule_label, :rule_description, "
                    ":expression, :is_editable, 'ACTIVE') "
                    "ON CONFLICT DO NOTHING"
                ),
                {
                    "cid": carrier_id,
                    "rule_key": rule["rule_key"],
                    "rule_label": rule["rule_label"],
                    "rule_description": rule["rule_description"],
                    "expression": rule["expression"],
                    "is_editable": rule["is_editable"],
                },
            )

        # carrier_theme_config — ON CONFLICT DO NOTHING preserves existing theme
        await db.execute(
            text(
                "INSERT INTO carrier_theme_config "
                "(carrier_id, theme_source, default_theme_id, allow_user_override) "
                "VALUES (:cid, 'SYSTEM', 1, TRUE) ON CONFLICT DO NOTHING"
            ),
            {"cid": carrier_id},
        )

        # Phase 7C — carrier_llm_config placeholder row (unconfigured state)
        # Seeded so the LLM config screen shows "unconfigured" rather than 404.
        await db.execute(
            text(
                "INSERT INTO carrier_llm_config "
                "(carrier_id, is_active, created_at, updated_at, created_by) "
                "VALUES (:cid, FALSE, now(), now(), 'system') "
                "ON CONFLICT (carrier_id) DO NOTHING"
            ),
            {"cid": carrier_id},
        )

        await db.execute(text("SET search_path TO public"))
        await db.commit()
        logger.info(
            "carrier_seeding.completed",
            extra={"schema": schema_name, "carrier_id": carrier_id},
        )

    # ------------------------------------------------------------------
    # Schema DDL — must use autocommit
    # ------------------------------------------------------------------

    async def _create_schema(self, schema_name: str) -> None:
        settings = self._settings
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"')
        finally:
            await conn.close()

    async def _drop_schema(self, schema_name: str) -> None:
        settings = self._settings
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE')
            logger.info("provisioning.schema_dropped", extra={"schema": schema_name})
        except Exception as exc:
            logger.error(
                "provisioning.schema_drop_failed",
                extra={"schema": schema_name, "error": str(exc)},
            )
        finally:
            await conn.close()

    # ------------------------------------------------------------------
    # Alembic migration via subprocess
    # ------------------------------------------------------------------

    async def _run_alembic_migration(self, schema_name: str) -> None:
        settings = self._settings
        cmd = ["alembic", "upgrade", "head"]
        subprocess_env = {
            **__import__("os").environ,
            "DATABASE_URL": settings.DATABASE_URL,
            "ALEMBIC_TARGET_SCHEMA": schema_name,
        }
        logger.info(
            "provisioning.alembic.starting",
            extra={"schema": schema_name, "cmd": " ".join(cmd)},
        )

        loop = asyncio.get_event_loop()
        result: subprocess.CompletedProcess[str] = await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=subprocess_env,
                cwd="/app",
            ),
        )

        if result.returncode != 0:
            error_detail = (
                f"Alembic migration failed for schema '{schema_name}'. "
                f"Exit code: {result.returncode}. "
                f"stderr: {result.stderr[:5000]}"
            )
            logger.error(
                "provisioning.alembic.failed",
                extra={
                    "schema": schema_name,
                    "returncode": result.returncode,
                    "stderr": result.stderr[:5000],
                },
            )
            logger.error(
                "provisioning.alembic.stdout",
                extra={"schema": schema_name, "stdout": result.stdout},
            )
            raise RuntimeError(error_detail)

        logger.info(
            "provisioning.alembic.completed",
            extra={"schema": schema_name, "stdout": result.stdout[:200]},
        )

    # ------------------------------------------------------------------
    # Tenant schema seeding (Phase 7A: no carrier loop here)
    # ------------------------------------------------------------------

    async def _seed_tenant_schema(
        self,
        schema_name: str,
        db: AsyncSession,
    ) -> None:
        """
        Seeds the freshly migrated tenant schema with baseline configuration.

        Phase 7A change: carrier seeding removed. Only tenant_calc_config is
        seeded here. Carrier config is seeded on-demand via add_carrier_to_tenant().
        """
        await db.execute(text(f"SET search_path TO {schema_name}, public"))

        # tenant_calc_config — one row for the tenant
        await db.execute(
            text(
                "INSERT INTO tenant_calc_config (use_calculation_engine) "
                "VALUES (TRUE) "
                "ON CONFLICT DO NOTHING"
            )
        )

        await db.execute(text("SET search_path TO public"))
        await db.commit()
