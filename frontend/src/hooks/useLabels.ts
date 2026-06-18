// /**
//  * useLabels — UI string registry
//  *
//  * V9 S23 — strict conformance implementation.
//  *
//  * All user-visible strings are accessed through this hook.
//  * No hardcoded strings in component JSX.
//  *
//  * Usage per V9 S23.2:
//  *   const label = useLabels("dashboard");
//  *   <span>{label("kpi.book_premium", "Total Book Premium")}</span>
//  *
//  * Resolution chain (V9 S23.1):
//  *   1. carrier_ui_labels from API (carrier-specific overrides)
//  *   2. DEFAULT_LABELS registry (platform defaults)
//  *   3. fallback argument (development safety net)
//  *
//  * Redis cache key: {schema}:labels:{carrier_id}:{screen_key}  TTL 5 min
//  */

// import axios from "axios";
// import { useQuery } from "@tanstack/react-query";
// import { useTenantCarrier } from "@/context/TenantCarrierContext";

// // ---------------------------------------------------------------------------
// // Screen key type — all valid screen namespaces per V9 S23.3
// // ---------------------------------------------------------------------------

// export type ScreenKey =
//   | "audit_runner"
//   | "calc_engine"
//   | "carrier_config"
//   | "dashboard"
//   | "field_mapping"
//   | "ingestion"
//   | "onboarding"
//   | "org_settings"
//   | "platform_admin"
//   | "policies"
//   | "policy_detail"
//   | "shared"
//   | "submission"
//   | "users"
//   | "zero_payroll"
//   ;

// // ---------------------------------------------------------------------------
// // DEFAULT_LABELS — platform defaults, grouped by screen_key per V9 S23.3.
// // Values are the in-code fallback; all must be non-empty strings.
// // MUST NOT be modified without updating the V9 S23.3 catalogue.
// // ---------------------------------------------------------------------------

