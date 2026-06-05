# from __future__ import annotations

# """
# IngestionService — Phase 3.

# Stage 1 — run():
#   Creates ingestion_run at status='awaiting_mapping'.
#   Calls AutoMappingService to generate field_mapping_proposals.
#   Returns (run_id, session_id). Does NOT write to fact tables.

# Stage 2 — run_post_approval():
#   Called only after TENANT_ADMIN approves the mapping gate.
#   Uses approved field_mapping_proposals to parse and upsert fact rows.
#   Advances run status: awaiting_mapping → processing → complete.
#   Triggers AuditCalculationService.
# """

# import xml.etree.ElementTree as ET
# from collections import defaultdict
# from datetime import date, datetime
# from decimal import Decimal
# from io import BytesIO
# from typing import Optional

# import openpyxl
# import structlog
# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncSession

# from app.services.audit_calculation_service import AuditCalculationService
# from app.services.auto_mapping_service import AutoMappingService
# from app.utils.text_utils import find_col, normalise

# logger = structlog.get_logger(__name__)


# # ---------------------------------------------------------------------------
# # Scalar coercers
# # ---------------------------------------------------------------------------

# def _safe_decimal(value: object) -> Optional[Decimal]:
#     if value is None:
#         return None
#     s = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
#     if s in ("", "N/A", "NA", "-", "n/a", "None"):
#         return None
#     try:
#         return Decimal(s)
#     except Exception:
#         return None


# def _safe_date(value: object) -> Optional[date]:
#     if isinstance(value, (date, datetime)):
#         return value.date() if isinstance(value, datetime) else value
#     if isinstance(value, str):
#         for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y"):
#             try:
#                 return datetime.strptime(value.strip(), fmt).date()
#             except ValueError:
#                 pass
#     return None


# def _safe_str(value: object, max_len: int | None = None) -> Optional[str]:
#     if value is None:
#         return None
#     s = str(value).strip()
#     if not s or s.lower() in ("none", "n/a", "na"):
#         return None
#     return s[:max_len] if max_len else s


# # ---------------------------------------------------------------------------
# # IngestionService
# # ---------------------------------------------------------------------------

# class IngestionService:
#     """
#     Phase 3 ingestion pipeline.

#     Routing after approval is based entirely on which CANONICAL columns
#     exist in the approved mapping proposals — not on original header names.

#     Routing priority (first match wins):
#       wages + class_code                         → payroll_variance_class
#       est_payroll + actual_payroll_reported       → payroll_variance_policy
#       est_premium_end OR actual_premium           → premium_variance
#       reason_code OR (report_date+policy_number) → zero_payroll
#       expected_period_start                       → missing_payroll
#       policy_number only                          → policies (header ingestion)
#     """

#     def __init__(self) -> None:
#         self._calc_service = AuditCalculationService()
#         self._auto_mapping = AutoMappingService()

#     # =========================================================================
#     # Stage 1 — Upload
#     # =========================================================================

#     async def run(
#         self,
#         schema_name: str,
#         carrier_id: int,
#         source_id: int,
#         file_bytes: bytes,
#         file_type: str,
#         db: AsyncSession,
#         uploaded_by: str = "system",
#         override_use_engine: Optional[bool] = None,
#     ) -> tuple[int, int]:
#         """Creates ingestion_run + generates mapping proposals. Returns (run_id, session_id)."""
#         print("file type in ingestion",file_type)
#         if file_type not in ("xlsx", "xml"):
#             raise ValueError(f"Unsupported file type: '{file_type}'. Accepted: xlsx, xml")

#         run_id = await self._create_ingestion_run(
#             carrier_id, source_id, uploaded_by, override_use_engine, db,
#             schema_name=schema_name,
#         )
#         try:
#             session_id = await self._auto_mapping.run(
#                 run_id=run_id,
#                 carrier_id=carrier_id,
#                 file_bytes=file_bytes,
#                 db=db,
#                 file_type=file_type,
#                 schema_name=schema_name,
#             )
#         except Exception as exc:
#             logger.error("ingestion.auto_mapping.failed", run_id=run_id, error=str(exc))
#             try:
#                 await db.rollback()
#             except Exception:
#                 pass
#             try:
#                 await db.execute(
#                     text("UPDATE ingestion_runs SET status='failed', error_detail=:err WHERE run_id=:rid"),
#                     {"err": str(exc)[:2000], "rid": run_id},
#                 )
#                 await db.commit()
#             except Exception:
#                 await db.rollback()
#             raise

#         logger.info("ingestion.awaiting_mapping", run_id=run_id, session_id=session_id)
#         return run_id, session_id

#     # =========================================================================
#     # Stage 2 — Post-approval
#     # =========================================================================

#     async def run_post_approval(
#         self,
#         schema_name: str,
#         carrier_id: int,
#         run_id: int,
#         session_id: int,
#         db: AsyncSession,
#     ) -> int:
#         """Parses and upserts fact rows using approved mapping proposals."""
#         proposals = await self._load_approved_proposals(session_id, db)
#         if not proposals:
#             raise ValueError(f"No approved proposals found for session {session_id}")

#         file_bytes = await self._load_file_bytes(run_id, db)

#         try:
#             # await self._advance_status(run_id, "processing", db)
#             await self._advance_status(run_id, "processing", db, schema_name=schema_name)

#             if file_bytes and (file_bytes[:5] in (b"<?xml", b"<PPlu") or b"<PPlus" in file_bytes[:100]):
#                 rows_ingested = await self._parse_and_upsert_xml(
#                     carrier_id=carrier_id, run_id=run_id,
#                     file_bytes=file_bytes, db=db,
#                 )
#             elif file_bytes:
#                 rows_ingested = await self._parse_and_upsert_xlsx(
#                     carrier_id=carrier_id, run_id=run_id,
#                     file_bytes=file_bytes, proposals=proposals, db=db,
#                 )
#             else:
#                 logger.warning("ingestion.post_approval.no_file_bytes", run_id=run_id)
#                 rows_ingested = 0

#             # await self._complete_run(run_id, rows_ingested, db)
#             await self._complete_run(run_id, rows_ingested, db, schema_name=schema_name)

#         except Exception as exc:
#             logger.error("ingestion.post_approval.failed", run_id=run_id, error=str(exc))
#             try:
#                 await db.rollback()
#             except Exception:
#                 pass
#             try:
#                 await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#                 await db.commit()
#                 await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#                 await db.execute(
#                     text("UPDATE ingestion_runs SET status='failed', error_detail=:err WHERE run_id=:rid"),
#                     {"err": str(exc)[:2000], "rid": run_id},
#                 )
#                 await db.commit()
#             except Exception:
#                 await db.rollback()
#             raise

#         await self._trigger_calc_for_run(schema_name, carrier_id, run_id, db)
#         return rows_ingested

#     # =========================================================================
#     # Run lifecycle helpers
#     # =========================================================================

#     # async def _create_ingestion_run(
#     #     self,
#     #     carrier_id: int,
#     #     source_id: int,
#     #     uploaded_by: str,
#     #     override_use_engine: Optional[bool],
#     #     db: AsyncSession,
#     # ) -> int:
#     #     result = await db.execute(
#     #         text("""
#     #             INSERT INTO ingestion_runs
#     #               (carrier_id, source_id, uploaded_by, started_at, status,
#     #                rows_skipped, rows_failed, skip_on_error, use_calculation_engine)
#     #             VALUES (:cid, :sid, :by, now(), 'awaiting_mapping', 0, 0, FALSE, :engine)
#     #             RETURNING run_id
#     #         """),
#     #         {"cid": carrier_id, "sid": source_id, "by": uploaded_by, "engine": override_use_engine},
#     #     )
#     #     await db.commit()
#     #     run_id: int = result.scalar_one()
#     #     logger.info("ingestion.run.created", run_id=run_id, carrier_id=carrier_id)
#     #     return run_id
#     async def _create_ingestion_run(
#         self,
#         carrier_id: int,
#         source_id: int,
#         uploaded_by: str,
#         override_use_engine: Optional[bool],
#         db: AsyncSession,
#         schema_name: str = "public",
#     ) -> int:
#         result = await db.execute(
#             text("""
#                 INSERT INTO ingestion_runs
#                   (carrier_id, source_id, uploaded_by, started_at, status,
#                    rows_skipped, rows_failed, skip_on_error, use_calculation_engine)
#                 VALUES (:cid, :sid, :by, now(), 'awaiting_mapping', 0, 0, FALSE, :engine)
#                 RETURNING run_id
#             """),
#             {"cid": carrier_id, "sid": source_id, "by": uploaded_by, "engine": override_use_engine},
#         )
#         await db.commit()
#         # Re-assert search_path — asyncpg resets it to the server default after
#         # every db.commit(). All subsequent queries in this session (auto_mapping,
#         # _persist_session_and_proposals) must run against the tenant schema.
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.commit()
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         run_id: int = result.scalar_one()
#         logger.info("ingestion.run.created", run_id=run_id, carrier_id=carrier_id)
#         return run_id

