/**
 * useLabels — UI string registry
 *
 * All user-visible strings must be accessed through this hook.
 * No hardcoded strings in component JSX.
 *
 * Phase 1: returns DEFAULT_LABELS (hardcoded).
 * Phase 3: merges carrier_ui_labels overrides from the API.
 *
 * Usage:
 *   const labels = useLabels();
 *   <span>{labels.kpi_total_book_premium}</span>
 */

export interface LabelMap {
  // ── Dashboard ─────────────────────────────────────────────────────────────
  dashboard_title: string;
  dashboard_subtitle: string;
  kpi_total_book_premium: string;
  kpi_total_est_earned: string;
  kpi_total_actual_earned: string;
  kpi_total_variance: string;
  chart_policy_status_title: string;
  chart_risk_distribution_title: string;
  chart_state_risk_title: string;
  chart_active_policies: string;
  chart_cancelled_policies: string;
  risk_high: string;
  risk_medium: string;
  risk_low: string;
  risk_unassigned: string;
  target_variance_title: string;
  target_variance_policies_above: string;
  target_variance_total_above: string;

  // ── Policies list ─────────────────────────────────────────────────────────
  policies_title: string;
  col_policy_number: string;
  col_insured_name: string;
  col_state: string;
  col_effective_date: string;
  col_policy_status: string;
  col_est_premium: string;
  col_variance_amount: string;
  col_variance_pct: string;
  col_risk_level: string;
  col_audit_status: string;
  filter_all_statuses: string;
  filter_all_risk: string;
  pagination_of: string;
  pagination_rows: string;

  // ── Policy detail — meta card ─────────────────────────────────────────────
  policy_detail_title: string;
  meta_policy_number: string;
  meta_insured: string;
  meta_fein: string;
  meta_state: string;
  meta_effective: string;
  meta_expiration: string;
  meta_cancellation: string;
  meta_policy_status: string;
  meta_payment_freq: string;
  meta_owner_status: string;
  meta_audit_status: string;
  meta_total_est_payroll: string;

  // ── Policy detail — tabs ──────────────────────────────────────────────────
  tab_summary: string;
  tab_missing_payrolls: string;
  tab_zero_payrolls: string;
  tab_ai_narrative: string;

  // ── Summary tab — premium variance ───────────────────────────────────────
  pv_section_title: string;
  pv_est_premium: string;
  pv_actual_premium: string;
  pv_variance_amount: string;
  pv_variance_pct: string;

  // ── Summary tab — payroll variance ───────────────────────────────────────
  pvp_section_title: string;
  pvp_est_payroll: string;
  pvp_actual_reported: string;
  pvp_reported_over_under: string;
  pvp_reported_pct: string;
  pvp_actual_classified: string;
  pvp_classified_over_under: string;
  pvp_classified_pct: string;

  // ── Summary tab — payroll metrics pills ───────────────────────────────────
  pm_actual_received: string;
  pm_zero_payrolls: string;
  pm_expected_submissions: string;
  pm_missing_payrolls: string;
  pm_submission_rate: string;

  // ── Class code variance ───────────────────────────────────────────────────
  pvc_class_code: string;
  pvc_description: string;
  pvc_state: string;
  pvc_est_payroll: string;
  pvc_actual_reported: string;
  pvc_reported_over_under: string;
  pvc_reported_pct: string;
  pvc_actual_classified: string;
  pvc_classified_over_under: string;
  pvc_classified_pct: string;

  // ── Zero / missing payroll tabs ───────────────────────────────────────────
  zp_policyholder: string;
  zp_policy_number: string;
  zp_state: string;
  zp_report_date: string;
  zp_frequency: string;
  mp_period_start: string;
  mp_period_end: string;
  mp_days_since: string;


