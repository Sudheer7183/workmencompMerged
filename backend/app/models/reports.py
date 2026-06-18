from __future__ import annotations

"""
ORM models for Phase 5 report generation.

Tables are defined in the initial schema migration (0001_initial_schema.py).
The run_id column is added by migration 0009_report_jobs_run_id.py.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, CHAR, Identity, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CarrierReportTemplate(Base):
    """
    Tenant schema: carrier_report_templates.

    One row per carrier. Branding applied to all generated reports for that carrier.

    Branding resolution chain (V9 S14.2):
      1. logo_url (carrier-specific logo overrides tenant_branding.logo_url)
      2. tenant_branding.logo_url (tenant fallback)
      3. Text fallback "the Audit Platform"

    primary_colour / secondary_colour: 6-char hex without leading # (e.g. "1A3C5E")
    contact_block: raw HTML rendered in PDF report footer
    """

    __tablename__ = "carrier_report_templates"

    template_id:      Mapped[int]           = mapped_column(BigInteger(), Identity(), primary_key=True)
    carrier_id:       Mapped[int]           = mapped_column(BigInteger(), nullable=False, unique=True)
    logo_url:         Mapped[Optional[str]] = mapped_column(Text(), nullable=True)
    primary_colour:   Mapped[Optional[str]] = mapped_column(CHAR(6), nullable=True)
    secondary_colour: Mapped[Optional[str]] = mapped_column(CHAR(6), nullable=True)
    contact_block:    Mapped[Optional[str]] = mapped_column(Text(), nullable=True)


class ReportJob(Base):
    """
    Tenant schema: report_jobs.

    UUID primary key. Tracks an async report generation task.

    Status lifecycle: QUEUED → PROCESSING → COMPLETE | FAILED

    S3 atomicity guarantee (V9 S21.2):
      file_url is written ONLY after S3 upload confirms.
      A failed upload leaves file_url NULL and status=FAILED.

    run_id: optional — required for exception_report and ingestion_audit_trail types.
            Added by migration 0009_report_jobs_run_id.py.
    """

    __tablename__ = "report_jobs"

    job_id:        Mapped[uuid.UUID]          = mapped_column(UUID(as_uuid=True), primary_key=True)
    carrier_id:    Mapped[int]                = mapped_column(BigInteger(), nullable=False, index=True)
    policy_id:     Mapped[Optional[int]]      = mapped_column(BigInteger(), nullable=True)
    report_type:   Mapped[str]                = mapped_column(Text(), nullable=False)
    output_format: Mapped[str]                = mapped_column(Text(), nullable=False)
    run_id:        Mapped[Optional[int]]      = mapped_column(BigInteger(), nullable=True)
    status:        Mapped[str]                = mapped_column(Text(), nullable=False, server_default="QUEUED")
    file_url:      Mapped[Optional[str]]      = mapped_column(Text(), nullable=True)
    requested_by:  Mapped[str]                = mapped_column(Text(), nullable=False)
    requested_at:  Mapped[datetime]           = mapped_column(nullable=False)
    completed_at:  Mapped[Optional[datetime]] = mapped_column(nullable=True)
    error_detail:  Mapped[Optional[str]]      = mapped_column(Text(), nullable=True)