#     async def _advance_status(
#         self, run_id: int, status: str, db: AsyncSession, schema_name: str = "public"
#     ) -> None:
#         # Re-assert search_path before the UPDATE — prior commits reset it
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.commit()
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.execute(
#             text("UPDATE ingestion_runs SET status=:s WHERE run_id=:rid"),
#             {"s": status, "rid": run_id},
#         )
#         await db.commit()

#     async def _complete_run(
#         self, run_id: int, rows: int, db: AsyncSession, schema_name: str = "public"
#     ) -> None:
#         # Re-assert search_path before the UPDATE — previous upsert commits reset it
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.commit()
#         await db.execute(text(f'SET search_path TO "{schema_name}", public'))
#         await db.execute(
#             text("UPDATE ingestion_runs SET status='complete', rows_ingested=:rows, completed_at=now() WHERE run_id=:rid"),
#             {"rows": rows, "rid": run_id},
#         )
#         await db.commit()

#     async def _load_approved_proposals(self, session_id: int, db: AsyncSession) -> list[dict]:
#         result = await db.execute(
#             text("""
#                 SELECT source_field, proposed_target, transform_fn
#                 FROM field_mapping_proposals
#                 WHERE session_id=:sid AND is_excluded=FALSE AND proposed_target IS NOT NULL
#             """),
#             {"sid": session_id},
#         )
#         return [
#             {"source_field": r[0], "proposed_target": r[1], "transform_fn": r[2]}
#             for r in result.fetchall()
#         ]

#     async def _load_file_bytes(self, run_id: int, db: AsyncSession) -> Optional[bytes]:
#         try:
#             result = await db.execute(
#                 text("SELECT raw_file_bytes FROM ingestion_runs WHERE run_id=:rid"),
#                 {"rid": run_id},
#             )
#             row = result.fetchone()
#             if row and row[0]:
#                 return bytes(row[0])
#         except Exception as exc:
#             logger.warning("ingestion.file_bytes.load_failed", run_id=run_id, error=str(exc))
#         return None

#     # =========================================================================
#     # XLSX parsing
#     # =========================================================================

#     async def _parse_and_upsert_xlsx(
#         self,
#         carrier_id: int,
#         run_id: int,
#         file_bytes: bytes,
#         proposals: list[dict],
#         db: AsyncSession,
#     ) -> int:
#         # Build source_field → canonical_name lookup from approved proposals
#         mapping_lookup: dict[str, str] = {
#             p["source_field"]: p["proposed_target"]
#             for p in proposals
#             if p["proposed_target"]
#         }

#         wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
#         total = 0
#         for sheet_name in wb.sheetnames:
#             ws = wb[sheet_name]
#             count = await self._process_sheet(
#                 ws=ws, carrier_id=carrier_id, run_id=run_id,
#                 mapping_lookup=mapping_lookup, db=db,
#             )
#             total += count
#             logger.debug("ingestion.sheet.processed", sheet=sheet_name, rows=count)
#         wb.close()
#         return total

#     async def _process_sheet(
#         self,
#         ws: openpyxl.worksheet.worksheet.Worksheet,
#         carrier_id: int,
#         run_id: int,
#         mapping_lookup: dict[str, str],
#         db: AsyncSession,
#     ) -> int:
#         # Find header row — skip report metadata rows
#         header_row_idx: Optional[int] = None
#         header_vals: list[str] = []

#         for row_idx in range(1, min(20, ws.max_row + 1)):
#             row_vals = [
#                 str(cell.value).strip() if cell.value is not None else ""
#                 for cell in ws[row_idx]
#             ]
#             non_empty = [v for v in row_vals if v]
#             if len(non_empty) < 3:
#                 continue
#             joined = " ".join(non_empty).upper()
#             if any(kw in joined for kw in (
#                 "AUDIT REPORT", "DATE REPORT RUN", "POLICY PERIOD",
#                 "BREAKDOWN OF PREMIUM", "CLASSIFICATION DETAIL", "KEY INDIVIDUALS",
#                 "SUMMARY", "TOTAL PREMIUM",
#             )):
#                 continue
#             if sum(len(v) for v in non_empty) / len(non_empty) > 45:
#                 continue
#             header_row_idx = row_idx
#             header_vals = row_vals
#             break

#         if not header_vals or header_row_idx is None:
#             return 0

#         # Build canonical_col_map: {canonical_name: 1-based_col_index}
#         canonical_col_map: dict[str, int] = {}
#         for col_idx, header in enumerate(header_vals, start=1):
#             if header and header in mapping_lookup:
#                 canonical_col_map[mapping_lookup[header]] = col_idx

#         if not canonical_col_map:
#             logger.warning("ingestion.sheet.no_mapped_columns", sheet=ws.title)
#             return 0

#         logger.info("ingestion.sheet.routing", sheet=ws.title, canonical_cols=list(canonical_col_map.keys()))

#         # Route by canonical columns present
#         if "wages" in canonical_col_map and "class_code" in canonical_col_map:
#             return await self._upsert_payroll_class(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

#         if "est_payroll" in canonical_col_map or "actual_payroll_reported" in canonical_col_map:
#             return await self._upsert_payroll_policy(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

#         if "est_premium_end" in canonical_col_map or "actual_premium" in canonical_col_map:
#             return await self._upsert_premium_variance(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

#         if "reason_code" in canonical_col_map or "report_date" in canonical_col_map:
#             return await self._upsert_zero_payroll(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

#         if "expected_period_start" in canonical_col_map or "days_overdue" in canonical_col_map:
#             return await self._upsert_missing_payroll(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

#         if "policy_number" in canonical_col_map:
#             return await self._upsert_policies_only(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

#         logger.warning("ingestion.sheet.unroutable", sheet=ws.title, cols=list(canonical_col_map.keys()))
#         return 0

#     # =========================================================================
#     # Core helper: get cell value by canonical name
#     # =========================================================================

#     def _cv(self, row: tuple, cmap: dict[str, int], *names: str) -> object:
#         """Returns first non-None value for given canonical column names."""
#         for name in names:
#             idx = cmap.get(name)
#             if idx is not None and idx - 1 < len(row):
#                 v = row[idx - 1]
#                 if v is not None:
#                     return v
#         return None

#     # =========================================================================
#     # Policy + policyholder upsert (shared by all XLSX upsert methods)
#     # =========================================================================

#     async def _ensure_policy(
#         self,
#         row: tuple,
#         cmap: dict[str, int],
#         carrier_id: int,
#         db: AsyncSession,
#     ) -> Optional[int]:
#         """
#         Upserts policyholder + policy from approved canonical columns.
#         Returns policy_id or None if policy_number is missing.
#         """
#         pol_num = _safe_str(self._cv(row, cmap, "policy_number"))
#         if not pol_num:
#             return None

#         insured = _safe_str(self._cv(row, cmap, "insured_name")) or "Unknown"
#         fein    = _safe_str(self._cv(row, cmap, "fein"))
#         state   = _safe_str(self._cv(row, cmap, "state_code"), max_len=2)
#         eff     = _safe_date(self._cv(row, cmap, "effective_date", "as_of_date"))
#         exp     = _safe_date(self._cv(row, cmap, "expiration_date"))

#         # Upsert policyholder
#         if fein:
#             ph = await db.execute(
#                 text("""
#                     INSERT INTO policyholders (carrier_id, name, fein)
#                     VALUES (:cid, :name, :fein)
#                     ON CONFLICT (carrier_id, fein) DO UPDATE SET name = EXCLUDED.name
#                     RETURNING policyholder_id
#                 """),
#                 {"cid": carrier_id, "name": insured, "fein": fein},
#             )
#         else:
#             # No FEIN — try to find by name, insert if missing
#             ph = await db.execute(
#                 text("SELECT policyholder_id FROM policyholders WHERE carrier_id=:cid AND name=:name AND fein IS NULL LIMIT 1"),
#                 {"cid": carrier_id, "name": insured},
#             )
#             row_ph = ph.fetchone()
#             if row_ph is None:
#                 ph = await db.execute(
#                     text("INSERT INTO policyholders (carrier_id, name, fein) VALUES (:cid, :name, NULL) RETURNING policyholder_id"),
#                     {"cid": carrier_id, "name": insured},
#                 )
#             else:
#                 # Return a fake result object with the found id
#                 ph_id = row_ph[0]
#                 pol = await db.execute(
#                     text("""
#                         INSERT INTO policies
#                           (carrier_id, policyholder_id, policy_number, state_code,
#                            effective_date, expiration_date, policy_status, audit_status)
#                         VALUES (:cid, :phid, :pnum, :state, :eff, :exp, 'Active', 'Pending')
#                         ON CONFLICT (carrier_id, policy_number) DO UPDATE SET
#                           policyholder_id = EXCLUDED.policyholder_id,
#                           state_code      = COALESCE(EXCLUDED.state_code, policies.state_code),
#                           effective_date  = COALESCE(EXCLUDED.effective_date, policies.effective_date),
#                           expiration_date = COALESCE(EXCLUDED.expiration_date, policies.expiration_date)
#                         RETURNING policy_id
#                     """),
#                     {"cid": carrier_id, "phid": ph_id, "pnum": pol_num,
#                      "state": state, "eff": eff, "exp": exp},
#                 )
#                 r = pol.fetchone()
#                 return r[0] if r else None

#         ph_row = ph.fetchone()
#         if ph_row is None:
#             return None
#         ph_id = ph_row[0]

#         pol = await db.execute(
#             text("""
#                 INSERT INTO policies
#                   (carrier_id, policyholder_id, policy_number, state_code,
#                    effective_date, expiration_date, policy_status, audit_status)
#                 VALUES (:cid, :phid, :pnum, :state, :eff, :exp, 'Active', 'Pending')
#                 ON CONFLICT (carrier_id, policy_number) DO UPDATE SET
#                   policyholder_id = EXCLUDED.policyholder_id,
#                   state_code      = COALESCE(EXCLUDED.state_code, policies.state_code),
#                   effective_date  = COALESCE(EXCLUDED.effective_date, policies.effective_date),
#                   expiration_date = COALESCE(EXCLUDED.expiration_date, policies.expiration_date)
#                 RETURNING policy_id
#             """),
#             {"cid": carrier_id, "phid": ph_id, "pnum": pol_num,
#              "state": state, "eff": eff, "exp": exp},
#         )
#         r = pol.fetchone()
#         return r[0] if r else None

#     # =========================================================================
#     # Resolve class_code_id from public.class_codes (upsert on miss)
#     # =========================================================================

#     async def _resolve_class_code_id(self, code: str, description: str, db: AsyncSession) -> int:
#         """Returns class_code_id from public.class_codes, inserting if absent."""
#         result = await db.execute(
#             text("SELECT class_code_id FROM public.class_codes WHERE code=:code"),
#             {"code": code},
#         )
#         row = result.fetchone()
#         if row:
#             return row[0]
#         ins = await db.execute(
#             text("INSERT INTO public.class_codes (code, description) VALUES (:code, :desc) ON CONFLICT (code) DO UPDATE SET description=COALESCE(EXCLUDED.description, class_codes.description) RETURNING class_code_id"),
#             {"code": code, "desc": description or code},
#         )
#         return ins.scalar_one()

#     # =========================================================================
#     # Fact table upserts — all use canonical_col_map
#     # =========================================================================

#     async def _upsert_policies_only(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
#         count = 0
#         for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
#             if not any(row):
#                 continue
#             pid = await self._ensure_policy(row, cmap, carrier_id, db)
#             if pid:
#                 count += 1
#         await db.commit()
#         return count

#     async def _upsert_premium_variance(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
#         count = 0
#         for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
#             if not any(row):
#                 continue
#             pid = await self._ensure_policy(row, cmap, carrier_id, db)
#             if pid is None:
#                 continue
#             est    = _safe_decimal(self._cv(row, cmap, "est_premium_end"))
#             actual = _safe_decimal(self._cv(row, cmap, "actual_premium", "premium_written"))
#             as_of  = _safe_date(self._cv(row, cmap, "as_of_date", "effective_date")) or date.today()
#             if est is None or actual is None:
#                 continue
#             await db.execute(
#                 text("""
#                     INSERT INTO premium_variance
#                       (policy_id, carrier_id, ingestion_run_id, as_of_date, est_premium_end, actual_premium)
#                     VALUES (:pid, :cid, :rid, :dt, :est, :actual)
#                     ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
#                       est_premium_end = EXCLUDED.est_premium_end,
#                       actual_premium  = EXCLUDED.actual_premium
#                 """),
#                 {"pid": pid, "cid": carrier_id, "rid": run_id,
#                  "dt": as_of, "est": float(est), "actual": float(actual)},
#             )
#             count += 1
#         await db.commit()
#         return count

#     # async def _upsert_payroll_policy(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
#     #     count = 0
#     #     for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
#     #         if not any(row):
#     #             continue
#     #         pid = await self._ensure_policy(row, cmap, carrier_id, db)
#     #         if pid is None:
#     #             continue
#     #         est      = _safe_decimal(self._cv(row, cmap, "est_payroll"))
#     #         reported = _safe_decimal(self._cv(row, cmap, "actual_payroll_reported"))
#     #         classfd  = _safe_decimal(self._cv(row, cmap, "actual_payroll_classified")) or Decimal("0")
#     #         as_of    = _safe_date(self._cv(row, cmap, "as_of_date", "effective_date")) or date.today()
#     #         if est is None and reported is None:
#     #             continue
#     #         # reported_pct and classified_pct are nullable — compute safely
#     #         rep_pct = float(reported / est * 100) if est and reported and est != 0 else None
#     #         cls_pct = float(classfd / est * 100)  if est and classfd and est != 0 else None
#     #         await db.execute(
#     #             text("""
#     #                 INSERT INTO payroll_variance_policy
#     #                   (policy_id, carrier_id, ingestion_run_id, as_of_date,
#     #                    est_payroll, actual_payroll_reported, reported_pct,
#     #                    actual_payroll_classified, classified_pct)
#     #                 VALUES (:pid, :cid, :rid, :dt, :est, :rep, :rpct, :cls, :cpct)
#     #                 ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
#     #                   est_payroll              = EXCLUDED.est_payroll,
#     #                   actual_payroll_reported  = EXCLUDED.actual_payroll_reported,
#     #                   actual_payroll_classified= EXCLUDED.actual_payroll_classified
#     #             """),
#     #             {"pid": pid, "cid": carrier_id, "rid": run_id, "dt": as_of,
#     #              "est":  float(est)      if est      is not None else None,
#     #              "rep":  float(reported) if reported is not None else None,
#     #              "rpct": rep_pct,
#     #              "cls":  float(classfd),
#     #              "cpct": cls_pct},
#     #         )
#     #         count += 1
#     #     await db.commit()
#     #     return count

#     async def _upsert_payroll_policy(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
#         count = 0
#         for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
#             if not any(row):
#                 continue
#             pid = await self._ensure_policy(row, cmap, carrier_id, db)
#             if pid is None:
#                 continue
#             est      = _safe_decimal(self._cv(row, cmap, "est_payroll"))
#             reported = _safe_decimal(self._cv(row, cmap, "actual_payroll_reported"))
#             classfd  = _safe_decimal(self._cv(row, cmap, "actual_payroll_classified")) or Decimal("0")
#             as_of    = _safe_date(self._cv(row, cmap, "as_of_date", "effective_date")) or date.today()
#             if est is None and reported is None:
#                 continue
#             # reported_pct and classified_pct are ENGINE-DERIVED columns (NUMERIC 8,4).
#             # Never compute them during ingestion — the audit calculation engine
#             # populates them. Insert NULL so the engine can set them correctly later.
#             await db.execute(
#                 text("""
#                     INSERT INTO payroll_variance_policy
#                       (policy_id, carrier_id, ingestion_run_id, as_of_date,
#                        est_payroll, actual_payroll_reported,
#                        actual_payroll_classified)
#                     VALUES (:pid, :cid, :rid, :dt, :est, :rep, :cls)
#                     ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
#                       est_payroll               = EXCLUDED.est_payroll,
#                       actual_payroll_reported   = EXCLUDED.actual_payroll_reported,
#                       actual_payroll_classified = EXCLUDED.actual_payroll_classified
#                 """),
#                 {"pid": pid, "cid": carrier_id, "rid": run_id, "dt": as_of,
#                  "est": float(est)      if est      is not None else None,
#                  "rep": float(reported) if reported is not None else None,
#                  "cls": float(classfd)},
#             )
#             count += 1
#         await db.commit()
#         return count

#     async def _upsert_payroll_class(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
#         """
#         Per-employee payroll detail (Bakeland_LLC_2026_2_24.xlsx style).
#         Aggregates wages per (policy_id, state_code, class_code) then upserts.
#         payroll_variance_class uses class_code_id FK to public.class_codes.
#         """
#         # Aggregate: (policy_id, state_code, class_code_str) → totals
#         agg: dict[tuple, dict] = defaultdict(lambda: {
#             "wages": Decimal("0"), "exposure": Decimal("0"),
#             "as_of": None, "description": "",
#         })
#         policy_cache: dict[str, Optional[int]] = {}

#         for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
#             if not any(row):
#                 continue

#             pol_idx = cmap.get("policy_number")
#             cls_idx = cmap.get("class_code")
#             if not pol_idx or not cls_idx:
#                 continue

#             pol_num = _safe_str(row[pol_idx - 1] if pol_idx - 1 < len(row) else None)
#             cls_str = _safe_str(row[cls_idx - 1] if cls_idx - 1 < len(row) else None)
#             if not pol_num or not cls_str:
#                 continue

#             if pol_num not in policy_cache:
#                 policy_cache[pol_num] = await self._ensure_policy(row, cmap, carrier_id, db)

#             pid = policy_cache[pol_num]
#             if pid is None:
#                 continue

#             state = _safe_str(self._cv(row, cmap, "state_code"), max_len=2) or "XX"
#             wages = _safe_decimal(self._cv(row, cmap, "wages")) or Decimal("0")
#             # exposure = wages when not separately mapped
#             exposure = _safe_decimal(self._cv(row, cmap, "exposure")) or wages
#             as_of = _safe_date(self._cv(row, cmap, "as_of_date", "report_date"))

#             key = (pid, state, cls_str)
#             agg[key]["wages"]    += wages
#             agg[key]["exposure"] += exposure
#             if as_of and not agg[key]["as_of"]:
#                 agg[key]["as_of"] = as_of

#         count = 0
#         for (pid, state, cls_str), totals in agg.items():
#             class_code_id = await self._resolve_class_code_id(cls_str, cls_str, db)
#             as_of = totals["as_of"] or date.today()
#             await db.execute(
#                 text("""
#                     INSERT INTO payroll_variance_class
#                       (policy_id, carrier_id, ingestion_run_id, class_code_id,
#                        state_code, as_of_date, est_payroll, actual_reported, actual_classified,
#                        reported_pct, classified_pct)
#                     VALUES (:pid, :cid, :rid, :ccid, :state, :dt,
#                             0, :wages, :exposure, NULL, NULL)
#                     ON CONFLICT (policy_id, state_code, class_code_id, ingestion_run_id)
#                     DO UPDATE SET
#                       actual_reported    = payroll_variance_class.actual_reported    + EXCLUDED.actual_reported,
#                       actual_classified  = payroll_variance_class.actual_classified  + EXCLUDED.actual_classified
#                 """),
#                 {"pid": pid, "cid": carrier_id, "rid": run_id, "ccid": class_code_id,
#                  "state": state, "dt": as_of,
#                  "wages": float(totals["wages"]), "exposure": float(totals["exposure"])},
#             )
#             count += 1

#         await db.commit()
#         return count

#     async def _upsert_zero_payroll(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
#         count = 0
#         for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
#             if not any(row):
#                 continue
#             pid = await self._ensure_policy(row, cmap, carrier_id, db)
#             if pid is None:
#                 continue
#             pol_num  = _safe_str(self._cv(row, cmap, "policy_number"))
#             insured  = _safe_str(self._cv(row, cmap, "insured_name"))
#             state    = _safe_str(self._cv(row, cmap, "state_code"), max_len=2)
#             rep_date = _safe_date(self._cv(row, cmap, "report_date", "as_of_date"))
#             freq     = _safe_str(self._cv(row, cmap, "payment_frequency"))
#             await db.execute(
#                 text("""
#                     INSERT INTO zero_payroll
#                       (policy_id, carrier_id, ingestion_run_id,
#                        policyholder_name, policy_number, state_code,
#                        report_date, payroll_frequency)
#                     VALUES (:pid, :cid, :rid, :name, :pnum, :state, :dt, :freq)
#                 """),
#                 {"pid": pid, "cid": carrier_id, "rid": run_id,
#                  "name": insured, "pnum": pol_num, "state": state,
#                  "dt": rep_date, "freq": freq},
#             )
#             count += 1
#         await db.commit()
#         return count

#     async def _upsert_missing_payroll(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
#         count = 0
#         for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
#             if not any(row):
#                 continue
#             pid = await self._ensure_policy(row, cmap, carrier_id, db)
#             if pid is None:
#                 continue
#             pol_num = _safe_str(self._cv(row, cmap, "policy_number"))
#             insured = _safe_str(self._cv(row, cmap, "insured_name"))
#             state   = _safe_str(self._cv(row, cmap, "state_code"), max_len=2)
#             p_start = _safe_date(self._cv(row, cmap, "expected_period_start"))
#             p_end   = _safe_date(self._cv(row, cmap, "expected_period_end"))
#             days    = self._cv(row, cmap, "days_overdue")
#             freq    = _safe_str(self._cv(row, cmap, "payment_frequency"))
#             await db.execute(
#                 text("""
#                     INSERT INTO missing_payroll
#                       (policy_id, carrier_id, ingestion_run_id,
#                        policyholder_name, policy_number, state_code,
#                        period_start, period_end, days_since_last_run, payroll_frequency)
#                     VALUES (:pid, :cid, :rid, :name, :pnum, :state, :ps, :pe, :days, :freq)
#                 """),
#                 {"pid": pid, "cid": carrier_id, "rid": run_id,
#                  "name": insured, "pnum": pol_num, "state": state,
#                  "ps": p_start, "pe": p_end,
#                  "days": int(days) if days is not None else None,
#                  "freq": freq},
#             )
#             count += 1
#         await db.commit()
#         return count

#     # =========================================================================
#     # XML parsing (PPlus format)
#     # =========================================================================

#     async def _parse_and_upsert_xml(
#         self,
#         carrier_id: int,
#         run_id: int,
#         file_bytes: bytes,
#         db: AsyncSession,
#     ) -> int:
#         try:
#             root = ET.fromstring(file_bytes)
#         except ET.ParseError as exc:
#             raise ValueError(f"XML parse error: {exc}") from exc

#         policy_elem = root.find("Policy")
#         if policy_elem is None:
#             raise ValueError("XML has no <Policy> element")

#         pd = policy_elem.find("PolicyData")
#         if pd is None:
#             raise ValueError("XML has no <PolicyData> element")

#         def _x(tag: str) -> Optional[str]:
#             n = pd.find(tag)
#             return n.text.strip() if n is not None and n.text else None

#         policy_number = _x("PolicyNumber")
#         if not policy_number:
#             raise ValueError("XML PolicyData has no PolicyNumber")

#         insured_name = _x("InsuredName") or "Unknown"
#         fein         = _x("Fein")
#         state_code   = _x("GoverningState") or (_x("Addr/StateProvCd"))
#         eff_date     = _safe_date(_x("EffectiveDate"))
#         exp_date     = _safe_date(_x("ExpirationDate"))
#         premium      = _safe_decimal(_x("Premium"))

#         # Upsert policyholder
#         if fein:
#             ph = await db.execute(
#                 text("""
#                     INSERT INTO policyholders (carrier_id, name, fein)
#                     VALUES (:cid, :name, :fein)
#                     ON CONFLICT (carrier_id, fein) DO UPDATE SET name = EXCLUDED.name
#                     RETURNING policyholder_id
#                 """),
#                 {"cid": carrier_id, "name": insured_name, "fein": fein},
#             )
#         else:
#             ph = await db.execute(
#                 text("INSERT INTO policyholders (carrier_id, name, fein) VALUES (:cid, :name, NULL) ON CONFLICT DO NOTHING RETURNING policyholder_id"),
#                 {"cid": carrier_id, "name": insured_name},
#             )
#             if not ph.rowcount:
#                 ph = await db.execute(
#                     text("SELECT policyholder_id FROM policyholders WHERE carrier_id=:cid AND name=:name LIMIT 1"),
#                     {"cid": carrier_id, "name": insured_name},
#                 )

#         ph_row = ph.fetchone()
#         if ph_row is None:
#             raise ValueError(f"Could not upsert policyholder for {insured_name}")
#         ph_id = ph_row[0]

#         # Upsert policy
#         pol = await db.execute(
#             text("""
#                 INSERT INTO policies
#                   (carrier_id, policyholder_id, policy_number, state_code,
#                    effective_date, expiration_date, premium_written,
#                    policy_status, audit_status)
#                 VALUES (:cid, :phid, :pnum, :state, :eff, :exp, :prem, 'Active', 'Pending')
#                 ON CONFLICT (carrier_id, policy_number) DO UPDATE SET
#                   policyholder_id = EXCLUDED.policyholder_id,
#                   state_code      = COALESCE(EXCLUDED.state_code,      policies.state_code),
#                   effective_date  = COALESCE(EXCLUDED.effective_date,  policies.effective_date),
#                   expiration_date = COALESCE(EXCLUDED.expiration_date, policies.expiration_date),
#                   premium_written = COALESCE(EXCLUDED.premium_written, policies.premium_written)
#                 RETURNING policy_id
#             """),
#             {"cid": carrier_id, "phid": ph_id, "pnum": policy_number,
#              "state": state_code, "eff": eff_date, "exp": exp_date,
#              "prem": float(premium) if premium else None},
#         )
#         pol_row = pol.fetchone()
#         if pol_row is None:
#             raise ValueError(f"Could not upsert policy {policy_number}")
#         policy_id = pol_row[0]

#         await db.commit()
#         logger.info("ingestion.xml.policy_upserted", policy_number=policy_number, policy_id=policy_id)

#         # Upsert payroll_variance_class from each Rate entry
#         rows_inserted = 0
#         for rate in root.findall(".//Rate"):
#             cls_str  = (rate.findtext("ClassCode") or "").strip()
#             desc     = (rate.findtext("Description") or cls_str).strip()
#             exposure = _safe_decimal(rate.findtext("Exposure"))
#             state    = (policy_elem.findtext(".//ComplexRateState/State") or state_code or "XX")[:2]
#             rate_eff = _safe_date(rate.findtext("EffectiveDate")) or eff_date or date.today()

#             if not cls_str or exposure is None:
#                 continue

#             class_code_id = await self._resolve_class_code_id(cls_str, desc, db)

#             await db.execute(
#                 text("""
#                     INSERT INTO payroll_variance_class
#                       (policy_id, carrier_id, ingestion_run_id, class_code_id,
#                        state_code, as_of_date, est_payroll, actual_reported, actual_classified)
#                     VALUES (:pid, :cid, :rid, :ccid, :state, :dt, :exp, 0, 0)
#                     ON CONFLICT (policy_id, state_code, class_code_id, ingestion_run_id)
#                     DO UPDATE SET
#                       est_payroll = payroll_variance_class.est_payroll + EXCLUDED.est_payroll
#                 """),
#                 {"pid": policy_id, "cid": carrier_id, "rid": run_id,
#                  "ccid": class_code_id, "state": state, "dt": rate_eff,
#                  "exp": float(exposure)},
#             )
#             rows_inserted += 1

#         # Upsert premium_variance from total premium
#         if premium is not None:
#             await db.execute(
#                 text("""
#                     INSERT INTO premium_variance
#                       (policy_id, carrier_id, ingestion_run_id, as_of_date,
#                        est_premium_end, actual_premium)
#                     VALUES (:pid, :cid, :rid, :dt, :est, :actual)
#                     ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
#                       est_premium_end = EXCLUDED.est_premium_end,
#                       actual_premium  = EXCLUDED.actual_premium
#                 """),
#                 {"pid": policy_id, "cid": carrier_id, "rid": run_id,
#                  "dt": eff_date or date.today(),
#                  "est": float(premium), "actual": float(premium)},
#             )

#         await db.commit()
#         logger.info("ingestion.xml.complete", run_id=run_id, policy_number=policy_number, rows=rows_inserted)
#         return max(rows_inserted, 1)

#     # =========================================================================
#     # Calc engine trigger
#     # =========================================================================

#     async def _trigger_calc_for_run(
#         self, schema_name: str, carrier_id: int, run_id: int, db: AsyncSession
#     ) -> None:
#         result = await db.execute(
#             text("SELECT DISTINCT policy_id FROM premium_variance WHERE ingestion_run_id=:rid AND carrier_id=:cid"),
#             {"rid": run_id, "cid": carrier_id},
#         )
#         policy_ids = [r[0] for r in result.fetchall()]
#         calc = AuditCalculationService()
#         for policy_id in policy_ids:
#             try:
#                 await calc.run(schema_name, carrier_id, policy_id, run_id, db)
#             except Exception as exc:
#                 logger.error("ingestion.calc.failed", policy_id=policy_id, run_id=run_id, error=str(exc))


from __future__ import annotations

"""
IngestionService — Phase 3.

Stage 1 — run():
  Creates ingestion_run at status='awaiting_mapping'.
  Calls AutoMappingService to generate field_mapping_proposals.
  Returns (run_id, session_id). Does NOT write to fact tables.

Stage 2 — run_post_approval():
  Called only after TENANT_ADMIN approves the mapping gate.
  Uses approved field_mapping_proposals to parse and upsert fact rows.
  Advances run status: awaiting_mapping → processing → complete.
  Triggers AuditCalculationService.
"""

import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional

import openpyxl
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.audit_calculation_service import AuditCalculationService
from app.services.auto_mapping_service import AutoMappingService
from app.utils.text_utils import find_col, normalise

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Scalar coercers
# ---------------------------------------------------------------------------

def _safe_decimal(value: object) -> Optional[Decimal]:
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if s in ("", "N/A", "NA", "-", "n/a", "None"):
        return None
    try:
        return Decimal(s)
    except Exception:
        return None


def _safe_date(value: object) -> Optional[date]:
    if isinstance(value, (date, datetime)):
        return value.date() if isinstance(value, datetime) else value
    if isinstance(value, str):
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%d/%m/%Y"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                pass
    return None


def _safe_str(value: object, max_len: int | None = None) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "n/a", "na"):
        return None
    return s[:max_len] if max_len else s