  // ── Platform Admin ────────────────────────────────────────────────────────
  platform_dashboard_title: string;
  platform_tenants_title: string;
  platform_carriers_title: string;
  platform_users_title: string;
  platform_stat_active_tenants: string;
  platform_stat_total_carriers: string;
  platform_stat_total_users: string;
  platform_stat_tenant_carrier_pairs: string;
  platform_col_slug: string;
  platform_col_name: string;
  platform_col_type: string;
  platform_col_status: string;
  platform_col_carrier_count: string;
  platform_col_actions: string;
  platform_col_email: string;
  platform_col_role: string;
  platform_col_tenant: string;
  platform_btn_new_tenant: string;
  platform_btn_new_carrier: string;
  platform_btn_activate: string;
  platform_btn_save_draft: string;
  platform_btn_back: string;
  platform_btn_next: string;
  platform_wizard_step1: string;
  platform_wizard_step2: string;
  platform_wizard_step3: string;
  platform_wizard_step4: string;
  platform_field_tenant_name: string;
  platform_field_subdomain: string;
  platform_field_tenant_type: string;
  platform_subdomain_preview: string;
  platform_subdomain_taken: string;
  platform_subdomain_reserved: string;
  platform_subdomain_immutable_note: string;
  platform_field_admin_first: string;
  platform_field_admin_last: string;
  platform_field_admin_email: string;
  platform_field_invite_toggle: string;
  platform_provisioning_schema: string;
  platform_provisioning_migrations: string;
  platform_provisioning_seeding: string;
  platform_provisioning_keycloak: string;

  // ── Organization Settings ─────────────────────────────────────────────────
  org_settings_title: string;
  org_tab_profile: string;
  org_tab_contacts: string;
  org_tab_branding: string;
  org_field_display_name: string;
  org_field_legal_name: string;
  org_field_address_line1: string;
  org_field_address_line2: string;
  org_field_city: string;
  org_field_state: string;
  org_field_zip: string;
  org_contact_primary: string;
  org_contact_secondary: string;
  org_field_contact_name: string;
  org_field_contact_email: string;
  org_field_contact_phone: string;
  org_branding_logo: string;
  org_branding_logo_hint: string;
  org_branding_brand_color: string;
  org_branding_brand_color_hint: string;
  org_branding_upload_btn: string;
  org_branding_drag_drop: string;
  org_btn_save: string;
  org_save_success: string;

  // ── User Management ───────────────────────────────────────────────────────
  users_title: string;
  users_btn_create: string;
  users_col_email: string;
  users_col_name: string;
  users_col_role: string;
  users_col_onboarding: string;
  users_col_actions: string;
  users_role_auditor: string;
  users_role_reviewer: string;
  users_role_tenant_admin: string;
  users_role_super_admin: string;
  users_field_first_name: string;
  users_field_last_name: string;
  users_field_email: string;
  users_field_role: string;
  users_create_title: string;
  users_edit_title: string;
  users_deactivate_confirm: string;
  users_btn_deactivate: string;
  users_btn_cancel: string;

  // ── Onboarding Wizard ─────────────────────────────────────────────────────
  onboarding_title: string;
  onboarding_step1: string;
  onboarding_step2: string;
  onboarding_step3: string;
  onboarding_step4: string;
  onboarding_step5: string;
  onboarding_s1_title: string;
  onboarding_s2_title: string;
  onboarding_s3_title: string;
  onboarding_s4_title: string;
  onboarding_s5_title: string;
  onboarding_s5_complete_msg: string;
  onboarding_btn_continue: string;
  onboarding_btn_prev: string;
  onboarding_btn_finish: string;
  onboarding_carrier_config_status: string;
  onboarding_carrier_not_configured: string;
  // ── Shared ────────────────────────────────────────────────────────────────
  na_label: string;
  engine_off_notice: string;
  loading: string;
  error_generic: string;
  no_data: string;
}