// export const DEFAULT_LABELS: Record<ScreenKey, Record<string, string>> = {
//   // ── audit_runner ────────────────────────────────────────────────────────────
//   "audit_runner": {
//     "btn.upload_and_map": "Upload & Map Fields",
//     "btn.uploading": "Uploading…",
//     "subtitle": "Upload a carrier data file to begin the audit ingestion pipeline. The system will auto-map fields and require your approval before loading data.",
//     "title": "Audit Runner",
//     "upload.dropzone_aria": "Click or drag to select XLSX file",
//     "upload.dropzone_hint": "XLSX files only (CSV and XML coming in Phase 4)",
//     "upload.dropzone_text": "Click to select or drag and drop",
//     "upload.error": "Upload failed. Please try again.",
//     "upload.format_coming_phase4": "Coming in Phase 4",
//     "upload.no_file": "Please select a file to upload.",
//     "upload.xlsx_only": "Please upload an XLSX file.",
//   },
//   // ── calc_engine ─────────────────────────────────────────────────────────────
//   "calc_engine": {
//     "btn.ai_suggest": "AI Suggest",
//     "btn.approve_activate": "Approve & Activate",
//     "btn.cancel": "Cancel",
//     "btn.deactivate": "Deactivate",
//     "btn.edit": "Edit",
//     "btn.history": "History",
//     "btn.revert_draft": "Revert to Draft",
//     "btn.save": "Save",
//     "btn.submit_review": "Submit for Review",
//     "btn.test_expression": "Test",
//     "col.actions": "Actions",
//     "col.expression": "Expression",
//     "col.rule_key": "Rule Key",
//     "col.rule_status": "Status",
//     "col.rule_type": "Type",
//     "rule.ai_suggest_loading": "Generating suggestion…",
//     "rule.expression_placeholder": "Enter expression (e.g. abs(variance_pct) > 30)",
//     "rule.history_title": "Rule Change History",
//     "rule.locked_tooltip": "This rule is locked and cannot be edited.",
//     "rule.test_result_label": "Test result:",
//     "rules.subtitle": "LOCKED rules use built-in Python logic. EDITABLE rules use configurable expressions evaluated at run time.",
//     "rules.title": "Calculation Rules",
//     "toggle.label": "Calculation Engine",
//     "toggle.off": "OFF",
//     "toggle.off_warning": "Engine is OFF. All engine-derived fields (Variance %, Risk Level) will show N/A on the dashboard.",
//     "toggle.on": "ON",
//     "toggle.saving": "Saving…",
//   },
//   // ── carrier_config ──────────────────────────────────────────────────────────
//   "carrier_config": {
//     "coming.phase4": "Coming in Phase 4",
//     "coming.phase5": "Coming in Phase 5",
//     "coming.phase6": "Coming in Phase 6",
//     "tab.calc_engine": "Calculation Engine",
//     "tab.field_map": "Field Mapping",
//     "tab.labels": "Labels & Display",
//     "tab.report": "Report Template",
//     "tab.theme": "Theme",
//     "title": "Carrier Configuration",
//   },
//   // ── dashboard ───────────────────────────────────────────────────────────────
//   "dashboard": {
//     "chart.active_policies": "Active",
//     "chart.cancelled_policies": "Cancelled",
//     "chart.risk_dist": "Risk Distribution",
//     "chart.state_risk": "Policies by State & Risk",
//     "chart.status_dist": "Policy Status",
//     "kpi.actual_earned": "Actual Earned Premium",
//     "kpi.book_premium": "Total Book Premium",
//     "kpi.est_earned": "Est. Earned Premium",
//     "kpi.variance": "Total Variance",
//     "risk.high": "High",
//     "risk.low": "Low",
//     "risk.medium": "Medium",
//     "risk.unassigned": "Unassigned",
//     "subtitle": "Workers Compensation Premium Audit Overview",
//     "target.over": "Policies Above Threshold",
//     "target.title": "Policies Above 30% Variance Threshold",
//     "target.total_above": "Total Variance Above Threshold",
//     "title": "Audit Dashboard",
//   },
//   // ── field_mapping ───────────────────────────────────────────────────────────
//   "field_mapping": {
//     "btn.approve_mapping": "Approve Mapping",
//     "btn.approving": "Approving…",
//     "btn.back_to_upload": "Back to Upload",
//     "btn.reject_mapping": "Reject & Start Over",
//     "col.exclude": "Exclude",
//     "col.proposed_target": "Target Column",
//     "col.source_field": "Source Field",
//     "col.source_sample": "Sample Value",
//     "col.transform": "Transform",
//     "confidence.high": "HIGH",
//     "confidence.medium_low": "MED/LOW",
//     "confidence.unmatched": "UNMATCHED",
//     "fields": "fields",
//     "mapping.admin_only": "Mapping approval requires Tenant Administrator access.",
//     "mapping.approve_disabled_tooltip": "Assign or exclude all UNMATCHED fields before approving.",
//     "mapping.load_error": "Failed to load field mapping.",
//     "mapping.session_missing": "No mapping session found. Please re-upload the file.",
//     "mapping.unassigned": "— Unassigned —",
//     "subtitle": "Review the auto-mapped field proposals before approving ingestion. Adjust any LOW or UNMATCHED fields.",
//     "title": "Field Mapping Review",
//   },
//   // ── ingestion ───────────────────────────────────────────────────────────────
//   "ingestion": {
//     "btn.run_calc_engine": "Run Calculation Engine",
//     "btn.try_again": "Try Again",
//     "progress.complete": "Ingestion complete.",
//     "progress.failed": "Ingestion failed.",
//     "progress.no_run_id": "No run ID found. Please start a new upload.",
//     "progress.partial": "Ingestion partially completed.",
//     "progress.poll_error": "Could not reach server:",
//     "progress.processing": "Processing data — this may take a moment…",
//     "progress.rows_loaded": "Rows loaded:",
//     "progress.rows_skipped": "Skipped:",
//     "progress.subtitle": "Run",
//     "progress.title": "Ingestion Progress",
//     "progress.waiting": "Waiting for ingestion to start…",
//   },
//   // ── onboarding ──────────────────────────────────────────────────────────────
//   "onboarding": {
//     "btn.continue": "Continue",
//     "btn.finish": "Go to Dashboard",
//     "btn.prev": "Previous",
//     "carrier.config_status": "Configuration Status",
//     "carrier.not_configured": "Not configured",
//     "screen.s1_title": "Tell us about your organisation",
//     "screen.s2_title": "Add your contact details",
//     "screen.s3_title": "Customise your branding",
//     "screen.s4_title": "Your assigned carriers",
//     "screen.s5_complete_msg": "Your organisation is configured. You can update these settings anytime under Organisation Settings.",
//     "screen.s5_title": "You're all set!",
//     "step.1": "Organisation Profile",
//     "step.2": "Contacts",
//     "step.3": "Branding",
//     "step.4": "Carrier Overview",
//     "step.5": "Complete",
//     "title": "Welcome — Let's set up your organisation",
//   },
//   // ── org_settings ────────────────────────────────────────────────────────────
//   "org_settings": {
//     "branding.brand_color": "Brand Colour",
//     "branding.brand_color_hint": "6-character hex value (e.g. 4ade80)",
//     "branding.drag_drop": "Drag and drop a file, or click to browse",
//     "branding.logo": "Organisation Logo",
//     "branding.logo_hint": "PNG, JPG, or SVG · Max 5 MB",
//     "branding.upload_btn": "Upload Logo",
//     "btn.save": "Save Changes",
//     "contact.primary": "Primary Contact",
//     "contact.secondary": "Secondary Contact",
//     "field.address_line1": "Address Line 1",
//     "field.address_line2": "Address Line 2",
//     "field.city": "City",
//     "field.contact_email": "Contact Email",
//     "field.contact_name": "Contact Name",
//     "field.contact_phone": "Contact Phone",
//     "field.display_name": "Display Name",
//     "field.legal_name": "Legal Name",
//     "field.state": "State",
//     "field.zip": "ZIP Code",
//     "msg.save_success": "Changes saved successfully.",
//     "tab.branding": "Branding",
//     "tab.contacts": "Contacts",
//     "tab.profile": "Profile",
//     "carriers.add_hint": "Adding a carrier seeds default calculation rules and configuration. Rules can be customised from the Carrier Configuration Hub.",
//    "carriers.create_title": "Create a New Carrier",
//    "carriers.create_hint": "Don't see the carrier you need? Create a new one and it will be assigned to your organisation immediately.",
//    "carriers.create_name_label": "Carrier Name",
//    "carriers.create_name_placeholder": "e.g. Acme Insurance",
//    "carriers.create_slug_label": "Identifier (slug)",
//    "carriers.create_slug_placeholder": "e.g. acme-insurance",
//    "carriers.create_slug_hint": "Lowercase letters, numbers, and hyphens only. Cannot be changed later.",
//    "carriers.btn.create": "+ New Carrier",
//    "carriers.btn.create_confirm": "Create & Assign",
//    "carriers.btn.creating": "Creating…",
//      "carriers.add_title": "Add a Carrier",
//      "carriers.all_assigned": "All available platform carriers are already assigned to your organisation.",
//      "carriers.assigned_title": "Assigned Carriers",
//      "carriers.btn.add": "Add Carrier",
//      "carriers.btn.adding": "Adding…",
//      "carriers.btn.cancel": "Cancel",
//      "carriers.btn.confirm": "Confirm",
//      "carriers.btn.remove": "Remove",
//      "carriers.col.actions": "Actions",
//      "carriers.col.name": "Carrier Name",
//      "carriers.col.slug": "Identifier",
//      "carriers.confirm_remove": "Remove this carrier?",
//      "carriers.none_assigned": "No carriers assigned yet. Use the section below to add your first carrier.",
//      "carriers.select_label": "Select carrier to add",
//      "carriers.select_placeholder": "— Select a carrier —",
//      "title": "Organization Settings",
//   },
//   // ── platform_admin ──────────────────────────────────────────────────────────
//   "platform_admin": {
//     "btn.activate": "Activate",
//     "btn.back": "Back",
//     "btn.new_carrier": "Add Carrier",
//     "btn.new_tenant": "New Tenant",
//     "btn.next": "Next",
//     "btn.save_draft": "Save as Draft",
//     "carriers.title": "Carriers",
//     "col.actions": "Actions",
//     "col.carrier_count": "Carriers",
//     "col.email": "Email",
//     "col.name": "Name",
//     "col.role": "Role",
//     "col.slug": "Slug",
//     "col.status": "Status",
//     "col.tenant": "Tenant",
//     "col.type": "Type",
//     "dashboard.title": "Platform Administration",
//     "field.admin_email": "Admin Email",
//     "field.admin_first": "First Name",
//     "field.admin_last": "Last Name",
//     "field.invite_toggle": "Send invitation email",
//     "field.subdomain": "Subdomain",
//     "field.tenant_name": "Tenant Name",
//     "field.tenant_type": "Tenant Type",
//     "provisioning.keycloak": "Configuring access…",
//     "provisioning.migrations": "Applying migrations…",
//     "provisioning.schema": "Creating schema…",
//     "provisioning.seeding": "Seeding data…",
//     "stat.active_tenants": "Active Tenants",
//     "stat.tenant_carrier_pairs": "Tenant-Carrier Pairs",
//     "stat.total_carriers": "Total Carriers",
//     "stat.total_users": "Total Users",
//     "subdomain.immutable_note": "Cannot be changed after creation.",
//     "subdomain.preview": "Subdomain Preview",
//     "subdomain.reserved": "This subdomain is reserved.",
//     "subdomain.taken": "This subdomain is already taken.",
//     "tenants.title": "Tenants",
//     "users.title": "Platform Users",
//     "wizard.step1": "Tenant Details",
//     "wizard.step2": "Admin User",
//     "step3.no_carriers": "No carriers configured yet. Add one below.",
//    "step3.optional_hint": "Carrier assignment is optional at this stage. You can add carriers after activation from the Tenant Administration panel.",
//    "step3.zero_carriers_notice": "No carriers selected — the tenant will be activated without carriers. Carriers can be added later from the Tenant Administration panel.",
//    "step4.no_carriers_note": "No carriers assigned at this time — carriers can be added from the Tenant Administration panel after activation.",
//    "step4.section.admin": "Administrator",
//    "step4.section.carriers": "Carriers",
//    "step4.section.tenant": "Tenant Details",
//    "step4.title": "Review & Activate",
//    "wizard.step3": "Carrier Assignment (Optional)",
//     "wizard.step4": "Review & Activate",
//   },
//   // ── policies ────────────────────────────────────────────────────────────────
//   "policies": {
//     "col.audit_status": "Audit Status",
//     "col.effective_date": "Effective Date",
//     "col.est_premium": "Est. Premium",
//     "col.insured_name": "Insured",
//     "col.policy_number": "Policy Number",
//     "col.risk_level": "Risk",
//     "col.state": "State",
//     "col.status": "Status",
//     "col.variance_amount": "Variance $",
//     "col.variance_pct": "Variance %",
//     "filter.all_risk": "All Risk Levels",
//     "filter.all_statuses": "All Statuses",
//     "pagination.of": "of",
//     "pagination.rows": "rows",
//     "title": "Policies",
//   },
//   // ── policy_detail ───────────────────────────────────────────────────────────
//   "policy_detail": {
//     "meta.audit_status": "Audit Status",
//     "meta.cancellation": "Cancellation Date",
//     "meta.effective": "Effective Date",
//     "meta.expiration": "Expiration Date",
//     "meta.fein": "FEIN",
//     "meta.insured": "Insured Name",
//     "meta.owner_status": "Owner Status",
//     "meta.payment_freq": "Payment Frequency",
//     "meta.policy_number": "Policy Number",
//     "meta.policy_status": "Policy Status",
//     "meta.state": "State",
//     "meta.total_est_payroll": "Total Est. Payroll",
//     "pv.actual_premium": "Actual Premium",
//     "pv.est_premium": "Est. Premium",
//     "pv.section_title": "Premium Variance",
//     "pv.variance_amount": "Variance Amount",
//     "pv.variance_pct": "Variance %",
//     "pvc.actual_classified": "Actual Classified",
//     "pvc.actual_reported": "Actual Reported",
//     "pvc.class_code": "Class Code",
//     "pvc.classified_over_under": "Classified Δ",
//     "pvc.classified_pct": "Classified %",
//     "pvc.description": "Description",
//     "pvc.est_payroll": "Est. Payroll",
//     "pvc.reported_over_under": "Reported Δ",
//     "pvc.reported_pct": "Reported %",
//     "pvc.state": "State",
//     "pvp.actual_classified": "Actual Classified",
//     "pvp.actual_reported": "Actual Reported",
//     "pvp.classified_over_under": "Classified Over / Under",
//     "pvp.classified_pct": "Classified %",
//     "pvp.est_payroll": "Est. Payroll",
//     "pvp.reported_over_under": "Reported Over / Under",
//     "pvp.reported_pct": "Reported %",
//     "pvp.section_title": "Payroll Variance",
//     "tab.ai_narrative": "AI Narrative",
//     "tab.missing_payrolls": "Missing Payrolls",
//     "tab.summary": "Summary",
//     "tab.zero_payrolls": "Zero Payrolls",
//     "title": "Policy Detail",
//   },
//   // ── shared ──────────────────────────────────────────────────────────────────
//   "shared": {
//     "engine_off_notice": "Calculation engine is off. Engine-derived fields show N/A.",
//     "error_generic": "Something went wrong. Please try again.",
//     "loading": "Loading…",
//     "na_label": "N/A",
//     "no_data": "No data available.",
//   },
//   // ── submission ──────────────────────────────────────────────────────────────
//   "submission": {
//     "missing.days_since": "Days Since Last",
//     "missing.period_end": "Period End",
//     "missing.period_start": "Period Start",
//     "pills.actual_received": "Received",
//     "pills.expected": "Expected",
//     "pills.missing": "Missing",
//     "pills.rate": "Submit Rate",
//     "pills.zero_payrolls": "Zero Payrolls",
//   },
//   // ── users ───────────────────────────────────────────────────────────────────
//   "users": {
//     "btn.cancel": "Cancel",
//     "btn.create": "Create User",
//     "btn.deactivate": "Deactivate",
//     "col.actions": "Actions",
//     "col.email": "Email",
//     "col.name": "Name",
//     "col.onboarding": "Onboarding",
//     "col.role": "Role",
//     "field.email": "Email Address",
//     "field.first_name": "First Name",
//     "field.last_name": "Last Name",
//     "field.role": "Role",
//     "modal.create_title": "Create User",
//     "modal.deactivate_confirm": "Are you sure you want to deactivate this user?",
//     "modal.edit_title": "Edit User",
//     "role.auditor": "Auditor",
//     "role.reviewer": "Reviewer",
//     "role.super_admin": "Super Admin",
//     "role.tenant_admin": "Tenant Admin",
//     "title": "User Management",
//   },
//   // ── zero_payroll ────────────────────────────────────────────────────────────
//   "zero_payroll": {
//     "col.frequency": "Frequency",
//     "col.policy_number": "Policy #",
//     "col.policyholder": "Policyholder",
//     "col.report_date": "Report Date",
//     "col.state": "State",
//   },
// };