# ---------------------------------------------------------------------------
# IngestionService
# ---------------------------------------------------------------------------

class IngestionService:
    """
    Phase 3 ingestion pipeline.

    Routing after approval is based entirely on which CANONICAL columns
    exist in the approved mapping proposals — not on original header names.

    Routing priority (first match wins):
      wages + class_code                         → payroll_variance_class
      est_payroll + actual_payroll_reported       → payroll_variance_policy
      est_premium_end OR actual_premium           → premium_variance
      reason_code OR (report_date+policy_number) → zero_payroll
      expected_period_start                       → missing_payroll
      policy_number only                          → policies (header ingestion)
    """

    def __init__(self) -> None:
        self._calc_service = AuditCalculationService()
        self._auto_mapping = AutoMappingService()

    # =========================================================================
    # Stage 1 — Upload
    # =========================================================================

    async def run(
        self,
        schema_name: str,
        carrier_id: int,
        source_id: int,
        file_bytes: bytes,
        file_type: str,
        db: AsyncSession,
        uploaded_by: str = "system",
        override_use_engine: Optional[bool] = None,
        ingestion_mode: str = "calc_engine",
    ) -> tuple[int, int]:
        """Creates ingestion_run + generates mapping proposals. Returns (run_id, session_id)."""
        print("file type in ingestion", file_type)
        if file_type not in ("xlsx", "xml"):
            raise ValueError(f"Unsupported file type: '{file_type}'. Accepted: xlsx, xml")

        run_id = await self._create_ingestion_run(
            carrier_id, source_id, uploaded_by, override_use_engine, db,
            schema_name=schema_name,
            ingestion_mode=ingestion_mode,
        )
        try:
            session_id = await self._auto_mapping.run(
                run_id=run_id,
                carrier_id=carrier_id,
                file_bytes=file_bytes,
                db=db,
                file_type=file_type,
                schema_name=schema_name,
            )
        except Exception as exc:
            logger.error("ingestion.auto_mapping.failed", run_id=run_id, error=str(exc))
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                await db.execute(
                    text("UPDATE ingestion_runs SET status='failed', error_detail=:err WHERE run_id=:rid"),
                    {"err": str(exc)[:2000], "rid": run_id},
                )
                await db.commit()
            except Exception:
                await db.rollback()
            raise

        logger.info("ingestion.awaiting_mapping", run_id=run_id, session_id=session_id)
        return run_id, session_id

    # =========================================================================
    # Stage 2 — Post-approval
    # =========================================================================

    async def run_post_approval(
        self,
        schema_name: str,
        carrier_id: int,
        run_id: int,
        session_id: int,
        db: AsyncSession,
    ) -> int:
        """Parses and upserts fact rows using approved mapping proposals."""
        proposals = await self._load_approved_proposals(session_id, db)
        if not proposals:
            raise ValueError(f"No approved proposals found for session {session_id}")

        file_bytes = await self._load_file_bytes(run_id, db)

        try:
            # await self._advance_status(run_id, "processing", db)
            await self._advance_status(run_id, "processing", db, schema_name=schema_name)

            if file_bytes and (file_bytes[:5] in (b"<?xml", b"<PPlu") or b"<PPlus" in file_bytes[:100]):
                rows_ingested = await self._parse_and_upsert_xml(
                    carrier_id=carrier_id, run_id=run_id,
                    file_bytes=file_bytes, db=db,
                )
            elif file_bytes and self._is_audit_report_xlsx(file_bytes):
                # Multi-section Audit Report XLSX — requires a dedicated parser
                # because the standard _process_sheet() stops at the first header
                # row and never reaches the Employee Detail section containing
                # per-employee wages and class codes.
                rows_ingested = await self._parse_and_upsert_audit_report_xlsx(
                    carrier_id=carrier_id, run_id=run_id,
                    file_bytes=file_bytes, proposals=proposals, db=db,
                )
            elif file_bytes:
                rows_ingested = await self._parse_and_upsert_xlsx(
                    carrier_id=carrier_id, run_id=run_id,
                    file_bytes=file_bytes, proposals=proposals, db=db,
                )
            else:
                logger.warning("ingestion.post_approval.no_file_bytes", run_id=run_id)
                rows_ingested = 0

            # await self._complete_run(run_id, rows_ingested, db)
            await self._complete_run(run_id, rows_ingested, db, schema_name=schema_name)

        except Exception as exc:
            logger.error("ingestion.post_approval.failed", run_id=run_id, error=str(exc))
            try:
                await db.rollback()
            except Exception:
                pass
            try:
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
                await db.commit()
                await db.execute(text(f'SET search_path TO "{schema_name}", public'))
                await db.execute(
                    text("UPDATE ingestion_runs SET status='failed', error_detail=:err WHERE run_id=:rid"),
                    {"err": str(exc)[:2000], "rid": run_id},
                )
                await db.commit()
            except Exception:
                await db.rollback()
            raise

        await self._trigger_calc_for_run(schema_name, carrier_id, run_id, db)
        return rows_ingested

    # =========================================================================
    # Run lifecycle helpers
    # =========================================================================

    # async def _create_ingestion_run(
    #     self,
    #     carrier_id: int,
    #     source_id: int,
    #     uploaded_by: str,
    #     override_use_engine: Optional[bool],
    #     db: AsyncSession,
    # ) -> int:
    #     result = await db.execute(
    #         text("""
    #             INSERT INTO ingestion_runs
    #               (carrier_id, source_id, uploaded_by, started_at, status,
    #                rows_skipped, rows_failed, skip_on_error, use_calculation_engine)
    #             VALUES (:cid, :sid, :by, now(), 'awaiting_mapping', 0, 0, FALSE, :engine)
    #             RETURNING run_id
    #         """),
    #         {"cid": carrier_id, "sid": source_id, "by": uploaded_by, "engine": override_use_engine},
    #     )
    #     await db.commit()
    #     run_id: int = result.scalar_one()
    #     logger.info("ingestion.run.created", run_id=run_id, carrier_id=carrier_id)
    #     return run_id
    async def _create_ingestion_run(
        self,
        carrier_id: int,
        source_id: int,
        uploaded_by: str,
        override_use_engine: Optional[bool],
        db: AsyncSession,
        schema_name: str = "public",
        ingestion_mode: str = "calc_engine",
    ) -> int:
        result = await db.execute(
            text("""
                INSERT INTO ingestion_runs
                  (carrier_id, source_id, uploaded_by, started_at, status,
                   rows_skipped, rows_failed, skip_on_error, use_calculation_engine,
                   ingestion_mode)
                VALUES (:cid, :sid, :by, now(), 'awaiting_mapping', 0, 0, FALSE, :engine, :mode)
                RETURNING run_id
            """),
            {
                "cid":    carrier_id,
                "sid":    source_id,
                "by":     uploaded_by,
                "engine": override_use_engine,
                "mode":   ingestion_mode,
            },
        )
        await db.commit()
        # Re-assert search_path — asyncpg resets it to the server default after
        # every db.commit(). All subsequent queries in this session (auto_mapping,
        # _persist_session_and_proposals) must run against the tenant schema.
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        run_id: int = result.scalar_one()
        logger.info("ingestion.run.created", run_id=run_id, carrier_id=carrier_id, ingestion_mode=ingestion_mode)
        return run_id

    async def _advance_status(
        self, run_id: int, status: str, db: AsyncSession, schema_name: str = "public"
    ) -> None:
        # Re-assert search_path before the UPDATE — prior commits reset it
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.execute(
            text("UPDATE ingestion_runs SET status=:s WHERE run_id=:rid"),
            {"s": status, "rid": run_id},
        )
        await db.commit()

    async def _complete_run(
        self, run_id: int, rows: int, db: AsyncSession, schema_name: str = "public"
    ) -> None:
        # Re-assert search_path before the UPDATE — previous upsert commits reset it
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.commit()
        await db.execute(text(f'SET search_path TO "{schema_name}", public'))
        await db.execute(
            text("UPDATE ingestion_runs SET status='complete', rows_ingested=:rows, completed_at=now() WHERE run_id=:rid"),
            {"rows": rows, "rid": run_id},
        )
        await db.commit()

    async def _load_approved_proposals(self, session_id: int, db: AsyncSession) -> list[dict]:
        result = await db.execute(
            text("""
                SELECT source_field, proposed_target, transform_fn
                FROM field_mapping_proposals
                WHERE session_id=:sid AND is_excluded=FALSE AND proposed_target IS NOT NULL
            """),
            {"sid": session_id},
        )
        return [
            {"source_field": r[0], "proposed_target": r[1], "transform_fn": r[2]}
            for r in result.fetchall()
        ]

    async def _load_file_bytes(self, run_id: int, db: AsyncSession) -> Optional[bytes]:
        try:
            result = await db.execute(
                text("SELECT raw_file_bytes FROM ingestion_runs WHERE run_id=:rid"),
                {"rid": run_id},
            )
            row = result.fetchone()
            if row and row[0]:
                return bytes(row[0])
        except Exception as exc:
            logger.warning("ingestion.file_bytes.load_failed", run_id=run_id, error=str(exc))
        return None

    # =========================================================================
    # Audit Report XLSX detection
    # =========================================================================

    @staticmethod
    def _is_audit_report_xlsx(file_bytes: bytes) -> bool:
        """
        Returns True when the XLSX file is a structured Audit Report.
        Detection: the first worksheet must contain the text "AUDIT REPORT"
        somewhere in the first five rows.

        Note: read_only=True is intentionally NOT used here. Merged-cell content
        (like the "AUDIT REPORT - Summary" title spanning columns A–C) is only
        accessible when read_only=False; in streaming read-only mode openpyxl
        returns empty strings for all non-top-left cells in a merge range.
        """
        try:
            wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True, read_only=False)
            ws = wb.worksheets[0]
            for row in ws.iter_rows(min_row=1, max_row=5, values_only=True):
                joined = " ".join(str(v) for v in row if v is not None).upper()
                if "AUDIT REPORT" in joined:
                    wb.close()
                    return True
            wb.close()
        except Exception:
            pass
        return False

    # =========================================================================
    # Multi-section Audit Report XLSX parser
    # =========================================================================

    async def _parse_and_upsert_audit_report_xlsx(
        self,
        carrier_id: int,
        run_id: int,
        file_bytes: bytes,
        proposals: list[dict],
        db: AsyncSession,
    ) -> int:
        """
        Parses the structured Audit Report XLSX and writes:
          - policies + policyholders (with state_code, payment_frequency, owner_status)
          - payroll_variance_class  (one row per class code, exposure_assessed as est_payroll)
          - payroll_variance_policy (one summary row + synthetic per-period rows)
          - premium_variance        (Total Premium Calculated)
          - missing_payroll         (via calc engine after ingestion)

        Correct calculation model (matches reference premium_agent.py):
          est_payroll (YTD)          = (exposure_assessed / expected_subs) * actual_submitted
          actual_payroll_reported    = same as est when audit-only; overwritten by payroll file upload
          variance                   = actual_payroll_reported - est_payroll (calc engine)
        """
        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
        ws = wb.worksheets[0]
        all_rows = list(ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True))
        wb.close()

        # ── Step 1: Policy header metadata ────────────────────────────────────
        policy_number:     Optional[str]   = None
        insured_name:      Optional[str]   = None
        effective_date:    Optional[str]   = None
        expiration_date:   Optional[str]   = None
        state_code:        Optional[str]   = None
        payment_frequency: Optional[str]   = None
        owner_status:      Optional[str]   = None
        total_premium:     Optional[float] = None

        for row in all_rows[0:8]:
            for cell in row:
                cs = str(cell or "").strip()
                if cs.startswith("Policy Number:"):
                    policy_number = cs.replace("Policy Number:", "").strip()
                elif cs.startswith("Policy Period:"):
                    parts = cs.replace("Policy Period:", "").strip().split(" - ")
                    if len(parts) == 2:
                        effective_date  = parts[0].strip()
                        expiration_date = parts[1].strip()
            row_text = str(row[0] or "").strip()
            if "Date Report Run:" in row_text:
                for cell in row[1:]:
                    cs = str(cell or "").strip()
                    if cs:
                        insured_name = cs
                        break

        if not policy_number:
            logger.warning("ingestion.audit_report.no_policy_number", run_id=run_id)
            return 0

        # ── Step 2: Classification Summary — dynamic header-driven column lookup ──
        # Header pattern: State | Class Code | Description | ... | Exposure Received | Exposure Assessed
        # IMPORTANT: skip any row that also contains "Net Rate" (that's the Rate Detail header)
        class_code_map: dict[tuple, dict] = {}  # (class_code, state) → {exposure_assessed, net_rate, est_cc_premium}

        for idx, row in enumerate(all_rows):
            cells_clean = [
                str(v).replace("\n", " ").strip()
                for v in row if v is not None and str(v).replace("\n", " ").strip()
            ]
            is_classification_summary = (
                "State" in cells_clean
                and "Class Code" in cells_clean
                and "Description" in cells_clean
                and "Net Rate" not in cells_clean      # exclude Rate Detail header
                and "Employee Count" not in cells_clean
            )
            if not is_classification_summary:
                continue

            # Dynamically find "Exposure Assessed" column index
            full_header = [str(v).replace("\n", " ").strip() if v is not None else "" for v in row]
            exp_assessed_idx: Optional[int] = None
            for ci, h in enumerate(full_header):
                if "Exposure Assessed" in h:
                    exp_assessed_idx = ci
                    break

            # Collect data rows — stop at the Rate Detail "State | Class Code" header
            for data_row in all_rows[idx + 1:]:
                first = str(data_row[0] or "").strip()
                # Stop at the Rate Detail header (second State/ClassCode header)
                if first == "State" and any(
                    "Net Rate" in str(v or "").replace("\n", " ")
                    for v in data_row if v is not None
                ):
                    break
                if first.upper() == "TOTAL" or "AUDIT REPORT" in first.upper():
                    break
                if not first or not data_row[1]:
                    continue

                if not state_code:
                    state_code = first[:2]
                cc_str = str(data_row[1] or "").strip()
                exp_val = 0.0
                if exp_assessed_idx is not None and exp_assessed_idx < len(data_row):
                    try:
                        exp_val = float(data_row[exp_assessed_idx] or 0)
                    except (TypeError, ValueError):
                        pass
                key = (cc_str, first[:2])
                if key not in class_code_map:
                    class_code_map[key] = {"exposure_assessed": exp_val, "net_rate": 0.0, "est_cc_premium": 0.0}
            break

        # ── Step 3: Rate Detail — enrich net_rate per class code ──────────────
        for idx, row in enumerate(all_rows):
            cells_clean = [
                str(v).replace("\n", " ").strip()
                for v in row if v is not None and str(v).replace("\n", " ").strip()
            ]
            if "Net Rate" not in cells_clean or "Employee Count" not in cells_clean:
                continue
            full_header = [str(v).replace("\n", " ").strip() if v is not None else "" for v in row]
            nr_idx  = next((ci for ci, h in enumerate(full_header) if h == "Net Rate"), None)
            cc_idx  = next((ci for ci, h in enumerate(full_header) if h == "Class Code"), None)
            st_idx  = next((ci for ci, h in enumerate(full_header) if h == "State"), 0)
            for data_row in all_rows[idx + 1:]:
                first = str(data_row[0] or "").strip()
                if first.upper() in ("TOTAL", "STATE") or "AUDIT REPORT" in first.upper():
                    break
                if not first:
                    continue
                if nr_idx is None or cc_idx is None:
                    continue
                cc_str = str(data_row[cc_idx] or "").strip() if cc_idx < len(data_row) else ""
                nr_raw = str(data_row[nr_idx] or "").replace(",", "").strip() if nr_idx < len(data_row) else ""
                state  = first[:2]
                key    = (cc_str, state)
                try:
                    nr = float(nr_raw)
                    if key in class_code_map and class_code_map[key]["net_rate"] == 0.0:
                        class_code_map[key]["net_rate"] = nr
                        class_code_map[key]["est_cc_premium"] = round(
                            class_code_map[key]["exposure_assessed"] * nr, 2
                        )
                except (ValueError, TypeError):
                    pass
            break

        exposure_assessed_total = sum(cc["exposure_assessed"] for cc in class_code_map.values())

        # ── Step 4: Breakdown of Premium ──────────────────────────────────────
        for row in all_rows[15:42]:
            cells = [str(v).strip() for v in row if v is not None and str(v).strip()]
            if len(cells) >= 2 and "Total Premium Calculated" in cells[-2]:
                try:
                    total_premium = float(str(cells[-1]).replace(",", ""))
                except Exception:
                    pass
                break

        # ── Step 5: Business Entity — payment_frequency + actual_submitted_count ─
        actual_submitted_count: int = 0
        for idx, row in enumerate(all_rows):
            cells_clean = [
                str(v).replace("\n", " ").strip()
                for v in row if v is not None and str(v).replace("\n", " ").strip()
            ]
            if "Payroll Frequency" not in cells_clean or "Business Entity" not in cells_clean:
                continue
            full_header = [str(v).replace("\n", " ").strip() if v is not None else "" for v in row]
            freq_idx      = next((ci for ci, h in enumerate(full_header) if h == "Payroll Frequency"), None)
            submitted_idx = next(
                (ci for ci, h in enumerate(full_header)
                 if "Number of Payroll Reports Submitted" in h and "Zero" not in h),
                None,
            )
            for data_row in all_rows[idx + 1: idx + 5]:
                first = str(data_row[0] or "").strip()
                if not first or first.upper() in ("PAYROLL COMPANY", "INSURED - SELF ADMINISTERED"):
                    continue
                if freq_idx is not None and freq_idx < len(data_row):
                    freq_raw = str(data_row[freq_idx] or "").strip()
                    freq_map = {
                        "1W": "Weekly", "2W": "Bi-Weekly",
                        "SM": "Semi-Monthly", "1M": "Monthly",
                        "2M": "Monthly", "1Q": "Monthly",
                    }
                    payment_frequency = freq_map.get(freq_raw) or None
                if submitted_idx is not None and submitted_idx < len(data_row):
                    try:
                        actual_submitted_count = int(float(str(data_row[submitted_idx] or 0)))
                    except (TypeError, ValueError):
                        pass
                break
            break

        # ── Step 6: Key Individuals — owner_status ─────────────────────────────
        for idx, row in enumerate(all_rows):
            cells_clean = [
                str(v).replace("\n", " ").strip()
                for v in row if v is not None and str(v).replace("\n", " ").strip()
            ]
            if "Included/Excluded" not in cells_clean or "Business Entity" not in cells_clean:
                continue
            full_header = [str(v).replace("\n", " ").strip() if v is not None else "" for v in row]
            ie_idx = next((ci for ci, h in enumerate(full_header) if h == "Included/Excluded"), None)
            included = excluded = 0
            for data_row in all_rows[idx + 1:]:
                if not any(data_row):
                    break
                first = str(data_row[0] or "").strip()
                if "AUDIT REPORT" in first.upper():
                    break
                if ie_idx is not None and ie_idx < len(data_row):
                    ie_val = str(data_row[ie_idx] or "").strip().upper()
                    if ie_val in ("I", "INCLUDED"):
                        included += 1
                    elif ie_val in ("E", "EXCLUDED"):
                        excluded += 1
            owner_status = "Included" if included > 0 else ("Excluded" if excluded > 0 else None)
            break

        # ── Step 7: Upsert policy record ───────────────────────────────────────
        synthetic_row = (policy_number, insured_name or "Unknown", effective_date, expiration_date, None)
        synthetic_cmap = {"policy_number": 1, "insured_name": 2, "effective_date": 3, "expiration_date": 4}
        policy_id = await self._ensure_policy(
            row=synthetic_row, cmap=synthetic_cmap, carrier_id=carrier_id, db=db
        )
        if policy_id is None:
            logger.warning("ingestion.audit_report.policy_upsert_failed", run_id=run_id, policy_number=policy_number)
            return 0

        # Enrich policy with audit-derived fields
        valid_freq  = {"Weekly", "Bi-Weekly", "Semi-Monthly", "Monthly"}
        valid_owner = {"Included", "Excluded"}
        safe_freq   = payment_frequency if payment_frequency in valid_freq else None
        safe_owner  = owner_status if owner_status in valid_owner else None

        await db.execute(
            text("""
                UPDATE policies SET
                    state_code        = COALESCE(:sc,    state_code),
                    payment_frequency = COALESCE(:freq,  payment_frequency),
                    owner_status      = COALESCE(:owner, owner_status)
                WHERE policy_id = :pid
            """),
            {"sc": state_code, "freq": safe_freq, "owner": safe_owner, "pid": policy_id},
        )
        await db.commit()

        # ── Step 8: Write payroll_variance_class ──────────────────────────────
        # est_payroll per class = exposure_assessed (full-term from Classification Detail).
        # The calc engine will prorate this to YTD using: est_ytd = est * (submitted/expected).
        rows_inserted = 0
        for (cc_str, st_str), cc_data in class_code_map.items():
            if not cc_str:
                continue
            class_code_id = await self._resolve_class_code_id(cc_str, cc_str, db)
            await db.execute(
                text("""
                    INSERT INTO payroll_variance_class
                      (policy_id, carrier_id, ingestion_run_id, class_code_id,
                       state_code, as_of_date, est_payroll, actual_reported, actual_classified)
                    VALUES (:pid, :cid, :rid, :ccid, :state, now(), :wages, :wages, :wages)
                    ON CONFLICT (policy_id, state_code, class_code_id, ingestion_run_id)
                    DO UPDATE SET
                      est_payroll       = EXCLUDED.est_payroll,
                      actual_reported   = EXCLUDED.actual_reported,
                      actual_classified = EXCLUDED.actual_classified
                """),
                {
                    "pid":   policy_id, "cid": carrier_id, "rid": run_id,
                    "ccid":  class_code_id, "state": st_str,
                    "wages": cc_data["exposure_assessed"],
                },
            )
            rows_inserted += 1
        await db.commit()

        # ── Step 9: Compute two distinct submission counts (reference: mock_data_api.py) ─
        #
        # The mock API computes TWO separate counts from the audit report:
        #
        #   a_actual_payroll_sub  = expected_till_today
        #       = calendar periods elapsed from eff_date to system date
        #       → used as submitted_count for YTD proration of est_payroll
        #       → formula: est_ytd = (exposure_full / expected_full) * expected_till_today
        #
        #   a_actual_payroll_sub2 = actual_submissions
        #       = "Number of Payroll Reports Submitted" from Business Entity section
        #       → used for: missing = max(0, expected_full - actual_submissions_from_file)
        #       → used for: submit_rate = actual_submissions_from_file / expected_full * 100
        #
        # Reference: mock_data_api.py _parse_audit_report() business_entity section
        # Reference: premium_agent.py submitted_count vs submitted_count2

        from datetime import datetime as _dt
        from dateutil.relativedelta import relativedelta as _rd

        freq_to_annual = {"Weekly": 52, "Bi-Weekly": 26, "Semi-Monthly": 24, "Monthly": 12}
        expected_full_term = freq_to_annual.get(safe_freq or "", 12)

        # expected_till_today: calendar periods from eff_date to today
        # (same logic as mock_data_api.py expected_till_today calculation)
        expected_till_today = expected_full_term  # default: full term
        if effective_date:
            try:
                eff_dt_obj = _dt.strptime(effective_date, "%m/%d/%Y")
                today_dt   = _dt.now()
                diff       = _rd(today_dt, eff_dt_obj)
                months_diff = (diff.years * 12) + diff.months
                if safe_freq == "Weekly":
                    expected_till_today = max(1, round((today_dt - eff_dt_obj).days / 7))
                elif safe_freq == "Bi-Weekly":
                    expected_till_today = max(1, round((today_dt - eff_dt_obj).days / 14))
                elif safe_freq == "Semi-Monthly":
                    expected_till_today = max(1, months_diff * 2)
                else:  # Monthly
                    expected_till_today = max(1, months_diff)
                # Cap at expected_full_term
                expected_till_today = min(expected_till_today, expected_full_term)
            except Exception:
                expected_till_today = expected_full_term

        # actual_submissions_from_file: "Number of Payroll Reports Submitted" in Business Entity
        # This is actual_submitted_count already extracted in Step 5
        actual_subs_from_file = actual_submitted_count  # a_actual_payroll_sub2

        # YTD-prorated est_payroll uses expected_till_today (not actual_subs_from_file)
        if expected_full_term > 0 and exposure_assessed_total > 0:
            est_payroll_ytd = round(
                (exposure_assessed_total / expected_full_term) * expected_till_today, 2
            )
        else:
            est_payroll_ytd = exposure_assessed_total

        # Update total_est_payroll on policy with YTD estimate
        await db.execute(
            text("UPDATE policies SET total_est_payroll = :wages WHERE policy_id = :pid"),
            {"wages": est_payroll_ytd, "pid": policy_id},
        )

        # ── Step 10: Write payroll_variance_policy summary row ─────────────────
        # FIRST: delete all synthetic per-period rows (negative run_ids) for this policy
        # that were written by previous ingestion runs of the same audit report.
        # Without this, re-uploading the same policy accumulates stale rows and
        # inflates the Received count.
        await db.execute(
            text("""
                DELETE FROM payroll_variance_policy
                WHERE policy_id = :pid AND ingestion_run_id < 0
            """),
            {"pid": policy_id},
        )
        await db.commit()

        # One authoritative row representing the audit report's summary.
        # actual_payroll_reported = est_payroll_ytd here (audit report IS the source of truth).
        # When the payroll file is separately uploaded, actual_reported gets updated.
        eff_dt = _safe_date(effective_date) if effective_date else None
        await db.execute(
            text("""
                INSERT INTO payroll_variance_policy
                  (policy_id, carrier_id, ingestion_run_id, as_of_date,
                   est_payroll, actual_payroll_reported, actual_payroll_classified)
                VALUES (:pid, :cid, :rid, :dt, :est, :rep, :cls)
                ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
                  est_payroll               = EXCLUDED.est_payroll,
                  actual_payroll_reported   = EXCLUDED.actual_payroll_reported,
                  actual_payroll_classified = EXCLUDED.actual_payroll_classified
            """),
            {
                "pid": policy_id, "cid": carrier_id, "rid": run_id,
                "dt":  eff_dt,
                "est": est_payroll_ytd, "rep": est_payroll_ytd, "cls": est_payroll_ytd,
            },
        )
        await db.commit()

        # Store both submission counts on the policy record so the calc engine
        # and submission metrics API can access them directly.
        # expected_till_today → stored in a JSON-compatible way using notes/narrative
        # actual_subs_from_file → used for missing + submit_rate
        # We store them on policies table as two new-style fields using
        # the existing payroll_variance_policy.reported_pct column as a proxy
        # for submit_rate so the engine can persist it.
        # The cleanest approach: store counts in two columns we already have:
        # payroll_variance_policy for the main run stores:
        #   reported_pct  = submit_rate = actual_subs_from_file / expected_full_term * 100
        if expected_full_term > 0 and actual_subs_from_file >= 0:
            # Store as RATIO (0.667) not percentage (66.7).
            # NaIndicator "pct" format uses Intl.NumberFormat percent style
            # which multiplies by 100 internally. Storing 0.667 → displays 66.7%.
            submit_rate_ratio = round(actual_subs_from_file / expected_full_term, 4)
            await db.execute(
                text("""
                    UPDATE payroll_variance_policy
                    SET reported_pct = :rate, classified_pct = :rate
                    WHERE policy_id = :pid AND ingestion_run_id = :rid
                """),
                {"rate": submit_rate_ratio, "pid": policy_id, "rid": run_id},
            )
            await db.commit()

        # Write one synthetic row per additional submitted period
        # so "Received" count in the UI matches actual_subs_from_file
        if actual_subs_from_file > 1 and eff_dt is not None and safe_freq:
            from datetime import timedelta
            per_period = round(est_payroll_ytd / actual_subs_from_file, 2)
            for i in range(1, actual_subs_from_file):
                try:
                    if safe_freq == "Monthly":
                        month = eff_dt.month + i
                        year  = eff_dt.year + (month - 1) // 12
                        month = ((month - 1) % 12) + 1
                        from datetime import date as _d
                        period_dt = eff_dt.replace(year=year, month=month)
                    else:
                        cycle = {"Weekly": 7, "Bi-Weekly": 14, "Semi-Monthly": 15}
                        period_dt = eff_dt + timedelta(days=cycle.get(safe_freq, 30) * i)
                    await db.execute(
                        text("""
                            INSERT INTO payroll_variance_policy
                              (policy_id, carrier_id, ingestion_run_id, as_of_date,
                               est_payroll, actual_payroll_reported, actual_payroll_classified)
                            VALUES (:pid, :cid, :rid, :dt, :est, :rep, :cls)
                            ON CONFLICT (policy_id, ingestion_run_id) DO NOTHING
                        """),
                        {
                            "pid": policy_id, "cid": carrier_id,
                            "rid": -(run_id * 1000 + i),
                            "dt":  period_dt,
                            "est": per_period, "rep": per_period, "cls": per_period,
                        },
                    )
                except Exception as exc:
                    logger.warning("ingestion.audit_report.period_row_failed", idx=i, error=str(exc))
            await db.commit()

        # ── Step 11: Write premium_variance ───────────────────────────────────
        # Reference: mock_data_api.py + premium_agent.py
        #
        # est_premium_end  = est_ytd_premium = (est_cc_premium_full / expected_full) * expected_till_today
        #   where expected_till_today = calendar periods from eff_date to today (a_actual_payroll_sub)
        #   This is NOT the full-term audit report total ($30,456.96)
        #
        # actual_premium   = SUM(earned_premium) from payroll file rows (a_actual_payroll_sub2 submissions)
        #   When audit report only (no payroll file): actual_premium = est_ytd (variance = 0 until payroll uploaded)
        #   When payroll file also uploaded: _upsert_payroll_class overwrites actual_premium with earned_premium
        #
        # total_premium from audit report = est_cc_premium_full (used only as the full-term base)
        if total_premium is not None:
            # Compute est_ytd using expected_till_today from Step 9
            if expected_full_term > 0:
                est_ytd_prem = round(
                    (float(total_premium) / expected_full_term) * expected_till_today, 2
                )
            else:
                est_ytd_prem = float(total_premium)

            # Check if payroll file was already ingested (inserted actual_premium first)
            existing_pv = await db.execute(
                text("""
                    SELECT pv_id, actual_premium FROM premium_variance
                    WHERE policy_id = :pid
                    ORDER BY ingestion_run_id DESC LIMIT 1
                """),
                {"pid": policy_id},
            )
            existing_pv_row = existing_pv.fetchone()

            # If payroll file already set actual_premium, preserve it.
            # Otherwise set actual_premium = est_ytd_prem (will be updated when payroll uploads).
            if existing_pv_row and existing_pv_row[1] and float(existing_pv_row[1]) > 0:
                # Payroll already ingested: just update est_premium_end
                await db.execute(
                    text("""
                        UPDATE premium_variance
                        SET est_premium_end = :est
                        WHERE pv_id = :pv_id
                    """),
                    {"est": est_ytd_prem, "pv_id": existing_pv_row[0]},
                )
            else:
                # Audit report first: insert with est = actual (variance = 0 until payroll uploads)
                await db.execute(
                    text("""
                        INSERT INTO premium_variance
                          (policy_id, carrier_id, ingestion_run_id, as_of_date,
                           est_premium_end, actual_premium)
                        VALUES (:pid, :cid, :rid, :dt, :est, :actual)
                        ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
                          est_premium_end = EXCLUDED.est_premium_end,
                          actual_premium  = EXCLUDED.actual_premium
                    """),
                    {
                        "pid": policy_id, "cid": carrier_id, "rid": run_id,
                        "dt":  eff_dt,
                        "est":    est_ytd_prem,
                        "actual": est_ytd_prem,
                    },
                )
            await db.commit()

        logger.info(
            "ingestion.audit_report.complete",
            run_id=run_id, policy_number=policy_number,
            exposure_assessed=exposure_assessed_total,
            est_payroll_ytd=est_payroll_ytd,
            submitted=actual_submitted_count,
            total_premium=total_premium, class_codes=rows_inserted,
        )
        return max(rows_inserted, 1)

    async def _upsert_payroll_class_from_audit_report(
        self,
        all_rows: list[tuple],
        header_row_idx: int,
        canonical_col_map: dict[str, int],
        policy_id: int,
        carrier_id: int,
        run_id: int,
        db: AsyncSession,
    ) -> int:
        """
        Iterates the Employee Detail data rows (below header_row_idx) and
        upserts one payroll_variance_class row per employee per class code.

        Stops when it encounters:
          - A row whose first non-null cell is empty, 'Total', or starts with
            'AUDIT REPORT' (indicating the next section header)
          - End of the worksheet
        """
        rows_inserted = 0

        # Aggregation: (state_code, class_code_str) → cumulative wages
        # We aggregate first so that employees with multiple rate-band rows
        # for the same class code are combined before upserting.
        from collections import defaultdict
        wage_agg: dict[tuple[str, str], float] = defaultdict(float)

        for row in all_rows[header_row_idx + 1:]:
            # Determine first non-null cell to detect section boundaries
            first_cell = ""
            for cell in row:
                if cell is not None:
                    first_cell = str(cell).replace("\n", " ").strip()
                    break

            if not first_cell:
                continue
            if first_cell.upper() == "TOTAL":
                break
            if "AUDIT REPORT" in first_cell.upper():
                break

            state_raw   = self._cv(row, canonical_col_map, "state_code")
            class_raw   = self._cv(row, canonical_col_map, "class_code")
            wages_raw   = self._cv(row, canonical_col_map, "wages")

            state_str = str(state_raw or "").strip()[:2] if state_raw else "XX"
            class_str = str(class_raw or "").strip() if class_raw else ""
            wages_val = float(str(wages_raw or 0).replace(",", "") or 0)

            if not class_str:
                continue

            wage_agg[(state_str, class_str)] += wages_val

        # Upsert one row per (state, class_code) aggregation bucket
        for (state_str, class_str), total_wages in wage_agg.items():
            class_code_id = await self._resolve_class_code_id(class_str, class_str, db)

            await db.execute(
                text("""
                    INSERT INTO payroll_variance_class
                      (policy_id, carrier_id, ingestion_run_id, class_code_id,
                       state_code, as_of_date, est_payroll, actual_reported, actual_classified)
                    VALUES (:pid, :cid, :rid, :ccid, :state, now(), :wages, :wages, :wages)
                    ON CONFLICT (policy_id, state_code, class_code_id, ingestion_run_id)
                    DO UPDATE SET
                      actual_reported    = payroll_variance_class.actual_reported + EXCLUDED.actual_reported,
                      actual_classified  = payroll_variance_class.actual_classified + EXCLUDED.actual_classified
                """),
                {
                    "pid":   policy_id,
                    "cid":   carrier_id,
                    "rid":   run_id,
                    "ccid":  class_code_id,
                    "state": state_str,
                    "wages": total_wages,
                },
            )
            rows_inserted += 1

        await db.commit()
        logger.info(
            "ingestion.audit_report.payroll_class_written",
            run_id=run_id,
            policy_id=policy_id,
            rows=rows_inserted,
        )
        return rows_inserted

    # =========================================================================
    # XLSX parsing (generic — for non-Audit-Report files)
    # =========================================================================

    async def _parse_and_upsert_xlsx(
        self,
        carrier_id: int,
        run_id: int,
        file_bytes: bytes,
        proposals: list[dict],
        db: AsyncSession,
    ) -> int:
        # Build source_field → canonical_name lookup from approved proposals
        mapping_lookup: dict[str, str] = {
            p["source_field"]: p["proposed_target"]
            for p in proposals
            if p["proposed_target"]
        }

        wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=True)
        total = 0
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            count = await self._process_sheet(
                ws=ws, carrier_id=carrier_id, run_id=run_id,
                mapping_lookup=mapping_lookup, db=db,
            )
            total += count
            logger.debug("ingestion.sheet.processed", sheet=sheet_name, rows=count)
        wb.close()
        return total

    async def _process_sheet(
        self,
        ws: openpyxl.worksheet.worksheet.Worksheet,
        carrier_id: int,
        run_id: int,
        mapping_lookup: dict[str, str],
        db: AsyncSession,
    ) -> int:
        SINGLE_CELL_SKIP = (
            "AUDIT REPORT", "DATE REPORT RUN", "POLICY NUMBER:",
            "POLICY PERIOD:", "CLASSIFICATION DETAIL",
            "BREAKDOWN OF PREMIUM", "PROVIDER(S) SELECTED",
            "POLICY STATUS(ES) SELECTED", "REPORT(S) SUBMITTED",
            "LATE MISSING PAYROLL",
        )
        header_row_idx: Optional[int] = None
        header_vals: list[str] = []
        all_rows_ws = list(ws.iter_rows(min_row=1, max_row=min(60, ws.max_row), values_only=True))

        for idx, row in enumerate(all_rows_ws):
            clean = [
                str(v).replace("\n", " ").replace("\r", " ").strip()
                for v in row
                if v is not None and str(v).replace("\n", " ").strip()
            ]
            if len(clean) < 2:
                continue
            joined = " ".join(clean).upper()
            if len(clean) <= 2 and any(kw in joined for kw in SINGLE_CELL_SKIP):
                continue
            if sum(len(v) for v in clean) / len(clean) > 45:
                continue
            if any(not isinstance(v, str) for v in row if v is not None):
                continue
            header_vals = [
                str(v).replace("\n", " ").replace("\r", " ").strip()
                if v is not None else ""
                for v in row
            ]
            header_row_idx = idx + 1
            break

        if not header_vals or header_row_idx is None:
            return 0

        canonical_col_map: dict[str, int] = {}
        for col_idx, header in enumerate(header_vals, start=1):
            if not header:
                continue
            if header in mapping_lookup:
                canonical_col_map[mapping_lookup[header]] = col_idx
            else:
                norm = "".join(c for c in header.lower() if c.isalnum() or c == " ").strip()
                for src_field, canonical in mapping_lookup.items():
                    src_norm = "".join(c for c in src_field.lower() if c.isalnum() or c == " ").strip()
                    if norm == src_norm:
                        canonical_col_map[canonical] = col_idx
                        break

        if not canonical_col_map:
            logger.warning("ingestion.sheet.no_mapped_columns", sheet=ws.title)
            return 0

        logger.info("ingestion.sheet.routing", sheet=ws.title, canonical_cols=list(canonical_col_map.keys()))

        # Route by canonical columns present
        if "wages" in canonical_col_map and "class_code" in canonical_col_map:
            return await self._upsert_payroll_class(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

        if "est_payroll" in canonical_col_map or "actual_payroll_reported" in canonical_col_map:
            return await self._upsert_payroll_policy(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

        if "est_premium_end" in canonical_col_map or "actual_premium" in canonical_col_map:
            return await self._upsert_premium_variance(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

        if "reason_code" in canonical_col_map or "report_date" in canonical_col_map:
            return await self._upsert_zero_payroll(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

        if "expected_period_start" in canonical_col_map or "days_overdue" in canonical_col_map:
            return await self._upsert_missing_payroll(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

        if "policy_number" in canonical_col_map:
            return await self._upsert_policies_only(ws, header_row_idx, canonical_col_map, carrier_id, run_id, db)

        logger.warning("ingestion.sheet.unroutable", sheet=ws.title, cols=list(canonical_col_map.keys()))
        return 0

    # =========================================================================
    # Core helper: get cell value by canonical name
    # =========================================================================

    def _cv(self, row: tuple, cmap: dict[str, int], *names: str) -> object:
        """Returns first non-None value for given canonical column names."""
        for name in names:
            idx = cmap.get(name)
            if idx is not None and idx - 1 < len(row):
                v = row[idx - 1]
                if v is not None:
                    return v
        return None

    # =========================================================================
    # Policy + policyholder upsert (shared by all XLSX upsert methods)
    # =========================================================================

    async def _ensure_policy(
        self,
        row: tuple,
        cmap: dict[str, int],
        carrier_id: int,
        db: AsyncSession,
    ) -> Optional[int]:
        """
        Upserts policyholder + policy from approved canonical columns.
        Returns policy_id or None if policy_number is missing.
        """
        pol_num = _safe_str(self._cv(row, cmap, "policy_number"))
        if not pol_num:
            return None

        insured = _safe_str(self._cv(row, cmap, "insured_name")) or "Unknown"
        fein    = _safe_str(self._cv(row, cmap, "fein"))
        state_raw = _safe_str(self._cv(row, cmap, "state_code"))
        state = (state_raw.split()[0][:2] if state_raw else None)
        eff     = _safe_date(self._cv(row, cmap, "effective_date", "as_of_date"))
        exp     = _safe_date(self._cv(row, cmap, "expiration_date"))

        # Upsert policyholder
        if fein:
            ph = await db.execute(
                text("""
                    INSERT INTO policyholders (carrier_id, name, fein)
                    VALUES (:cid, :name, :fein)
                    ON CONFLICT (carrier_id, fein) DO UPDATE SET name = EXCLUDED.name
                    RETURNING policyholder_id
                """),
                {"cid": carrier_id, "name": insured, "fein": fein},
            )
        else:
            # No FEIN — try to find by name, insert if missing
            ph = await db.execute(
                text("SELECT policyholder_id FROM policyholders WHERE carrier_id=:cid AND name=:name AND fein IS NULL LIMIT 1"),
                {"cid": carrier_id, "name": insured},
            )
            row_ph = ph.fetchone()
            if row_ph is None:
                ph = await db.execute(
                    text("INSERT INTO policyholders (carrier_id, name, fein) VALUES (:cid, :name, NULL) RETURNING policyholder_id"),
                    {"cid": carrier_id, "name": insured},
                )
            else:
                # Return a fake result object with the found id
                ph_id = row_ph[0]
                pol = await db.execute(
                    text("""
                        INSERT INTO policies
                          (carrier_id, policyholder_id, policy_number, state_code,
                           effective_date, expiration_date, policy_status, audit_status)
                        VALUES (:cid, :phid, :pnum, :state, :eff, :exp, 'Active', 'Pending')
                        ON CONFLICT (carrier_id, policy_number) DO UPDATE SET
                          policyholder_id = EXCLUDED.policyholder_id,
                          state_code      = COALESCE(EXCLUDED.state_code, policies.state_code),
                          effective_date  = COALESCE(EXCLUDED.effective_date, policies.effective_date),
                          expiration_date = COALESCE(EXCLUDED.expiration_date, policies.expiration_date)
                        RETURNING policy_id
                    """),
                    {"cid": carrier_id, "phid": ph_id, "pnum": pol_num,
                     "state": state, "eff": eff, "exp": exp},
                )
                r = pol.fetchone()
                return r[0] if r else None

        ph_row = ph.fetchone()
        if ph_row is None:
            return None
        ph_id = ph_row[0]

        pol = await db.execute(
            text("""
                INSERT INTO policies
                  (carrier_id, policyholder_id, policy_number, state_code,
                   effective_date, expiration_date, policy_status, audit_status)
                VALUES (:cid, :phid, :pnum, :state, :eff, :exp, 'Active', 'Pending')
                ON CONFLICT (carrier_id, policy_number) DO UPDATE SET
                  policyholder_id = EXCLUDED.policyholder_id,
                  state_code      = COALESCE(EXCLUDED.state_code, policies.state_code),
                  effective_date  = COALESCE(EXCLUDED.effective_date, policies.effective_date),
                  expiration_date = COALESCE(EXCLUDED.expiration_date, policies.expiration_date)
                RETURNING policy_id
            """),
            {"cid": carrier_id, "phid": ph_id, "pnum": pol_num,
             "state": state, "eff": eff, "exp": exp},
        )
        r = pol.fetchone()
        return r[0] if r else None

    # =========================================================================
    # Resolve class_code_id from public.class_codes (upsert on miss)
    # =========================================================================

    async def _resolve_class_code_id(self, code: str, description: str, db: AsyncSession) -> int:
        """Returns class_code_id from public.class_codes, inserting if absent."""
        result = await db.execute(
            text("SELECT class_code_id FROM public.class_codes WHERE code=:code"),
            {"code": code},
        )
        row = result.fetchone()
        if row:
            return row[0]
        ins = await db.execute(
            text("INSERT INTO public.class_codes (code, description) VALUES (:code, :desc) ON CONFLICT (code) DO UPDATE SET description=COALESCE(EXCLUDED.description, class_codes.description) RETURNING class_code_id"),
            {"code": code, "desc": description or code},
        )
        return ins.scalar_one()

    # =========================================================================
    # Fact table upserts — all use canonical_col_map
    # =========================================================================

    async def _upsert_policies_only(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
        count = 0
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not any(row):
                continue
            pid = await self._ensure_policy(row, cmap, carrier_id, db)
            if pid:
                count += 1
        await db.commit()
        return count

    async def _upsert_premium_variance(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
        count = 0
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not any(row):
                continue
            pid = await self._ensure_policy(row, cmap, carrier_id, db)
            if pid is None:
                continue
            est    = _safe_decimal(self._cv(row, cmap, "est_premium_end"))
            actual = _safe_decimal(self._cv(row, cmap, "actual_premium", "premium_written"))
            as_of  = _safe_date(self._cv(row, cmap, "as_of_date", "effective_date")) or date.today()
            if est is None or actual is None:
                continue
            await db.execute(
                text("""
                    INSERT INTO premium_variance
                      (policy_id, carrier_id, ingestion_run_id, as_of_date, est_premium_end, actual_premium)
                    VALUES (:pid, :cid, :rid, :dt, :est, :actual)
                    ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
                      est_premium_end = EXCLUDED.est_premium_end,
                      actual_premium  = EXCLUDED.actual_premium
                """),
                {"pid": pid, "cid": carrier_id, "rid": run_id,
                 "dt": as_of, "est": float(est), "actual": float(actual)},
            )
            count += 1
        await db.commit()
        return count

    # async def _upsert_payroll_policy(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
    #     count = 0
    #     for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
    #         if not any(row):
    #             continue
    #         pid = await self._ensure_policy(row, cmap, carrier_id, db)
    #         if pid is None:
    #             continue
    #         est      = _safe_decimal(self._cv(row, cmap, "est_payroll"))
    #         reported = _safe_decimal(self._cv(row, cmap, "actual_payroll_reported"))
    #         classfd  = _safe_decimal(self._cv(row, cmap, "actual_payroll_classified")) or Decimal("0")
    #         as_of    = _safe_date(self._cv(row, cmap, "as_of_date", "effective_date")) or date.today()
    #         if est is None and reported is None:
    #             continue
    #         # reported_pct and classified_pct are nullable — compute safely
    #         rep_pct = float(reported / est * 100) if est and reported and est != 0 else None
    #         cls_pct = float(classfd / est * 100)  if est and classfd and est != 0 else None
    #         await db.execute(
    #             text("""
    #                 INSERT INTO payroll_variance_policy
    #                   (policy_id, carrier_id, ingestion_run_id, as_of_date,
    #                    est_payroll, actual_payroll_reported, reported_pct,
    #                    actual_payroll_classified, classified_pct)
    #                 VALUES (:pid, :cid, :rid, :dt, :est, :rep, :rpct, :cls, :cpct)
    #                 ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
    #                   est_payroll              = EXCLUDED.est_payroll,
    #                   actual_payroll_reported  = EXCLUDED.actual_payroll_reported,
    #                   actual_payroll_classified= EXCLUDED.actual_payroll_classified
    #             """),
    #             {"pid": pid, "cid": carrier_id, "rid": run_id, "dt": as_of,
    #              "est":  float(est)      if est      is not None else None,
    #              "rep":  float(reported) if reported is not None else None,
    #              "rpct": rep_pct,
    #              "cls":  float(classfd),
    #              "cpct": cls_pct},
    #         )
    #         count += 1
    #     await db.commit()
    #     return count

    async def _upsert_payroll_policy(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
        count = 0
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not any(row):
                continue
            pid = await self._ensure_policy(row, cmap, carrier_id, db)
            if pid is None:
                continue
            # Default to 0 instead of None — actual_payroll_reported is NOT NULL in schema.
            est      = _safe_decimal(self._cv(row, cmap, "est_payroll"))               or Decimal("0")
            reported = _safe_decimal(self._cv(row, cmap, "actual_payroll_reported"))   or Decimal("0")
            classfd  = _safe_decimal(self._cv(row, cmap, "actual_payroll_classified")) or Decimal("0")
            as_of    = _safe_date(self._cv(row, cmap, "as_of_date", "effective_date")) or date.today()
            if est == Decimal("0") and reported == Decimal("0"):
                continue
            await db.execute(
                text("""
                    INSERT INTO payroll_variance_policy
                      (policy_id, carrier_id, ingestion_run_id, as_of_date,
                       est_payroll, actual_payroll_reported,
                       actual_payroll_classified)
                    VALUES (:pid, :cid, :rid, :dt, :est, :rep, :cls)
                    ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
                      est_payroll               = EXCLUDED.est_payroll,
                      actual_payroll_reported   = EXCLUDED.actual_payroll_reported,
                      actual_payroll_classified = EXCLUDED.actual_payroll_classified
                """),
                {"pid": pid, "cid": carrier_id, "rid": run_id, "dt": as_of,
                 "est": float(est), "rep": float(reported), "cls": float(classfd)},
            )
            count += 1
        await db.commit()
        return count

    async def _upsert_payroll_class(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
        """
        Per-employee payroll detail (Bakeland_LLC_2026_2_24.xlsx style).
        Aggregates wages per (policy_id, state_code, class_code) then upserts.
        payroll_variance_class uses class_code_id FK to public.class_codes.
        """
        # Build a direct header→index map from the worksheet itself.
        # This is used to find earned_premium regardless of whether the
        # mapping proposal included it — the payroll file format is fixed.
        header_vals = [
            str(v).replace("\n", " ").strip().lower() if v is not None else ""
            for v in next(ws.iter_rows(min_row=header_row, max_row=header_row, values_only=True), [])
        ]
        # Direct column index (1-based) for earned_premium
        # Payroll file column: "Earned Prem." → norm = "earned prem"
        earned_prem_col: Optional[int] = None
        for ci, h in enumerate(header_vals, start=1):
            norm = "".join(c for c in h if c.isalnum() or c == " ").strip()
            if norm in ("earned prem", "earned premium", "earnedprem"):
                earned_prem_col = ci
                break
        # If not in cmap already, add it
        if earned_prem_col and "earned_premium" not in cmap:
            cmap = {**cmap, "earned_premium": earned_prem_col}

        # Aggregate: (policy_id, state_code, class_code_str) → totals
        # earned_premium is read from the "Earned Prem." column in the payroll file.
        # It is used to UPDATE premium_variance.actual_premium after all rows are written.
        agg: dict[tuple, dict] = defaultdict(lambda: {
            "wages": Decimal("0"), "exposure": Decimal("0"),
            "earned_premium": Decimal("0"),
            "as_of": None, "description": "",
        })
        policy_cache: dict[str, Optional[int]] = {}

        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not any(row):
                continue

            pol_idx = cmap.get("policy_number")
            cls_idx = cmap.get("class_code")
            if not pol_idx or not cls_idx:
                continue

            pol_num = _safe_str(row[pol_idx - 1] if pol_idx - 1 < len(row) else None)
            cls_raw = _safe_str(row[cls_idx - 1] if cls_idx - 1 < len(row) else None)
            if not pol_num or not cls_raw:
                continue
            cls_str = cls_raw.split()[0].strip() if " " in cls_raw else cls_raw

            if pol_num not in policy_cache:
                policy_cache[pol_num] = await self._ensure_policy(row, cmap, carrier_id, db)

            pid = policy_cache[pol_num]
            if pid is None:
                continue

            state = _safe_str(self._cv(row, cmap, "state_code"), max_len=2) or "XX"
            wages = _safe_decimal(self._cv(row, cmap, "wages")) or Decimal("0")
            # exposure = wages when not separately mapped
            exposure = _safe_decimal(self._cv(row, cmap, "exposure")) or wages
            # earned_premium from "Earned Prem." column — the actual premium this period
            earned_premium = _safe_decimal(self._cv(row, cmap, "earned_premium")) or Decimal("0")
            as_of = _safe_date(self._cv(row, cmap, "as_of_date", "report_date"))

            key = (pid, state, cls_str)
            agg[key]["wages"]          += wages
            agg[key]["exposure"]       += exposure
            agg[key]["earned_premium"] += earned_premium
            if as_of and not agg[key]["as_of"]:
                agg[key]["as_of"] = as_of

        count = 0
        # Track earned_premium per policy for premium_variance update
        policy_earned_premium: dict[int, Decimal] = {}

        for (pid, state, cls_str), totals in agg.items():
            class_code_id = await self._resolve_class_code_id(cls_str, cls_str, db)
            as_of = totals["as_of"] or date.today()
            await db.execute(
                text("""
                    INSERT INTO payroll_variance_class
                      (policy_id, carrier_id, ingestion_run_id, class_code_id,
                       state_code, as_of_date, est_payroll, actual_reported, actual_classified)
                    VALUES (:pid, :cid, :rid, :ccid, :state, :dt,
                            0, :wages, :exposure)
                    ON CONFLICT (policy_id, state_code, class_code_id, ingestion_run_id)
                    DO UPDATE SET
                      actual_reported    = payroll_variance_class.actual_reported    + EXCLUDED.actual_reported,
                      actual_classified  = payroll_variance_class.actual_classified  + EXCLUDED.actual_classified
                """),
                {"pid": pid, "cid": carrier_id, "rid": run_id, "ccid": class_code_id,
                 "state": state, "dt": as_of,
                 "wages": float(totals["wages"]), "exposure": float(totals["exposure"])},
            )
            # Accumulate earned_premium per policy
            if pid not in policy_earned_premium:
                policy_earned_premium[pid] = Decimal("0")
            policy_earned_premium[pid] += totals["earned_premium"]
            count += 1

        await db.commit()

        # ── Update premium_variance.actual_premium with earned_premium from payroll file ──
        # Reference: premium_agent.py → earned_premium = sum(r["earned_premium"] for r in matching)
        # Reference: mock_data_api.py → "Earned Prem." column from payroll file
        #
        # The audit report sets actual_premium = est_ytd_premium (same as est).
        # When the payroll file is uploaded (same run or different run), we UPDATE
        # actual_premium with the real earned_premium from the payroll rows.
        # This creates the variance: actual_premium ≠ est_premium_end.
        for pid, total_earned in policy_earned_premium.items():
            if total_earned <= 0:
                continue

            # Check if a premium_variance row already exists (written by audit report)
            existing = await db.execute(
                text("SELECT pv_id, est_premium_end FROM premium_variance WHERE policy_id = :pid ORDER BY ingestion_run_id DESC LIMIT 1"),
                {"pid": pid},
            )
            existing_row = existing.fetchone()

            if existing_row:
                # Audit report already wrote est_premium_end — just update actual_premium
                await db.execute(
                    text("""
                        UPDATE premium_variance
                        SET actual_premium = :earned
                        WHERE pv_id = :pv_id
                    """),
                    {"earned": float(total_earned), "pv_id": existing_row[0]},
                )
                logger.info(
                    "ingestion.payroll_class.actual_premium_updated",
                    policy_id=pid, pv_id=existing_row[0],
                    earned_premium=float(total_earned),
                    est_premium=float(existing_row[1]) if existing_row[1] else None,
                )
            else:
                # Payroll file arrived before audit report — write actual_premium now.
                # est_premium_end will be filled in when audit report is uploaded.
                await db.execute(
                    text("""
                        INSERT INTO premium_variance
                          (policy_id, carrier_id, ingestion_run_id, as_of_date,
                           est_premium_end, actual_premium)
                        VALUES (:pid, :cid, :rid, now(), 0, :earned)
                        ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
                          actual_premium = EXCLUDED.actual_premium
                    """),
                    {
                        "pid": pid, "cid": carrier_id, "rid": run_id,
                        "earned": float(total_earned),
                    },
                )
                logger.info(
                    "ingestion.payroll_class.actual_premium_inserted",
                    policy_id=pid, earned_premium=float(total_earned),
                )
        await db.commit()
        return count

    async def _upsert_zero_payroll(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
        count = 0
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not any(row):
                continue
            pid = await self._ensure_policy(row, cmap, carrier_id, db)
            if pid is None:
                continue
            pol_num  = _safe_str(self._cv(row, cmap, "policy_number"))
            insured  = _safe_str(self._cv(row, cmap, "insured_name"))
            state    = _safe_str(self._cv(row, cmap, "state_code"), max_len=2)
            rep_date = _safe_date(self._cv(row, cmap, "report_date", "as_of_date"))
            freq     = _safe_str(self._cv(row, cmap, "payment_frequency"))
            await db.execute(
                text("""
                    INSERT INTO zero_payroll
                      (policy_id, carrier_id, ingestion_run_id,
                       policyholder_name, policy_number, state_code,
                       report_date, payroll_frequency)
                    VALUES (:pid, :cid, :rid, :name, :pnum, :state, :dt, :freq)
                """),
                {"pid": pid, "cid": carrier_id, "rid": run_id,
                 "name": insured, "pnum": pol_num, "state": state,
                 "dt": rep_date, "freq": freq},
            )
            count += 1
        await db.commit()
        return count

    async def _upsert_missing_payroll(self, ws, header_row, cmap, carrier_id, run_id, db) -> int:
        count = 0
        for row in ws.iter_rows(min_row=header_row + 1, values_only=True):
            if not any(row):
                continue
            pid = await self._ensure_policy(row, cmap, carrier_id, db)
            if pid is None:
                continue
            pol_num = _safe_str(self._cv(row, cmap, "policy_number"))
            insured = _safe_str(self._cv(row, cmap, "insured_name"))
            state   = _safe_str(self._cv(row, cmap, "state_code"), max_len=2)
            p_start = _safe_date(self._cv(row, cmap, "expected_period_start"))
            p_end   = _safe_date(self._cv(row, cmap, "expected_period_end"))
            days    = self._cv(row, cmap, "days_overdue")
            freq    = _safe_str(self._cv(row, cmap, "payment_frequency"))
            await db.execute(
                text("""
                    INSERT INTO missing_payroll
                      (policy_id, carrier_id, ingestion_run_id,
                       policyholder_name, policy_number, state_code,
                       period_start, period_end, days_since_last_run, payroll_frequency)
                    VALUES (:pid, :cid, :rid, :name, :pnum, :state, :ps, :pe, :days, :freq)
                """),
                {"pid": pid, "cid": carrier_id, "rid": run_id,
                 "name": insured, "pnum": pol_num, "state": state,
                 "ps": p_start, "pe": p_end,
                 "days": int(days) if days is not None else None,
                 "freq": freq},
            )
            count += 1
        await db.commit()
        return count

    # =========================================================================
    # XML parsing (PPlus format)
    # =========================================================================

    async def _parse_and_upsert_xml(
        self,
        carrier_id: int,
        run_id: int,
        file_bytes: bytes,
        db: AsyncSession,
    ) -> int:
        try:
            root = ET.fromstring(file_bytes)
        except ET.ParseError as exc:
            raise ValueError(f"XML parse error: {exc}") from exc

        policy_elem = root.find("Policy")
        if policy_elem is None:
            raise ValueError("XML has no <Policy> element")

        pd = policy_elem.find("PolicyData")
        if pd is None:
            raise ValueError("XML has no <PolicyData> element")

        def _x(tag: str) -> Optional[str]:
            n = pd.find(tag)
            return n.text.strip() if n is not None and n.text else None

        policy_number = _x("PolicyNumber")
        if not policy_number:
            raise ValueError("XML PolicyData has no PolicyNumber")

        insured_name = _x("InsuredName") or "Unknown"
        fein         = _x("Fein")
        state_code   = _x("GoverningState") or (_x("Addr/StateProvCd"))
        eff_date     = _safe_date(_x("EffectiveDate"))
        exp_date     = _safe_date(_x("ExpirationDate"))
        premium      = _safe_decimal(_x("Premium"))

        # Upsert policyholder
        if fein:
            ph = await db.execute(
                text("""
                    INSERT INTO policyholders (carrier_id, name, fein)
                    VALUES (:cid, :name, :fein)
                    ON CONFLICT (carrier_id, fein) DO UPDATE SET name = EXCLUDED.name
                    RETURNING policyholder_id
                """),
                {"cid": carrier_id, "name": insured_name, "fein": fein},
            )
        else:
            ph = await db.execute(
                text("INSERT INTO policyholders (carrier_id, name, fein) VALUES (:cid, :name, NULL) ON CONFLICT DO NOTHING RETURNING policyholder_id"),
                {"cid": carrier_id, "name": insured_name},
            )
            if not ph.rowcount:
                ph = await db.execute(
                    text("SELECT policyholder_id FROM policyholders WHERE carrier_id=:cid AND name=:name LIMIT 1"),
                    {"cid": carrier_id, "name": insured_name},
                )

        ph_row = ph.fetchone()
        if ph_row is None:
            raise ValueError(f"Could not upsert policyholder for {insured_name}")
        ph_id = ph_row[0]

        # Upsert policy
        pol = await db.execute(
            text("""
                INSERT INTO policies
                  (carrier_id, policyholder_id, policy_number, state_code,
                   effective_date, expiration_date, premium_written,
                   policy_status, audit_status)
                VALUES (:cid, :phid, :pnum, :state, :eff, :exp, :prem, 'Active', 'Pending')
                ON CONFLICT (carrier_id, policy_number) DO UPDATE SET
                  policyholder_id = EXCLUDED.policyholder_id,
                  state_code      = COALESCE(EXCLUDED.state_code,      policies.state_code),
                  effective_date  = COALESCE(EXCLUDED.effective_date,  policies.effective_date),
                  expiration_date = COALESCE(EXCLUDED.expiration_date, policies.expiration_date),
                  premium_written = COALESCE(EXCLUDED.premium_written, policies.premium_written)
                RETURNING policy_id
            """),
            {"cid": carrier_id, "phid": ph_id, "pnum": policy_number,
             "state": state_code, "eff": eff_date, "exp": exp_date,
             "prem": float(premium) if premium else None},
        )
        pol_row = pol.fetchone()
        if pol_row is None:
            raise ValueError(f"Could not upsert policy {policy_number}")
        policy_id = pol_row[0]

        await db.commit()
        logger.info("ingestion.xml.policy_upserted", policy_number=policy_number, policy_id=policy_id)

        # Upsert payroll_variance_class from each Rate entry
        rows_inserted = 0
        for rate in root.findall(".//Rate"):
            cls_str  = (rate.findtext("ClassCode") or "").strip()
            desc     = (rate.findtext("Description") or cls_str).strip()
            exposure = _safe_decimal(rate.findtext("Exposure"))
            state    = (policy_elem.findtext(".//ComplexRateState/State") or state_code or "XX")[:2]
            rate_eff = _safe_date(rate.findtext("EffectiveDate")) or eff_date or date.today()

            if not cls_str or exposure is None:
                continue

            class_code_id = await self._resolve_class_code_id(cls_str, desc, db)

            await db.execute(
                text("""
                    INSERT INTO payroll_variance_class
                      (policy_id, carrier_id, ingestion_run_id, class_code_id,
                       state_code, as_of_date, est_payroll, actual_reported, actual_classified)
                    VALUES (:pid, :cid, :rid, :ccid, :state, :dt, :exp, 0, 0)
                    ON CONFLICT (policy_id, state_code, class_code_id, ingestion_run_id)
                    DO UPDATE SET
                      est_payroll = payroll_variance_class.est_payroll + EXCLUDED.est_payroll
                """),
                {"pid": policy_id, "cid": carrier_id, "rid": run_id,
                 "ccid": class_code_id, "state": state, "dt": rate_eff,
                 "exp": float(exposure)},
            )
            rows_inserted += 1

        # Upsert premium_variance from total premium
        if premium is not None:
            await db.execute(
                text("""
                    INSERT INTO premium_variance
                      (policy_id, carrier_id, ingestion_run_id, as_of_date,
                       est_premium_end, actual_premium)
                    VALUES (:pid, :cid, :rid, :dt, :est, :actual)
                    ON CONFLICT (policy_id, ingestion_run_id) DO UPDATE SET
                      est_premium_end = EXCLUDED.est_premium_end,
                      actual_premium  = EXCLUDED.actual_premium
                """),
                {"pid": policy_id, "cid": carrier_id, "rid": run_id,
                 "dt": eff_date or date.today(),
                 "est": float(premium), "actual": float(premium)},
            )

        await db.commit()
        logger.info("ingestion.xml.complete", run_id=run_id, policy_number=policy_number, rows=rows_inserted)
        return max(rows_inserted, 1)

    # =========================================================================
    # Calc engine trigger
    # =========================================================================

    async def _trigger_calc_for_run(
        self, schema_name: str, carrier_id: int, run_id: int, db: AsyncSession
    ) -> None:
        result = await db.execute(
            text("SELECT DISTINCT policy_id FROM premium_variance WHERE ingestion_run_id=:rid AND carrier_id=:cid"),
            {"rid": run_id, "cid": carrier_id},
        )
        policy_ids = [r[0] for r in result.fetchall()]
        calc = AuditCalculationService()
        for policy_id in policy_ids:
            try:
                await calc.run(schema_name, carrier_id, policy_id, run_id, db)
            except Exception as exc:
                logger.error("ingestion.calc.failed", policy_id=policy_id, run_id=run_id, error=str(exc))