export const DEFAULT_LABELS: LabelMap = {
  // Dashboard
  dashboard_title: "Audit Dashboard",
  dashboard_subtitle: "Workers Compensation Premium Audit Overview",
  kpi_total_book_premium: "Total Book Premium",
  kpi_total_est_earned: "Est. Earned Premium",
  kpi_total_actual_earned: "Actual Earned Premium",
  kpi_total_variance: "Total Variance",
  chart_policy_status_title: "Policy Status",
  chart_risk_distribution_title: "Risk Distribution",
  chart_state_risk_title: "Policies by State & Risk",
  chart_active_policies: "Active",
  chart_cancelled_policies: "Cancelled",
  risk_high: "High",
  risk_medium: "Medium",
  risk_low: "Low",
  risk_unassigned: "Unassigned",
  target_variance_title: "Policies Above 30% Variance Threshold",
  target_variance_policies_above: "Policies Above Threshold",
  target_variance_total_above: "Total Variance Above Threshold",

  // Policies list
  policies_title: "Policies",
  col_policy_number: "Policy Number",
  col_insured_name: "Insured",
  col_state: "State",
  col_effective_date: "Effective Date",
  col_policy_status: "Status",
  col_est_premium: "Est. Premium",
  col_variance_amount: "Variance $",
  col_variance_pct: "Variance %",
  col_risk_level: "Risk",
  col_audit_status: "Audit Status",
  filter_all_statuses: "All Statuses",
  filter_all_risk: "All Risk Levels",
  pagination_of: "of",
  pagination_rows: "rows",

  // Policy detail — meta card
  policy_detail_title: "Policy Detail",
  meta_policy_number: "Policy Number",
  meta_insured: "Insured Name",
  meta_fein: "FEIN",
  meta_state: "State",
  meta_effective: "Effective Date",
  meta_expiration: "Expiration Date",
  meta_cancellation: "Cancellation Date",
  meta_policy_status: "Policy Status",
  meta_payment_freq: "Payment Frequency",
  meta_owner_status: "Owner Status",
  meta_audit_status: "Audit Status",
  meta_total_est_payroll: "Total Est. Payroll",

  // Tabs
  tab_summary: "Summary",
  tab_missing_payrolls: "Missing Payrolls",
  tab_zero_payrolls: "Zero Payrolls",
  tab_ai_narrative: "AI Narrative",

  // Premium variance
  pv_section_title: "Premium Variance",
  pv_est_premium: "Est. Premium",
  pv_actual_premium: "Actual Premium",
  pv_variance_amount: "Variance Amount",
  pv_variance_pct: "Variance %",

  // Payroll variance policy
  pvp_section_title: "Payroll Variance",
  pvp_est_payroll: "Est. Payroll",
  pvp_actual_reported: "Actual Reported",
  pvp_reported_over_under: "Reported Over / Under",
  pvp_reported_pct: "Reported %",
  pvp_actual_classified: "Actual Classified",
  pvp_classified_over_under: "Classified Over / Under",
  pvp_classified_pct: "Classified %",

  // Payroll metrics pills
  pm_actual_received: "Received",
  pm_zero_payrolls: "Zero Payrolls",
  pm_expected_submissions: "Expected",
  pm_missing_payrolls: "Missing",
  pm_submission_rate: "Submit Rate",

  // Class code variance
  pvc_class_code: "Class Code",
  pvc_description: "Description",
  pvc_state: "State",
  pvc_est_payroll: "Est. Payroll",
  pvc_actual_reported: "Actual Reported",
  pvc_reported_over_under: "Reported Δ",
  pvc_reported_pct: "Reported %",
  pvc_actual_classified: "Actual Classified",
  pvc_classified_over_under: "Classified Δ",
  pvc_classified_pct: "Classified %",

  // Zero / missing payroll
  zp_policyholder: "Policyholder",
  zp_policy_number: "Policy #",
  zp_state: "State",
  zp_report_date: "Report Date",
  zp_frequency: "Frequency",
  mp_period_start: "Period Start",
  mp_period_end: "Period End",
  mp_days_since: "Days Since Last",


  // Platform Admin
  platform_dashboard_title: "Platform Administration",
  platform_tenants_title: "Tenants",
  platform_carriers_title: "Carriers",
  platform_users_title: "Platform Users",
  platform_stat_active_tenants: "Active Tenants",
  platform_stat_total_carriers: "Total Carriers",
  platform_stat_total_users: "Total Users",
  platform_stat_tenant_carrier_pairs: "Tenant-Carrier Pairs",
  platform_col_slug: "Slug",
  platform_col_name: "Name",
  platform_col_type: "Type",
  platform_col_status: "Status",
  platform_col_carrier_count: "Carriers",
  platform_col_actions: "Actions",
  platform_col_email: "Email",
  platform_col_role: "Role",
  platform_col_tenant: "Tenant",
  platform_btn_new_tenant: "New Tenant",
  platform_btn_new_carrier: "Add Carrier",
  platform_btn_activate: "Activate",
  platform_btn_save_draft: "Save as Draft",
  platform_btn_back: "Back",
  platform_btn_next: "Next",
  platform_wizard_step1: "Tenant Details",
  platform_wizard_step2: "Admin User",
  platform_wizard_step3: "Carrier Assignment",
  platform_wizard_step4: "Review & Activate",
  platform_field_tenant_name: "Tenant Name",
  platform_field_subdomain: "Subdomain",
  platform_field_tenant_type: "Tenant Type",
  platform_subdomain_preview: "Subdomain Preview",
  platform_subdomain_taken: "This subdomain is already taken.",
  platform_subdomain_reserved: "This subdomain is reserved.",
  platform_subdomain_immutable_note: "Cannot be changed after creation.",
  platform_field_admin_first: "First Name",
  platform_field_admin_last: "Last Name",
  platform_field_admin_email: "Admin Email",
  platform_field_invite_toggle: "Send invitation email",
  platform_provisioning_schema: "Creating schema…",
  platform_provisioning_migrations: "Applying migrations…",
  platform_provisioning_seeding: "Seeding data…",
  platform_provisioning_keycloak: "Configuring access…",

  // Organization Settings
  org_settings_title: "Organization Settings",
  org_tab_profile: "Profile",
  org_tab_contacts: "Contacts",
  org_tab_branding: "Branding",
  org_field_display_name: "Display Name",
  org_field_legal_name: "Legal Name",
  org_field_address_line1: "Address Line 1",
  org_field_address_line2: "Address Line 2",
  org_field_city: "City",
  org_field_state: "State",
  org_field_zip: "ZIP Code",
  org_contact_primary: "Primary Contact",
  org_contact_secondary: "Secondary Contact",
  org_field_contact_name: "Contact Name",
  org_field_contact_email: "Contact Email",
  org_field_contact_phone: "Contact Phone",
  org_branding_logo: "Organisation Logo",
  org_branding_logo_hint: "PNG, JPG, or SVG · Max 5 MB",
  org_branding_brand_color: "Brand Colour",
  org_branding_brand_color_hint: "6-character hex value (e.g. 4ade80)",
  org_branding_upload_btn: "Upload Logo",
  org_branding_drag_drop: "Drag and drop a file, or click to browse",
  org_btn_save: "Save Changes",
  org_save_success: "Changes saved successfully.",

  // User Management
  users_title: "User Management",
  users_btn_create: "Create User",
  users_col_email: "Email",
  users_col_name: "Name",
  users_col_role: "Role",
  users_col_onboarding: "Onboarding",
  users_col_actions: "Actions",
  users_role_auditor: "Auditor",
  users_role_reviewer: "Reviewer",
  users_role_tenant_admin: "Tenant Admin",
  users_role_super_admin: "Super Admin",
  users_field_first_name: "First Name",
  users_field_last_name: "Last Name",
  users_field_email: "Email Address",
  users_field_role: "Role",
  users_create_title: "Create User",
  users_edit_title: "Edit User",
  users_deactivate_confirm: "Are you sure you want to deactivate this user?",
  users_btn_deactivate: "Deactivate",
  users_btn_cancel: "Cancel",

  // Onboarding Wizard
  onboarding_title: "Welcome — Let's set up your organisation",
  onboarding_step1: "Organisation Profile",
  onboarding_step2: "Contacts",
  onboarding_step3: "Branding",
  onboarding_step4: "Carrier Overview",
  onboarding_step5: "Complete",
  onboarding_s1_title: "Tell us about your organisation",
  onboarding_s2_title: "Add your contact details",
  onboarding_s3_title: "Customise your branding",
  onboarding_s4_title: "Your assigned carriers",
  onboarding_s5_title: "You're all set!",
  onboarding_s5_complete_msg: "Your organisation is configured. You can update these settings anytime under Organisation Settings.",
  onboarding_btn_continue: "Continue",
  onboarding_btn_prev: "Previous",
  onboarding_btn_finish: "Go to Dashboard",
  onboarding_carrier_config_status: "Configuration Status",
  onboarding_carrier_not_configured: "Not configured",

  // Phase 3 — Audit Runner (AuditRunnerPage)
  audit_runner_title:         "Audit Runner",
  audit_runner_subtitle:      "Upload a carrier data file to begin the audit ingestion pipeline. The system will auto-map fields and require your approval before loading data.",
  upload_dropzone_text:       "Click to select or drag and drop",
  upload_dropzone_hint:       "XLSX files only (CSV and XML coming in Phase 4)",
  upload_dropzone_aria:       "Click or drag to select XLSX file",
  upload_no_file:             "Please select a file to upload.",
  upload_xlsx_only:           "Please upload an XLSX file.",
  upload_error:               "Upload failed. Please try again.",
  btn_uploading:              "Uploading…",
  btn_upload_and_map:         "Upload & Map Fields",
  format_coming_phase4:       "Coming in Phase 4",

  // Phase 3 — Field Mapping Review (FieldMappingReview)
  field_mapping_title:                 "Field Mapping Review",
  field_mapping_subtitle:              "Review the auto-mapped field proposals before approving ingestion. Adjust any LOW or UNMATCHED fields.",
  field_mapping_fields:                "fields",
  confidence_high:                     "HIGH",
  confidence_medium_low:               "MED/LOW",
  confidence_unmatched:                "UNMATCHED",
  col_source_field:                    "Source Field",
  col_source_sample:                   "Sample Value",
  col_proposed_target:                 "Target Column",
  col_transform:                       "Transform",
  col_exclude:                         "Exclude",
  mapping_unassigned:                  "— Unassigned —",
  mapping_session_missing:             "No mapping session found. Please re-upload the file.",
  mapping_load_error:                  "Failed to load field mapping.",
  mapping_admin_only:                  "Mapping approval requires Tenant Administrator access.",
  mapping_approve_disabled_tooltip:    "Assign or exclude all UNMATCHED fields before approving.",
  btn_back_to_upload:                  "Back to Upload",
  btn_reject_mapping:                  "Reject & Start Over",
  btn_approve_mapping:                 "Approve Mapping",
  btn_approving:                       "Approving…",

  // Phase 3 — Ingestion Progress (IngestionProgress)
  progress_title:           "Ingestion Progress",
  progress_subtitle:        "Run",
  progress_mapping_approved:"Mapping approved — preparing ingestion…",
  progress_processing:      "Processing data — this may take a moment…",
  progress_complete:        "Ingestion complete.",
  progress_partial:         "Ingestion partially completed.",
  progress_failed:          "Ingestion failed.",
  progress_waiting:         "Waiting for ingestion to start…",
  progress_rows_loaded:     "Rows loaded:",
  progress_rows_skipped:    "Skipped:",
  progress_no_run_id:       "No run ID found. Please start a new upload.",
  progress_poll_error:      "Could not reach server:",
  btn_run_calc_engine:      "Run Calculation Engine",
  btn_try_again:            "Try Again",

  // Phase 3 — Carrier Config Hub (CarrierConfigHub)
  carrier_config_title:           "Carrier Configuration",
  carrier_config_tab_data_sources:"Data Sources",
  carrier_config_tab_field_map:   "Field Mapping",
  carrier_config_tab_calc_engine: "Calculation Engine",
  carrier_config_tab_labels:      "Labels & Display",
  carrier_config_tab_report:      "Report Template",
  carrier_config_tab_theme:       "Theme",
  carrier_config_coming_phase4:   "Coming in Phase 4",
  carrier_config_coming_phase5:   "Coming in Phase 5",
  carrier_config_coming_phase6:   "Coming in Phase 6",

  // Phase 3 — Calc Engine Toggle (CalcEngineToggle)
  calc_engine_toggle_label:       "Calculation Engine",
  calc_engine_on_label:           "ON",
  calc_engine_off_label:          "OFF",
  calc_engine_off_warning:        "Engine is OFF. All engine-derived fields (Variance %, Risk Level) will show N/A on the dashboard.",
  calc_engine_saving:             "Saving…",

  // Phase 3 — Calc Rules List (CalcRulesList)
  calc_rules_title:               "Calculation Rules",
  calc_rules_subtitle:            "LOCKED rules use built-in Python logic. EDITABLE rules use configurable expressions evaluated at run time.",
  col_rule_key:                   "Rule Key",
  col_rule_type:                  "Type",
  col_expression:                 "Expression",
  col_rule_status:                "Status",
  col_actions:                    "Actions",
  rule_locked_tooltip:            "This rule is locked and cannot be edited.",
  btn_edit:                       "Edit",
  btn_save:                       "Save",
  btn_cancel:                     "Cancel",
  btn_submit_review:              "Submit for Review",
  btn_approve_activate:           "Approve & Activate",
  btn_revert_draft:               "Revert to Draft",
  btn_deactivate:                 "Deactivate",
  btn_test_expression:            "Test",
  btn_ai_suggest:                 "AI Suggest",
  btn_history:                    "History",
  rule_history_title:             "Rule Change History",
  rule_test_result_label:         "Test result:",
  rule_expression_placeholder:    "Enter expression (e.g. abs(variance_pct) > 30)",
  rule_ai_suggest_loading:        "Generating suggestion…",

  // Shared
  na_label: "N/A",
  engine_off_notice: "Calculation engine is off. Engine-derived fields show N/A.",
  loading: "Loading…",
  error_generic: "Something went wrong. Please try again.",
  no_data: "No data available.",
};

export function useLabels(): LabelMap {
  // Phase 3: TODO — merge carrier_ui_labels overrides from API
  return DEFAULT_LABELS;
}