// // ---------------------------------------------------------------------------
// // API fetch — per screen_key, matches Redis key structure
// // ---------------------------------------------------------------------------

// async function fetchLabels(
//   carrierId: number,
//   screenKey: ScreenKey,
// ): Promise<Record<string, string>> {
//   const { data } = await axios.get<Record<string, string>>(
//     `/api/v1/labels?carrier_id=${carrierId}&screen_key=${screenKey}`,
//   );
//   return data;
// }

// // ---------------------------------------------------------------------------
// // useLabels — V9 S23.2 exact signature
// // ---------------------------------------------------------------------------

// /**
//  * useLabels(screenKey) — Phase 6 V9 S23.2 conformant implementation.
//  *
//  * Returns a lookup function: (fieldKey: string, fallback: string) => string
//  *
//  * The lookup function resolves:
//  *   1. API override for this carrier + screen_key + field_key
//  *   2. DEFAULT_LABELS[screenKey][fieldKey]
//  *   3. fallback argument (shown only in development — never in production data)
//  *
//  * Cache: TanStack Query staleTime 5 min; query key includes screenKey so each
//  * screen fetches its own Redis slot matching {schema}:labels:{carrier_id}:{screen_key}.
//  *
//  * Fallback guarantee: the returned function never throws, never returns undefined.
//  * If the API is unavailable, DEFAULT_LABELS values are used transparently.
//  */
// export function useLabels(screenKey: ScreenKey): (fieldKey: string, fallback: string) => string {
//   const { carrierId } = useTenantCarrier();

