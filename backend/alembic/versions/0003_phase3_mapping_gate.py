"""Phase 3 — Mapping gate tables and ingestion_runs gate column.

Revision ID: 0003_phase3_mapping_gate
Revises: 0002_phase2_tenant_branding
Create Date: 2026-06-06

Adds Phase 3 field-mapping gate structures to each tenant schema.
These objects may already exist on databases that were initialised with
the full 0001 schema (which embeds Phase 3 tables).  Every DDL operation
is guarded by an existence check so the migration is safe to run against
both old (pre-Phase-3) and new (0001 already applied) databases.

Adds per-tenant schema:
  - ingestion_field_maps          table  (carrier→field approved mappings)
  - field_mapping_sessions        table  (one session per ingestion run)
  - field_mapping_proposals       table  (one row per source column per session)
  - ingestion_runs.mapping_status column (explicit gate-status column, nullable,
                                          only added when the column is absent —
                                          the 0001 schema uses the `status` column
                                          itself; some older schemas carried a
                                          dedicated mapping_status column instead)

NOTE: public schema is intentionally left untouched — all Phase 3 objects
live in tenant schemas only.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# ── revision identifiers ──────────────────────────────────────────────────────
revision      = "0003_phase3_mapping_gate"
down_revision = "0002_phase2_tenant_branding"
branch_labels = None
depends_on    = None


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_tenant_schemas(conn: sa.engine.Connection) -> list[str]:
    """Return all tenant_* schema names that exist in the current DB."""
    result = conn.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'tenant_%'"
        )
    )
    return [row[0] for row in result]


def _table_exists(conn: sa.engine.Connection, schema: str, table: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": schema, "table": table},
    )
    return result.scalar() > 0  # type: ignore[operator]


def _column_exists(
    conn: sa.engine.Connection, schema: str, table: str, column: str
) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = :schema "
            "  AND table_name   = :table "
            "  AND column_name  = :col"
        ),
        {"schema": schema, "table": table, "col": column},
    )
    return result.scalar() > 0  # type: ignore[operator]


# ── upgrade ───────────────────────────────────────────────────────────────────

def upgrade() -> None:
    conn = op.get_bind()
    for schema in _get_tenant_schemas(conn):
        _upgrade_tenant_schema(conn, schema)


def _upgrade_tenant_schema(conn: sa.engine.Connection, schema: str) -> None:
    # ── ingestion_field_maps ──────────────────────────────────────────────────
    # Stores approved source_field → canonical_column mappings per carrier.
    if not _table_exists(conn, schema, "ingestion_field_maps"):
        op.create_table(
            "ingestion_field_maps",
            sa.Column("map_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
            sa.Column("carrier_id", sa.BigInteger(), nullable=False),
            sa.Column("source_field", sa.Text(), nullable=False),
            sa.Column("canonical_column", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("map_id", name=f"pk_ingestion_field_maps_{schema}"),
            sa.UniqueConstraint(
                "carrier_id", "source_field",
                name=f"uq_ifm_carrier_source_{schema}",
            ),
            schema=schema,
        )

    # ── field_mapping_sessions ────────────────────────────────────────────────
    # One session per ingestion_run; tracks auto-mapping review state.
    if not _table_exists(conn, schema, "field_mapping_sessions"):
        op.create_table(
            "field_mapping_sessions",
            sa.Column("session_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
            sa.Column("ingestion_run_id", sa.BigInteger(), nullable=False),
            sa.Column("carrier_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "status",
                sa.Text(),
                sa.CheckConstraint(
                    "status IN ('PENDING_REVIEW','APPROVED','REJECTED')",
                    name=f"ck_fms_status_{schema}",
                ),
                nullable=False,
                server_default="PENDING_REVIEW",
            ),
            sa.Column(
                "created_at",
                sa.TIMESTAMP(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("reviewed_at", sa.TIMESTAMP(timezone=True), nullable=True),
            sa.Column("reviewed_by", sa.Text(), nullable=True),
            sa.Column(
                "auto_mapped_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "flagged_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "unmatched_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.PrimaryKeyConstraint("session_id", name=f"pk_field_mapping_sessions_{schema}"),
            schema=schema,
        )

    # ── field_mapping_proposals ───────────────────────────────────────────────
    # One row per source column per mapping session.
    if not _table_exists(conn, schema, "field_mapping_proposals"):
        op.create_table(
            "field_mapping_proposals",
            sa.Column("proposal_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
            sa.Column("session_id", sa.BigInteger(), nullable=False),
            sa.Column("source_field", sa.Text(), nullable=False),
            sa.Column("source_sample", sa.Text(), nullable=True),
            sa.Column(
                "inferred_type",
                sa.Text(),
                nullable=False,
                server_default="TEXT",
            ),
            sa.Column("proposed_target", sa.Text(), nullable=True),
            sa.Column(
                "confidence",
                sa.Text(),
                sa.CheckConstraint(
                    "confidence IN ('HIGH','MEDIUM','LOW','UNMATCHED')",
                    name=f"ck_fmp_confidence_{schema}",
                ),
                nullable=False,
                server_default="UNMATCHED",
            ),
            sa.Column(
                "score",
                sa.Numeric(precision=6, scale=4),
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "transform_fn",
                sa.Text(),
                nullable=False,
                server_default="none",
            ),
            sa.Column(
                "is_excluded",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
            sa.Column(
                "match_reason",
                sa.Text(),
                nullable=False,
                server_default="",
            ),
            sa.PrimaryKeyConstraint("proposal_id", name=f"pk_field_mapping_proposals_{schema}"),
            schema=schema,
        )

    # ── ingestion_runs: mapping_status gate column ────────────────────────────
    # Older schema variants carried an explicit `mapping_status` column separate
    # from `status`.  The 0001 schema encodes the gate in `status` itself, so
    # this column will already be absent on those databases — skip it.
    if (
        _table_exists(conn, schema, "ingestion_runs")
        and not _column_exists(conn, schema, "ingestion_runs", "mapping_status")
    ):
        op.add_column(
            "ingestion_runs",
            sa.Column(
                "mapping_status",
                sa.Text(),
                sa.CheckConstraint(
                    "mapping_status IN ('PENDING','APPROVED','REJECTED')",
                    name=f"ck_ingestion_runs_mapping_status_{schema}",
                ),
                nullable=True,  # nullable: existing rows get NULL (gate not applicable)
            ),
            schema=schema,
        )


# ── downgrade ─────────────────────────────────────────────────────────────────

def downgrade() -> None:
    conn = op.get_bind()
    for schema in _get_tenant_schemas(conn):
        _downgrade_tenant_schema(conn, schema)


def _downgrade_tenant_schema(conn: sa.engine.Connection, schema: str) -> None:
    if _column_exists(conn, schema, "ingestion_runs", "mapping_status"):
        op.drop_column("ingestion_runs", "mapping_status", schema=schema)

    for table in ("field_mapping_proposals", "field_mapping_sessions", "ingestion_field_maps"):
        if _table_exists(conn, schema, table):
            op.drop_table(table, schema=schema)