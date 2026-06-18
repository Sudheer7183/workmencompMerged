    -- =============================================================================
    -- Hotfix SQL v2 — Dashboard KPI zeros fix + tenant_registry fix
    -- =============================================================================
    -- 
    -- ROOT CAUSE (Bug 1 — Dashboard KPIs $0):
    --   When two files are ingested per policy (audit report XLSX + payroll XLSX),
    --   each file creates its own ingestion_run (run A, run B).
    --
    --   Audit report run (A):
    --     → INSERTs premium_variance row with ingestion_run_id = A
    --     → ingestion_runs[A].status = 'complete'
    --
    --   Payroll run (B):
    --     → Finds existing premium_variance row, UPDATEs actual_premium only
    --     → premium_variance row still has ingestion_run_id = A
    --     → ingestion_runs[B].status = 'complete'
    --
    --   v_dashboard_summary:
    --     → MAX(complete run) = B
    --     → JOIN on pv.ingestion_run_id = B → no match → $0
    --
    -- HOW TO APPLY:
    --   psql -U auditplatform -d auditplatform -f hotfix_0010_v2.sql
    --
    --   Replace 'tenant_demo' with your actual schema name throughout.
    -- =============================================================================

    -- ── Step 1: Recreate v_dashboard_summary with run fallback ────────────────────
    CREATE OR REPLACE VIEW tenant_demo.v_dashboard_summary AS
    SELECT
        p.carrier_id,
        COUNT(DISTINCT p.policy_id)                                            AS total_policies,
        COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Active')  AS active_policies,
        COUNT(DISTINCT p.policy_id) FILTER (WHERE p.policy_status = 'Cancelled') AS cancelled_policies,
        COALESCE(SUM(p.premium_written), 0)                                    AS total_book_premium,
        COALESCE(SUM(pv.est_premium_end), 0)                                   AS total_est_earned_premium,
        COALESCE(SUM(pv.actual_premium), 0)                                    AS total_actual_earned_premium,
        COALESCE(SUM(pv.variance_amount), 0)                                   AS total_variance_amount,
        COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'High')       AS risk_high_count,
        COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Medium')     AS risk_medium_count,
        COUNT(DISTINCT p.policy_id) FILTER (WHERE p.risk_level = 'Low')        AS risk_low_count
    FROM tenant_demo.policies p
    LEFT JOIN tenant_demo.premium_variance pv
        ON pv.policy_id = p.policy_id
        AND pv.ingestion_run_id = (
            SELECT COALESCE(
                (SELECT MAX(ir_c.run_id)
                FROM tenant_demo.ingestion_runs ir_c
                WHERE ir_c.carrier_id = p.carrier_id
                AND ir_c.status = 'complete'),
                (SELECT MAX(ir_a.run_id)
                FROM tenant_demo.ingestion_runs ir_a
                WHERE ir_a.carrier_id = p.carrier_id)
            )
        )
    WHERE p.deleted_at IS NULL
    GROUP BY p.carrier_id;


    -- ── Step 2: Backfill stale ingestion_run_id on premium_variance rows ──────────
    --
    -- For each premium_variance row whose ingestion_run_id does not match the latest
    -- complete run for its carrier, advance it to the latest complete run.
    --
    -- Safety: we only update when no row already exists at the target run_id
    -- for that policy (avoids violating the UNIQUE(policy_id, ingestion_run_id) constraint).
    -- Duplicate rows (both old and new run_id exist) are removed first by keeping
    -- only the row with the highest run_id.

    -- 2a. Delete duplicate lower-run_id rows when a higher-run_id row already exists
    --     for the same policy (keeps the most recent data, removes the stale duplicate).
    DELETE FROM tenant_demo.premium_variance pv_old
    WHERE EXISTS (
        SELECT 1
        FROM tenant_demo.premium_variance pv_new
        WHERE pv_new.policy_id = pv_old.policy_id
        AND pv_new.ingestion_run_id > pv_old.ingestion_run_id
    );

    -- 2b. Advance remaining stale rows to the latest complete run.
    --     After step 2a there is at most one row per policy_id, so no unique constraint risk.
    UPDATE tenant_demo.premium_variance pv
    SET ingestion_run_id = (
        SELECT COALESCE(
            (SELECT MAX(ir_c.run_id)
            FROM tenant_demo.ingestion_runs ir_c
            WHERE ir_c.carrier_id = pv.carrier_id
            AND ir_c.status = 'complete'),
            (SELECT MAX(ir_a.run_id)
            FROM tenant_demo.ingestion_runs ir_a
            WHERE ir_a.carrier_id = pv.carrier_id)
        )
    )
    WHERE pv.ingestion_run_id NOT IN (
        SELECT run_id
        FROM tenant_demo.ingestion_runs
        WHERE carrier_id = pv.carrier_id
        AND status = 'complete'
    );


    -- ── Step 3: Create public.tenant_registry compat view ────────────────────────
    -- Fixes report generation error:
    --   UndefinedTableError: relation "public.tenant_registry" does not exist
    -- The actual table is public.tenants. This view aliases it with the old name.
    CREATE OR REPLACE VIEW public.tenant_registry AS
    SELECT
        slug,
        schema_name,
        name   AS tenant_name,
        tenant_type,
        status,
        config,
        created_at,
        deleted_at
    FROM public.tenants;


    -- ── Verify: quick sanity check ────────────────────────────────────────────────
    -- Run this SELECT after applying the hotfix to confirm data is now visible:
    --
    --   SELECT carrier_id,
    --          total_book_premium,
    --          total_est_earned_premium,
    --          total_actual_earned_premium,
    --          total_variance_amount
    --   FROM tenant_demo.v_dashboard_summary;
    --
    -- Expected: total_est_earned_premium and total_actual_earned_premium should now
    -- show non-zero values matching what the policy detail pages display.