//   const { data: overrides } = useQuery({
//     queryKey: ["labels", carrierId, screenKey],
//     queryFn: () => fetchLabels(carrierId, screenKey),
//     staleTime: 5 * 60 * 1000,
//     enabled: carrierId > 0,
//     placeholderData: {},
//     retry: false,
//     // Errors swallowed — DEFAULT_LABELS is always the safe fallback.
//   });

//   const defaults = DEFAULT_LABELS[screenKey] ?? {};

//   return (fieldKey: string, fallback: string): string =>
//     overrides?.[fieldKey] ?? defaults[fieldKey] ?? fallback;
// }

/**
 * useLabels — UI string registry
 *
 * V9 S23 — strict conformance implementation.
 *
 * All user-visible strings are accessed through this hook.
 * No hardcoded strings in component JSX.
 *
 * Usage per V9 S23.2:
 *   const label = useLabels("dashboard");
 *   <span>{label("kpi.book_premium", "Total Book Premium")}</span>
 *
 * Resolution chain (V9 S23.1):
 *   1. carrier_ui_labels from API (carrier-specific overrides)
 *   2. DEFAULT_LABELS registry (platform defaults)
 *   3. fallback argument (development safety net)
 *
 * Redis cache key: {schema}:labels:{carrier_id}:{screen_key}  TTL 5 min
 */

import axios from "axios";
import { useQuery } from "@tanstack/react-query";
import { useTenantCarrier } from "@/context/TenantCarrierContext";
import { useAuth } from "@/context/AuthContext";

// ---------------------------------------------------------------------------
// Screen key type — all valid screen namespaces per V9 S23.3
// ---------------------------------------------------------------------------

export type ScreenKey =
  | "audit_runner"
  | "calc_engine"
  | "calc_rule_builder"
  | "carrier_config"
  | "dashboard"
  | "field_mapping"
  | "ingestion"
  | "narrative_panel"
  | "ai_config"
  | "onboarding"
  | "org_settings"
  | "platform_admin"
  | "policies"
  | "policy_detail"
  | "reports"
  | "shared"
  | "submission"
  | "tenant_detail"
  | "create_user"
  | "users"
  | "zero_payroll"
  ;

// ---------------------------------------------------------------------------
// DEFAULT_LABELS — platform defaults, grouped by screen_key per V9 S23.3.
// Values are the in-code fallback; all must be non-empty strings.
// MUST NOT be modified without updating the V9 S23.3 catalogue.
// ---------------------------------------------------------------------------

export const DEFAULT_LABELS: Record<ScreenKey, Record<string, string>> = {
  // ── audit_runner ────────────────────────────────────────────────────────────
  "audit_runner": {
    "btn.upload_and_map": "Upload & Map Fields",
    "btn.uploading": "Uploading…",
    "subtitle": "Upload a carrier data file to begin the audit ingestion pipeline. The system will auto-map fields and require your approval before loading data.",
    "title": "Audit Runner",
    "upload.dropzone_aria": "Click or drag to select XLSX file",
    "upload.dropzone_hint": "XLSX files only (CSV and XML coming in Phase 4)",
    "upload.dropzone_text": "Click to select or drag and drop",
    "upload.error": "Upload failed. Please try again.",
    "upload.format_coming_phase4": "Coming in Phase 4",
    "upload.no_file": "Please select a file to upload.",
    "upload.xlsx_only": "Please upload an XLSX file.",
  },
  // ── calc_engine ─────────────────────────────────────────────────────────────
  "calc_engine": {
    "btn.ai_suggest": "AI Suggest",
    "btn.approve_activate": "Approve & Activate",
    "btn.cancel": "Cancel",
    "btn.deactivate": "Deactivate",
    "btn.edit": "Edit",
    "btn.history": "History",
    "btn.revert_draft": "Revert to Draft",
    "btn.save": "Save",
    "btn.submit_review": "Submit for Review",
    "btn.test_expression": "Test",
    "col.actions": "Actions",
    "col.expression": "Expression",
    "col.rule_key": "Rule Key",
    "col.rule_status": "Status",
    "col.rule_type": "Type",
    "rule.ai_suggest_loading": "Generating suggestion…",
    "rule.expression_placeholder": "Enter expression (e.g. abs(variance_pct) > 30)",
    "rule.history_title": "Rule Change History",
    "rule.locked_tooltip": "This rule is locked and cannot be edited.",
    "rule.test_result_label": "Test result:",
    "rules.subtitle": "LOCKED rules use built-in Python logic. EDITABLE rules use configurable expressions evaluated at run time.",
    "rules.title": "Calculation Rules",
    "toggle.label": "Calculation Engine",
    "toggle.off": "OFF",
    "toggle.off_warning": "Engine is OFF. All engine-derived fields (Variance %, Risk Level) will show N/A on the dashboard.",
    "toggle.on": "ON",
    "toggle.saving": "Saving…",
  },
  // ── carrier_config ──────────────────────────────────────────────────────────
  "carrier_config": {
    "coming.phase4": "Coming in Phase 4",
    "coming.phase5": "Coming in Phase 5",
    "coming.phase6": "Coming in Phase 6",
    "tab.calc_engine": "Calculation Engine",
    "tab.field_map": "Field Mapping",
    "tab.labels": "Labels & Display",
    "tab.report": "Report Template",
    "tab.theme": "Theme",
    "tab.ai_config": "AI Configuration",
    "title": "Carrier Configuration",
  },
  // ── dashboard ───────────────────────────────────────────────────────────────
  "dashboard": {
    "chart.active_policies": "Active",
    "chart.cancelled_policies": "Cancelled",
    "chart.risk_dist": "Risk Distribution",
    "chart.state_risk": "Policies by State & Risk",
    "chart.status_dist": "Policy Status",
    "kpi.actual_earned": "Actual Earned Premium",
    "kpi.book_premium": "Total Book Premium",
    "kpi.est_earned": "Est. Earned Premium",
    "kpi.variance": "Total Variance",
    "risk.high": "High",
    "risk.low": "Low",
    "risk.medium": "Medium",
    "risk.unassigned": "Unassigned",
    "subtitle": "Workers Compensation Premium Audit Overview",
    "target.over": "Policies Above Threshold",
    "target.title": "Policies Above 30% Variance Threshold",
    "target.total_above": "Total Variance Above Threshold",
    "title": "Audit Dashboard",
    "btn_view_all_policies": "View All Policies →",
    "section_all_policies": "All Policies",
    "table_view_all_link": "View all policies →",
    "table_col_audit_status": "Audit Status",
    "chart_tooltip_count": "Count",
    "chart_tooltip_pct_of_total": "% of total",
    "state_filter_all_label": "All States",
    "state_filter_select_all": "Select All",
    "state_filter_placeholder": "Filter states…",
  },
  // ── field_mapping ───────────────────────────────────────────────────────────
  "field_mapping": {
    "btn.approve_mapping": "Approve Mapping",
    "btn.approving": "Approving…",
    "btn.back_to_upload": "Back to Upload",
    "btn.reject_mapping": "Reject & Start Over",
    "col.exclude": "Exclude",
    "col.proposed_target": "Target Column",
    "col.source_field": "Source Field",
    "col.source_sample": "Sample Value",
    "col.transform": "Transform",
    "confidence.high": "HIGH",
    "confidence.medium_low": "MED/LOW",
    "confidence.unmatched": "UNMATCHED",
    "fields": "fields",
    "mapping.admin_only": "Mapping approval requires Tenant Administrator access.",
    "mapping.approve_disabled_tooltip": "Assign or exclude all UNMATCHED fields before approving.",
    "mapping.load_error": "Failed to load field mapping.",
    "mapping.session_missing": "No mapping session found. Please re-upload the file.",
    "mapping.unassigned": "— Unassigned —",
    "subtitle": "Review the auto-mapped field proposals before approving ingestion. Adjust any LOW or UNMATCHED fields.",
    "title": "Field Mapping Review",
  },
  // ── ingestion ───────────────────────────────────────────────────────────────
  "ingestion": {
    "btn.run_calc_engine": "Run Calculation Engine",
    "btn.try_again": "Try Again",
    "progress.complete": "Ingestion complete.",
    "progress.failed": "Ingestion failed.",
    "progress.no_run_id": "No run ID found. Please start a new upload.",
    "progress.partial": "Ingestion partially completed.",
    "progress.poll_error": "Could not reach server:",
    "progress.processing": "Processing data — this may take a moment…",
    "progress.rows_loaded": "Rows loaded:",
    "progress.rows_skipped": "Skipped:",
    "progress.subtitle": "Run",
    "progress.title": "Ingestion Progress",
    "progress.waiting": "Waiting for ingestion to start…",
  },
  // ── onboarding ──────────────────────────────────────────────────────────────
  "onboarding": {
    "btn.continue": "Continue",
    "btn.finish": "Go to Dashboard",
    "btn.prev": "Previous",
    "carrier.config_status": "Configuration Status",
    "carrier.not_configured": "Not configured",
    "screen.s1_title": "Tell us about your organisation",
    "screen.s2_title": "Add your contact details",
    "screen.s3_title": "Customise your branding",
    "screen.s4_title": "Your assigned carriers",
    "screen.s5_complete_msg": "Your organisation is configured. You can update these settings anytime under Organisation Settings.",
    "screen.s5_title": "You're all set!",
    "step.1": "Organisation Profile",
    "step.2": "Contacts",
    "step.3": "Branding",
    "step.4": "Carrier Overview",
    "step.5": "Complete",
    "title": "Welcome — Let's set up your organisation",
  },
  // ── org_settings ────────────────────────────────────────────────────────────
  "org_settings": {
    "branding.brand_color": "Brand Colour",
    "branding.brand_color_hint": "6-character hex value (e.g. 4ade80)",
    "branding.drag_drop": "Drag and drop a file, or click to browse",
    "branding.logo": "Organisation Logo",
    "branding.logo_hint": "PNG, JPG, or SVG · Max 5 MB",
    "branding.upload_btn": "Upload Logo",
    "btn.save": "Save Changes",
    "contact.primary": "Primary Contact",
    "contact.secondary": "Secondary Contact",
    "field.address_line1": "Address Line 1",
    "field.address_line2": "Address Line 2",
    "field.city": "City",
    "field.contact_email": "Contact Email",
    "field.contact_name": "Contact Name",
    "field.contact_phone": "Contact Phone",
    "field.display_name": "Display Name",
    "field.legal_name": "Legal Name",
    "field.state": "State",
    "field.zip": "ZIP Code",
    "msg.save_success": "Changes saved successfully.",
    "tab.branding": "Branding",
    "tab.carriers": "Carriers",
    "tab.contacts": "Contacts",
    "tab.profile": "Profile",
    "carriers.add_hint": "Adding a carrier seeds default calculation rules and configuration. Rules can be customised from the Carrier Configuration Hub.",
    "carriers.create_title": "Create a New Carrier",
    "carriers.create_hint": "Don't see the carrier you need? Create a new one and it will be assigned to your organisation immediately.",
    "carriers.create_name_label": "Carrier Name",
    "carriers.create_name_placeholder": "e.g. Acme Insurance",
    "carriers.create_slug_label": "Identifier (slug)",
    "carriers.create_slug_placeholder": "e.g. acme-insurance",
    "carriers.create_slug_hint": "Lowercase letters, numbers, and hyphens only. Cannot be changed later.",
    "carriers.btn.create": "+ New Carrier",
    "carriers.btn.create_confirm": "Create & Assign",
    "carriers.btn.creating": "Creating…",
    "carriers.add_title": "Add a Carrier",
    "carriers.all_assigned": "All available platform carriers are already assigned to your organisation.",
    "carriers.assigned_title": "Assigned Carriers",
    "carriers.btn.add": "Add Carrier",
    "carriers.btn.adding": "Adding…",
    "carriers.btn.cancel": "Cancel",
    "carriers.btn.confirm": "Confirm",
    "carriers.btn.remove": "Remove",
    "carriers.col.actions": "Actions",
    "carriers.col.name": "Carrier Name",
    "carriers.col.slug": "Identifier",
    "carriers.confirm_remove": "Remove this carrier?",
    "carriers.none_assigned": "No carriers assigned yet. Use the section below to add your first carrier.",
    "carriers.select_label": "Select carrier to add",
    "carriers.select_placeholder": "— Select a carrier —",
    "title": "Organization Settings",
    // Phase 7B additions
    "tab_profile": "Profile",
    "tab_branding": "Branding",
    "tab_carriers": "Carriers",
    "branding_logo_light": "Logo (Light Background)",
    "branding_logo_dark": "Logo (Dark Background)",
    "branding_favicon": "Favicon",
    "branding_brand_color": "Brand Colour",
    "branding_preview": "Live Preview",
    // Phase 7BCD redesign additions
    "page_subtitle": "Manage your organisation profile, contacts, branding, and carrier assignments.",
    "section.identity": "Organisation Identity",
    "section.identity_subtitle": "The display name appears throughout the platform. The legal name is used on reports and documents.",
    "section.address": "Mailing Address",
    "section.contacts": "Contact Details",
    "section.contacts_subtitle": "Primary and secondary contacts are used for billing and audit communications.",
    "branding.file_type_error": "Only PNG, JPG, and SVG files are accepted.",
    "branding.file_size_error": "File exceeds the 5 MB size limit.",
    "branding.color_format_error": "Enter a 6-character hex value, e.g. 4ade80",
    "branding.logo_preview_alt": "Logo preview",
  },
  // ── platform_admin ──────────────────────────────────────────────────────────
  "platform_admin": {
    "btn.activate": "Activate",
    "btn.back": "Back",
    "btn.new_carrier": "Add Carrier",
    "btn.new_tenant": "New Tenant",
    "btn.next": "Next",
    "btn.save_draft": "Save as Draft",
    "carriers.title": "Carriers",
    "col.actions": "Actions",
    "col.carrier_count": "Carriers",
    "col.email": "Email",
    "col.name": "Name",
    "col.role": "Role",
    "col.slug": "Slug",
    "col.status": "Status",
    "col.tenant": "Tenant",
    "col.type": "Type",
    "dashboard.title": "Platform Administration",
    "field.admin_email": "Admin Email",
    "field.admin_first": "First Name",
    "field.admin_last": "Last Name",
    "field.invite_toggle": "Send invitation email",
    "field.subdomain": "Subdomain",
    "field.tenant_name": "Tenant Name",
    "field.tenant_type": "Tenant Type",
    "provisioning.keycloak": "Configuring access…",
    "provisioning.migrations": "Applying migrations…",
    "provisioning.schema": "Creating schema…",
    "provisioning.seeding": "Seeding data…",
    "stat.active_tenants": "Active Tenants",
    "stat.tenant_carrier_pairs": "Tenant-Carrier Pairs",
    "stat.total_carriers": "Total Carriers",
    "stat.total_users": "Total Users",
    "subdomain.immutable_note": "Cannot be changed after creation.",
    "subdomain.preview": "Subdomain Preview",
    "subdomain.reserved": "This subdomain is reserved.",
    "subdomain.taken": "This subdomain is already taken.",
    "tenants.title": "Tenants",
    "users.title": "Platform Users",
    "wizard.step1": "Tenant Details",
    "wizard.step2": "Admin User",
    "wizard.step3": "Carrier Assignment (Optional)",
    "wizard.step4": "Review & Activate",
    "step3.no_carriers": "No carriers configured yet. Add one below.",
    "step3.optional_hint": "Carrier assignment is optional at this stage. You can add carriers after activation from the Tenant Administration panel.",
    "step3.zero_carriers_notice": "No carriers selected — the tenant will be activated without carriers. Carriers can be added later from the Tenant Administration panel.",
    "step4.no_carriers_note": "No carriers assigned at this time — carriers can be added from the Tenant Administration panel after activation.",
    "step4.section.admin": "Administrator",
    "step4.section.carriers": "Carriers",
    "step4.section.tenant": "Tenant Details",
    "step4.title": "Review & Activate",
    // Phase 7B additions
    "title": "Platform Administration",
    "btn_new_tenant": "+ New Tenant",
    "stat_tenants": "Tenants",
    "stat_tenants_sub": "Active",
    "stat_carriers": "Carriers",
    "stat_carriers_sub": "Platform",
    "stat_users": "Total Users",
    "stat_users_sub": "Across all tenants",
    "stat_tc_pairs": "Active TC Pairs",
    "stat_tc_pairs_sub": "Tenant-Carrier",
    "table_col_name": "Name",
    "table_col_type": "Type",
    "table_col_status": "Status",
    "table_col_carriers": "Carriers",
    "table_col_actions": "Actions",
    "search_placeholder": "Search tenants…",
    "filter_status_all": "All Statuses",
    "action_view": "View",
    // Phase 7BCD additions — carrier edit, theme management, wizard redesign
    "carrier.edit_title": "Edit Carrier",
    "carrier.slug_label": "Slug / Identifier",
    "carrier.slug_immutable": "Slug cannot be changed after creation.",
    "carrier.ai_narrative_label": "AI Narrative",
    "carrier.ai_enabled": "Enabled",
    "carrier.ai_disabled": "Disabled",
    "carrier.btn_save": "Save Changes",
    "carriers.empty": "No carriers yet. Add one to get started.",
    "col.edit": "Edit",
    "aria.progress": "Wizard progress",
    "wizard.optional_hint": "Optional",
    "btn.cancel_short": "Cancel",
    "themes.title": "Platform Themes",
    "themes.subtitle": "Manage default and variant themes for the platform. The designated default theme is used when no tenant theme override exists.",
    "themes.btn_new": "New Theme Variant",
    "themes.btn_create": "Create",
    "themes.btn_set_default": "Set as Default",
    "themes.default_badge": "Platform Default",
    "themes.mode_dark": "Dark mode",
    "themes.mode_light": "Light mode",
    "themes.created_prefix": "Created",
    "themes.id_prefix": "ID:",
    "themes.empty": "No platform themes found.",
    "themes.new_name_placeholder": "Theme name…",
    "themes.create_error": "Failed to create theme.",
    // Phase 7BCD additions — theme token editor + wizard page
    "themes.btn_edit_tokens": "Edit Tokens",
    "themes.edit_title": "Edit Theme Tokens",
    "themes.btn_save_tokens": "Save Tokens",
    "themes.name_label": "Theme Name",
    "wizard.error_generic": "Provisioning failed. Please try again.",
    "wizard.page_subtitle": "Complete all steps to provision and activate a new tenant.",
  },
  // ── policies ────────────────────────────────────────────────────────────────
  "policies": {
    "col.audit_status": "Audit Status",
    "col.effective_date": "Effective Date",
    "col.est_premium": "Est. Premium",
    "col.insured_name": "Insured",
    "col.policy_number": "Policy Number",
    "col.risk_level": "Risk",
    "col.state": "State",
    "col.status": "Status",
    "col.variance_amount": "Variance $",
    "col.variance_pct": "Variance %",
    "filter.all_risk": "All Risk Levels",
    "filter.all_statuses": "All Statuses",
    "pagination.of": "of",
    "pagination.rows": "rows",
    "title": "Policies",
    "filter_status_label": "STATUS",
    "filter_risk_label": "RISK",
    "filter_state_label": "STATE",
    "col_audit_status": "Audit Status",
  },
  // ── reports ─────────────────────────────────────────────────────────────────
  "reports": {
    "btn.book_summary": "Book Summary",
    "btn.export_excel": "Export Excel",
    "btn.generate": "Generate Report",
    "btn.generate_audit": "Generate Audit Report",
    "format.excel": "Excel",
    "format.pdf": "PDF",
    "modal.status_title": "Report Status",
    "msg.select_policy_first": "Select a policy to generate a report.",
    "status.failed": "Report generation failed.",
    "status.generating": "Generating report…",
    "status.generating_detail": "This may take a moment.",
    "status.ready": "Report ready.",
  },
  // ── policy_detail ───────────────────────────────────────────────────────────
  "policy_detail": {
    "meta.audit_status": "Audit Status",
    "meta.cancellation": "Cancellation Date",
    "meta.effective": "Effective Date",
    "meta.expiration": "Expiration Date",
    "meta.fein": "FEIN",
    "meta.insured": "Insured Name",
    "meta.owner_status": "Owner Status",
    "meta.payment_freq": "Payment Frequency",
    "meta.policy_number": "Policy Number",
    "meta.policy_status": "Policy Status",
    "meta.state": "State",
    "meta.total_est_payroll": "Total Est. Payroll",
    "pv.actual_premium": "Actual Premium",
    "pv.est_premium": "Est. Premium",
    "pv.section_title": "Premium Variance",
    "pv.variance_amount": "Variance Amount",
    "pv.variance_pct": "Variance %",
    "pvc.actual_classified": "Actual Classified",
    "pvc.actual_reported": "Actual Reported",
    "pvc.class_code": "Class Code",
    "pvc.classified_over_under": "Classified Δ",
    "pvc.classified_pct": "Classified %",
    "pvc.description": "Description",
    "pvc.est_payroll": "Est. Payroll",
    "pvc.reported_over_under": "Reported Δ",
    "pvc.reported_pct": "Reported %",
    "pvc.state": "State",
    "pvp.actual_classified": "Actual Classified",
    "pvp.actual_reported": "Actual Reported",
    "pvp.classified_over_under": "Classified Over / Under",
    "pvp.classified_pct": "Classified %",
    "pvp.est_payroll": "Est. Payroll",
    "pvp.reported_over_under": "Reported Over / Under",
    "pvp.reported_pct": "Reported %",
    "pvp.section_title": "Payroll Variance",
    "tab.ai_narrative": "AI Narrative",
    "tab.missing_payrolls": "Missing Payrolls",
    "tab.summary": "Summary",
    "tab.zero_payrolls": "Zero Payrolls",
    "title": "Policy Detail",
  },
  // ── shared ──────────────────────────────────────────────────────────────────
  "shared": {
    "btn.close": "Close",
    "engine_off_notice": "Calculation engine is off. Engine-derived fields show N/A.",
    "error_generic": "Something went wrong. Please try again.",
    "loading": "Loading…",
    "na_label": "N/A",
    "no_data": "No data available.",
  },
  // ── submission ──────────────────────────────────────────────────────────────
  "submission": {
    "missing.days_since": "Days Since Last",
    "missing.period_end": "Period End",
    "missing.period_start": "Period Start",
    "pills.actual_received": "Received",
    "pills.expected": "Expected",
    "pills.missing": "Missing",
    "pills.rate": "Submit Rate",
    "pills.zero_payrolls": "Zero Payrolls",
  },
  // ── users ───────────────────────────────────────────────────────────────────
  "users": {
    "btn.cancel": "Cancel",
    "btn.create": "Invite User",
    "btn.deactivate": "Deactivate User",
    "col.actions": "Actions",
    "col.edit": "Edit",
    "col.email": "Email",
    "col.last_login": "Last Login",
    "col.name": "Name",
    "col.onboarding": "Onboarding",
    "col.role": "Role",
    "col.status": "Status",
    "empty_cta": "Invite your first team member",
    "empty_state": "No team members yet.",
    "field.email": "Email Address",
    "field.first_name": "First Name",
    "field.last_name": "Last Name",
    "field.role": "Role",
    "modal.create_title": "Create User",
    "modal.deactivate_confirm": "Are you sure you want to deactivate this user? They will lose access immediately.",
    "modal.edit_title": "Edit User",
    "role.auditor": "Auditor",
    "role.reviewer": "Reviewer",
    "role.super_admin": "Super Admin",
    "role.tenant_admin": "Tenant Admin",
    "section.danger_zone": "Danger Zone",
    "section.identity": "Identity",
    "section.role": "Role & Permissions",
    "title": "User Management",
  },
  // ── zero_payroll ────────────────────────────────────────────────────────────
  "zero_payroll": {
    "col.frequency": "Frequency",
    "col.policy_number": "Policy #",
    "col.policyholder": "Policyholder",
    "col.report_date": "Report Date",
    "col.state": "State",
  },

  // ── Phase 7B: tenant_detail ──────────────────────────────────────────────
  "tenant_detail": {
    "section_identity": "Identity",
    "section_carriers": "Assigned Carriers",
    "carriers_managed_by_admin": "Carrier assignments are managed by the Tenant Administrator.",
    "section_users": "Users",
    "section_danger_zone": "Danger Zone",
    "label_slug": "Slug",
    "label_schema": "Schema",
    "label_type": "Type",
    "label_url": "URL",
    "carrier_engine_on": "Engine ON",
    "carrier_engine_off": "Engine OFF",
    "btn_deactivate_tenant": "Deactivate Tenant",
    "btn_delete_tenant": "Delete Tenant",
    "back_to_admin": "← Platform Admin",
  },

  // ── Phase 7B: create_user (new keys) ─────────────────────────────────────
  "create_user": {
    "section_personal": "Personal Details",
    "section_role": "Role & Permissions",
    "label_first_name": "First Name",
    "label_last_name": "Last Name",
    "label_email": "Email Address",
    "role_auditor_description": "Can upload files and trigger calculations.",
    "role_reviewer_description": "Read-only. Can view policies and reports.",
    "role_tenant_admin_description": "Full access to organisation settings and user management.",
    "btn_send_invitation": "Send Invitation →",
    "btn_cancel": "Cancel",
    "validation_email_required": "Email address is required.",
    "validation_email_invalid": "Please enter a valid email address.",
    "validation_first_name_required": "First name is required.",
    "validation_last_name_required": "Last name is required.",
    "validation_role_required": "Please select a role.",
  },

  // ── Phase 7C: narrative_panel ─────────────────────────────────────────────
  "narrative_panel": {
    "title": "AI-Generated Audit Narrative",
    "generated_at_prefix": "Generated:",
    "btn_show_full": "Show Full Narrative ▼",
    "btn_collapse": "Collapse ▲",
    "btn_copy": "Copy to Clipboard",
    "btn_copied": "Copied!",
    "fallback_notice": "This narrative was generated using a template because the AI service was unavailable.",
    "engine_not_run_notice": "Enable the Calculation Engine and re-run to generate an AI narrative.",
    "not_attempted": "Narrative generation was not attempted for this run.",
    "loading": "Generating narrative…",
    "provider_badge_prefix": "via",
    "no_narrative": "No narrative available for this policy.",
  },

  // ── Phase 7C: ai_config ───────────────────────────────────────────────────
  "ai_config": {
    "tab_title": "AI Configuration",
    "page_title": "AI Narrative Configuration",
    "page_subtitle": "Configure the language model used to generate audit narratives for this carrier. Leave unconfigured to use the platform default (Anthropic Claude).",
    "section_current": "Current Configuration",
    "no_config_notice": "No AI configuration for this carrier. Using platform default (Anthropic Claude).",
    "provider_label": "LLM Provider",
    "model_label": "Model",
    "api_key_label": "API Key",
    "api_key_placeholder": "Enter API key (stored encrypted)",
    "api_key_stored_hint": "API key stored securely. Last 4 digits:",
    "api_base_url_label": "API Base URL",
    "api_base_url_placeholder": "e.g. https://resource.openai.azure.com/",
    "btn_save": "Save Configuration",
    "btn_saving": "Saving…",
    "btn_test": "Test Connection",
    "btn_testing": "Testing…",
    "btn_delete": "Remove Configuration",
    "test_success": "Connection successful",
    "test_failed": "Connection failed",
    "test_latency": "Latency:",
    "save_success": "AI configuration saved.",
    "save_error": "Failed to save configuration.",
    "delete_confirm": "Remove AI configuration for this carrier? The platform default will be used.",
    "select_provider_placeholder": "— Select a provider —",
    "select_model_placeholder": "— Select a model —",
    // Phase 7BCD — standalone AI Config page
    "carrier_selector_label": "Carrier:",
    "carrier_selector_aria": "Select carrier",
    "no_carriers_notice": "No carriers available. Please configure a carrier first.",
  },

  // ── Phase 7D: calc_rule_builder ───────────────────────────────────────────
  "calc_rule_builder": {
    "title": "Expression Builder",
    "btn_switch_to_raw": "↔ Switch to Raw Text",
    "btn_switch_to_builder": "↔ Switch to Builder",
    "section_fields": "Available Fields",
    "section_canvas": "Expression Canvas",
    "section_operators": "Operators",
    "section_expression": "Expression (raw)",
    "search_placeholder": "Search fields…",
    "complex_expression_notice": "This expression is too complex for the visual builder. Edit it in raw text mode.",
    "btn_test_expression": "Test Expression",
    "btn_apply": "Apply →",
    "drop_hint": "Drag fields here to build your expression",
    "tooltip_example": "Example:",
    "category_payroll": "Payroll",
    "category_premium": "Premium",
    "category_class_code": "Class Code",
    "category_officer": "Officer",
    "category_submission": "Submission",
    "fields_empty_state": "No fields available",
    "validation_errors_heading": "Expression errors must be resolved before saving",
  },
};

// ---------------------------------------------------------------------------
// API fetch — per screen_key, matches Redis key structure
// ---------------------------------------------------------------------------

async function fetchLabels(
  carrierId: number,
  screenKey: ScreenKey,
): Promise<Record<string, string>> {
  const { data } = await axios.get<Record<string, string>>(
    `/api/v1/labels?carrier_id=${carrierId}&screen_key=${screenKey}`,
  );
  return data;
}

// ---------------------------------------------------------------------------
// useLabels — V9 S23.2 exact signature
// ---------------------------------------------------------------------------

/**
 * useLabels(screenKey) — Phase 6 V9 S23.2 conformant implementation.
 *
 * Returns a lookup function: (fieldKey: string, fallback: string) => string
 *
 * The lookup function resolves:
 *   1. API override for this carrier + screen_key + field_key
 *   2. DEFAULT_LABELS[screenKey][fieldKey]
 *   3. fallback argument (shown only in development — never in production data)
 *
 * Cache: TanStack Query staleTime 5 min; query key includes screenKey so each
 * screen fetches its own Redis slot matching {schema}:labels:{carrier_id}:{screen_key}.
 *
 * Fallback guarantee: the returned function never throws, never returns undefined.
 * If the API is unavailable, DEFAULT_LABELS values are used transparently.
 */
export function useLabels(screenKey: ScreenKey): (fieldKey: string, fallback: string) => string {
  const { carrierId } = useTenantCarrier();
  const { user } = useAuth();
  // SUPER_ADMIN has no tenant schema — disable label API calls to prevent 400 errors.
  // Labels fall through to DEFAULT_LABELS for SUPER_ADMIN screens.
  const isTenantUser = user !== null && user.role !== "SUPER_ADMIN";

  const { data: overrides } = useQuery({
    queryKey: ["labels", carrierId, screenKey],
    queryFn: () => fetchLabels(carrierId, screenKey),
    staleTime: 5 * 60 * 1000,
    enabled: isTenantUser && carrierId > 0,
    placeholderData: {},
    retry: false,
    // Errors swallowed — DEFAULT_LABELS is always the safe fallback.
  });

  const defaults = DEFAULT_LABELS[screenKey] ?? {};

  return (fieldKey: string, fallback: string): string =>
    overrides?.[fieldKey] ?? defaults[fieldKey] ?? fallback;
}