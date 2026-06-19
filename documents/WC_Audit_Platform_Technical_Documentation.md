# Workers' Compensation Premium Audit Platform — Technical Documentation

> **Version:** Post-Phase 7D (Phase 7B, 7C, 7D complete)
> **Architecture Reference:** V9.0 + Theme Addendum A
> **Repository:** https://github.com/Sudheer7183/workmencompMerged
> **Naming Note:** All references use "the Platform" or "the Audit Platform."

---

## Table of Contents

1. [Executive Overview](#1-executive-overview)
2. [Architecture Overview](#2-architecture-overview)
3. [Technology Stack](#3-technology-stack)
4. [Repository Structure](#4-repository-structure)
5. [Database Schema](#5-database-schema)
6. [RBAC & Security Model](#6-rbac--security-model)
7. [Platform Features — End-to-End Flow](#7-platform-features--end-to-end-flow)
8. [Module-by-Module Code Documentation](#8-module-by-module-code-documentation)
9. [API Reference](#9-api-reference)
10. [Input File Specifications](#10-input-file-specifications)
11. [Deployment Guide](#11-deployment-guide)
12. [Testing Strategy](#12-testing-strategy)
13. [Known Gaps & Future Work](#13-known-gaps--future-work)

---

## 1. Executive Overview

### 1.1 Platform Purpose

The Audit Platform is a multi-tenant, carrier-agnostic SaaS application for Workers' Compensation (WC) premium auditing. It is used by insurance carriers, audit organizations, payroll companies, and brokers to ingest periodic payroll data from insured entities, compare actual payroll against estimated payroll, compute premium variance, and produce audit-grade reports.

### 1.2 The Problem It Solves

Workers' Compensation insurance premiums are initially estimated based on projected payroll. At the end of each policy period, an audit is conducted to determine the actual payroll. If actual payroll exceeds the estimate, additional premium is owed; if it is less, a refund may apply. This comparison — actual vs. estimated payroll, and the resulting premium variance — is the core calculation the Platform automates.

Without this platform, auditors must manually reconcile XLSX payroll reports, XML policy exports, and audit summary files — a slow, error-prone process with no standardised workflow. The Platform replaces that with a structured pipeline: upload files, approve field mappings, run calculations, review exceptions, generate reports.

### 1.3 Deployment Model

The Platform is a multi-tenant SaaS application:

- **Multi-tenancy:** Single PostgreSQL database, one schema per tenant (`tenant_{slug}`). Each tenant is a separate organization (insurer, broker, or audit firm) with its own users, carriers, configuration, and data.
- **Subdomain routing:** Each tenant accesses the platform at its own subdomain (e.g., `demo.platform.com`). The `TenantMiddleware` resolves the subdomain to the correct tenant schema on every request.
- **Multi-carrier:** Within each tenant, data is partitioned further by `carrier_id`. A single tenant may administer multiple insurance carriers.

### 1.4 End-to-End Flow Summary

A SUPER_ADMIN provisions a tenant, creating its PostgreSQL schema via Alembic migration and seeding calculation rules. The TENANT_ADMIN completes a 5-step onboarding wizard and configures each assigned carrier through a 6-tab (post-Phase 7C: 7-tab) Carrier Configuration Hub. An AUDITOR uploads payroll data files (XLSX, CSV, or XML). The platform auto-maps file columns to canonical database columns using a 4-pass confidence-scoring algorithm, then presents the mapping for mandatory TENANT_ADMIN approval before any data is written to fact tables. Once approved, the ingestion pipeline processes the data row by row. The calculation engine then evaluates 22 configurable rules (using the `simpleeval` sandbox) to produce variance, risk, and payroll metrics. The AI Narrative Service calls the configured LLM provider (defaulting to Anthropic Claude) to generate a human-readable audit narrative per policy. Reports are generated asynchronously (PDF or Excel) and delivered via pre-signed S3 URLs.

---

## 2. Architecture Overview

### 2.1 Six-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Presentation                                         │
│  React 18 + TypeScript SPA (Vite)                               │
│  DM Sans + DM Mono fonts · CSS custom property token system     │
│  Feature-driven modules · useLabels() · useTheme()              │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/JSON over Axios
┌──────────────────────────▼──────────────────────────────────────┐
│  LAYER 2 — API Gateway                                          │
│  FastAPI 0.115+ · TenantMiddleware · Keycloak RS256 JWT auth    │
│  CORS · Rate-limiting (Redis) · Structured logging (structlog)  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Pydantic v2 validated
┌──────────────────────────▼──────────────────────────────────────┐
│  LAYER 3 — Service Layer                                        │
│  AuditCalculationService · IngestionService · AutoMappingService│
│  AInarrativeService · ReportService · CleanupService            │
│  TenantProvisioningService · LLMClientFactory                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LAYER 4 — Rules Engine                                         │
│  simpleeval 0.9.13 · SAFE_NAMES namespace · 22 calc rules       │
│  LOCKED (10) + EDITABLE (12) · DRAFT→PENDING_REVIEW→ACTIVE      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LAYER 5 — Data Access                                          │
│  SQLAlchemy 2.0 async ORM · Repository pattern                  │
│  search_path scoped per-request to tenant_{slug}               │
│  carrier_id filter on every query                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  LAYER 6 — Infrastructure                                       │
│  PostgreSQL 16 (multi-schema) · Redis 7 (cache + rate-limit)    │
│  S3-compatible object storage · Keycloak / Microsoft Entra ID   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Multi-Tenancy Architecture

| Aspect | Detail |
|---|---|
| **Strategy** | Single PostgreSQL database, one schema per tenant: `tenant_{slug}` |
| **Isolation boundary** | The PostgreSQL schema is the isolation boundary. No `tenant_id` column exists on tenant-scoped tables. |
| **Sub-dimension** | Within a tenant schema, `carrier_id` is the data partition key. Every fact table, configuration table, and most query filters include `carrier_id`. |
| **Subdomain routing** | `TenantMiddleware` extracts the subdomain from the `Host` header, looks up `public.tenants` by slug, validates `status = ACTIVE`, and attaches the tenant record to `request.state.tenant`. |
| **Session scoping** | `get_db()` reads `request.state.tenant.schema_name` and executes `SET search_path TO "{schema}", public` before yielding the async session. All queries in that request execute inside the tenant schema automatically. |
| **JWT scoping** | The JWT `tenant_slug` claim must match the subdomain-resolved tenant. `verify_tenant()` enforces this on every protected endpoint. SUPER_ADMIN tokens have `tenant_slug = null` and are exempt from this check. |

### 2.3 Infrastructure Components

| Component | Version | Role |
|---|---|---|
| PostgreSQL | 16 | Primary data store. Multi-schema tenancy. |
| Redis | 7.2+ | JWKS cache (TTL 1 hour), calc rules cache (TTL 5 min), labels cache (TTL 5 min), theme cache (TTL 5 min), rate-limiting. |
| S3-compatible storage | Any (AWS S3 / MinIO) | File uploads in production. Pre-signed URLs for report downloads. |
| Keycloak / Microsoft Entra ID | Keycloak 24+ | RS256 JWT issuance. JWKS endpoint. Realm-level role and tenant_slug claims. |

### 2.4 Key Architectural Decisions

#### Decision 1 — Single Database, Multiple Schemas

- **Decision:** One PostgreSQL database with a schema per tenant (`tenant_{slug}`), rather than separate databases or a single schema with `tenant_id` columns.
- **Rationale:** Schema-per-tenant provides strong structural isolation without the operational overhead of managing separate database connections per tenant. It allows Alembic to run the same migration file across all schemas.
- **Trade-off accepted:** Schema proliferation requires iterating all tenant schemas in Alembic's `env.py`. Cross-tenant analytics require explicit schema-qualified queries.

#### Decision 2 — Alembic Multi-Schema Migration Strategy

- **Decision:** `alembic/env.py` applies migrations to the `public` schema first, then iterates all active `tenant_{slug}` schemas. The `_s()` helper inside migration files reads the current target schema.
- **Rationale:** A single migration file governs both public and tenant schema structures, ensuring they stay in sync.
- **Trade-off accepted:** New tenant provisioning requires running `alembic -x target_schema=tenant_{slug} upgrade head` as a subprocess from `TenantProvisioningService`. This couples provisioning to Alembic.

#### Decision 3 — Mandatory Field-Mapping Approval Gate

- **Decision:** Ingestion does NOT write to fact tables until a TENANT_ADMIN explicitly approves the field mapping. This is a hard gate — it cannot be bypassed even when all mappings are HIGH confidence.
- **Rationale:** Data quality in WC auditing is critical. A bad column mapping silently corrupts all downstream calculations and reports.
- **Trade-off accepted:** Adds an extra step for every ingestion run. AUDITOR cannot complete an ingestion without TENANT_ADMIN involvement.

#### Decision 4 — Three-Level Calculation Mode Hierarchy

- **Decision:** Calculation mode is resolved from three levels: tenant default (`tenant_calc_config.use_calculation_engine`) → carrier default (`carrier_calc_config.use_calculation_engine`) → per-run override (`ingestion_runs.use_calculation_engine`). More specific overrides the less specific.
- **Rationale:** Different carriers within the same tenant may have different calculation needs. Individual runs may need one-off overrides without changing the default.
- **Trade-off accepted:** Increased complexity in `resolve_effective_mode()`. Per-run overrides can cause unexpected behavior if not documented.

#### Decision 5 — Two-Step Self-Approval for Calculation Rules

- **Decision:** A TENANT_ADMIN creates a rule edit (DRAFT), submits it for review (PENDING_REVIEW), then performs a separate "Approve & Activate" action (ACTIVE). Both steps may be performed by the same user but must be separate UI actions.
- **Rationale:** Satisfies the review-and-approval requirement without requiring a second person. Prevents accidental activation of untested expressions.
- **Trade-off accepted:** A single admin can effectively self-approve, which limits the control value. The audit log records all transitions.

#### Decision 6 — Carrier-Agnostic Design

- **Decision:** All carrier-specific configuration is database-driven (labels, calculation rules, field maps, themes, LLM config). No carrier-specific logic is hardcoded.
- **Rationale:** The platform must support any number of carriers without code changes.
- **Trade-off accepted:** Increased complexity in all configuration management screens. Carrier configuration must be set up before meaningful ingestion is possible.

#### Decision 7 — CSS Custom Property Token Architecture

- **Decision:** All visual colors flow through exactly 13 CSS custom properties (`--bg`, `--surface`, `--surface2`, `--border`, `--text`, `--muted`, `--brand`, `--brand-dark`, `--accent`, `--green`, `--amber`, `--red`, `--blue`). No hardcoded hex values in any component. Tokens are written exclusively by `useTheme()` on `:root`.
- **Rationale:** Theme switching (including tenant branding and user preferences) requires only changing the token values, not touching any component.
- **Trade-off accepted:** Developers must learn the token vocabulary. Color-specific designs must be expressible through the 13-token palette.

#### Decision 8 — `useLabels()` for All Display Strings

- **Decision:** All user-visible strings in JSX are retrieved via `useLabels()`. No hardcoded strings in component markup. The hook merges carrier-configured overrides onto the `DEFAULT_LABELS` registry. Keys in `DEFAULT_LABELS` are immutable — they may never be changed after first commit.
- **Rationale:** TENANT_ADMIN can customise every label per carrier without code changes.
- **Trade-off accepted:** Adding a new string requires adding a key to `DEFAULT_LABELS` first.

#### Decision 9 — Subdomain-Based Tenant Resolution

- **Decision:** Tenant identity is established from the subdomain of the `Host` request header, not from a URL path prefix.
- **Rationale:** Clean URL structure (`demo.platform.com` vs `platform.com/tenant/demo`). Each tenant's users see only their subdomain.
- **Trade-off accepted:** Requires wildcard DNS and wildcard SSL certificate in production. Local development requires `/etc/hosts` or a proxy.

#### Decision 10 — `carriers.ai_narrative_enabled` Retained but Not Evaluated (Post-Phase 7C)

- **Decision:** The `carriers.ai_narrative_enabled` column exists in `public.carriers` for backward compatibility and historical audit purposes, but `AInarrativeService` no longer reads it to gate narrative generation.
- **Rationale:** Phase 7C introduced carrier-scoped LLM config. The enable/disable semantics are now implicit — a carrier with no LLM config falls back to the platform default, and a carrier whose config is `is_active = FALSE` will also fall through to the platform Anthropic key. An explicit enable flag on the carrier table adds confusion without adding control.
- **Trade-off accepted:** Historical data in `ai_narrative_enabled` no longer has operational effect, which may surprise operators who set it.

---

## 3. Technology Stack

### 3.1 Backend

| Component | Version | Notes |
|---|---|---|
| Python | 3.12+ | `from __future__ import annotations` on every file |
| FastAPI | 0.115+ | Async ASGI framework |
| Pydantic | v2 | `pydantic-settings` for env config; `ConfigDict(from_attributes=True)` on ORM schemas |
| SQLAlchemy | 2.0 async | `Mapped[T]` + `mapped_column()` syntax only; no legacy `Column()` |
| asyncpg | 0.30+ | PostgreSQL async driver |
| Alembic | 1.14+ | Multi-schema migration strategy |
| simpleeval | 0.9.13 | Safe expression evaluator for calc rules; `EvalWithCompoundTypes` used exclusively |
| difflib | Python stdlib | Fuzzy column name matching in `AutoMappingService` |
| httpx | 0.27+ | Async HTTP client (Anthropic API calls) |
| structlog | 24+ | Structured JSON logging |
| openpyxl | 3.1+ | XLSX ingestion and Excel report generation |
| WeasyPrint | 62+ | PDF report generation from Jinja2/HTML templates |
| Jinja2 | 3.1+ | PDF report templates |
| python-jose | 3.3+ | RS256 JWT decoding |
| cryptography (Fernet) | Latest | AES-256 encryption of LLM API keys in `carrier_llm_config` |
| anthropic | Latest | Anthropic SDK for AI narrative generation |
| openai | 1.0+ | OpenAI/Azure OpenAI/Ollama/OpenAI-compatible LLM clients |
| google-generativeai | 0.8.0+ | Google AI (Gemini) LLM client |
| redis (aioredis) | Latest | Async Redis client for caching |

### 3.2 Frontend

| Component | Version | Notes |
|---|---|---|
| React | 18.3+ | Functional components + hooks only |
| TypeScript | 5.4+ strict | `strict: true` in `tsconfig.json`; no `any` permitted |
| Vite | 5.3+ | Build tool and dev server |
| TanStack Query | v5 | Server-state management; all API calls through query/mutation hooks |
| Recharts | 2.12+ | Chart components (dashboard KPI charts) |
| Axios | Latest | HTTP client; all API calls go through an `axios` instance (no raw `fetch()`) |
| @dnd-kit/core | Latest | Drag-and-drop for the Expression Field Builder (Phase 7D) |
| @dnd-kit/sortable | Latest | Sortable drag-and-drop for expression token canvas |
| JSZip | Latest | Client-side ZIP extraction in `BulkUploadPage` |
| DM Sans | Google Fonts | Weights 300/400/500/600/700 |
| DM Mono | Google Fonts | Weights 400/500 |
| Tailwind CSS | 3.4+ | Utility classes; all colors via CSS variables (no hardcoded palette) |

### 3.3 Infrastructure

| Component | Version | Notes |
|---|---|---|
| PostgreSQL | 16 | Schema-per-tenant; asyncpg driver |
| Redis | 7.2+ | JWKS cache, calc rules cache, labels cache, theme cache, rate-limiting |
| S3-compatible storage | Any | AWS S3 / MinIO; pre-signed URLs for uploads and report downloads |
| Keycloak | 24+ | Primary auth provider; RS256 JWTs; wildcard subdomain redirect URIs |
| Microsoft Entra ID | — | Alternative auth provider (same RS256 JWT contract) |
| Docker Compose | v2 | Local/staging environment |
| Kubernetes | 1.30+ | Production deployment |
| nginx | 1.26+ | Wildcard subdomain routing in production |

### 3.4 Testing

| Component | Version | Notes |
|---|---|---|
| Playwright | Latest | E2E test suite; 25 specs (22 baseline + 3 Phase 7BCD additions) |
| pytest | Latest | Backend unit and integration tests |
| pytest-asyncio | Latest | Async test support |
| Vitest / Jest | Latest | Frontend unit and component tests |
| mypy | Latest | Backend static type checking in CI |

---

## 4. Repository Structure

```
/
├── backend/                          # FastAPI Python 3.12 application
│   ├── app/
│   │   ├── api/                      # FastAPI routers, security, shared deps
│   │   │   ├── security.py           # JWT decoding, RS256 Keycloak verification, dev bypass
│   │   │   ├── deps.py               # Shared FastAPI dependencies (get_db, pagination)
│   │   │   └── v1/                   # Versioned API routers
│   │   │       ├── platform.py       # SUPER_ADMIN routes: tenants, carriers, platform themes
│   │   │       ├── tenant_admin.py   # TENANT_ADMIN: org settings, user management
│   │   │       ├── carrier_config.py # Carrier config hub: calc rules, engine mode, field maps
│   │   │       ├── data_sources.py   # Data source and field map CRUD (soft-delete)
│   │   │       ├── ingestion.py      # Upload, mapping gate, run status, rollback
│   │   │       ├── dashboard.py      # KPI aggregations, chart data
│   │   │       ├── policies.py       # Policy list, policy detail (all tabs)
│   │   │       ├── reports.py        # Report generation, async job status, download URL
│   │   │       ├── cleanup.py        # Database cleanup: preview, execute, history
│   │   │       ├── labels.py         # UI label overrides CRUD and resolution
│   │   │       ├── themes.py         # Theme CRUD, resolved theme, user preference
│   │   │       └── llm_config.py     # Carrier-scoped LLM provider configuration
│   │   ├── services/                 # Business logic — pure Python service classes
│   │   │   ├── audit_calculation_service.py   # 22-rule calc engine (simpleeval + locked)
│   │   │   ├── ingestion_service.py           # File parse, fact table writes, post-approval
│   │   │   ├── auto_mapping_service.py        # 4-pass field mapping confidence scoring
│   │   │   ├── ai_narrative_service.py        # LLM narrative generation with fallback chain
│   │   │   ├── llm_client_factory.py          # LLM provider factory (Anthropic/OpenAI/etc.)
│   │   │   ├── llm_clients/                   # Per-provider client classes
│   │   │   │   ├── anthropic_client.py
│   │   │   │   ├── openai_client.py
│   │   │   │   ├── azure_openai_client.py
│   │   │   │   ├── google_client.py
│   │   │   │   ├── ollama_client.py
│   │   │   │   └── openai_compatible_client.py
│   │   │   ├── llm_key_vault_service.py       # Fernet AES-256 encrypt/decrypt for API keys
│   │   │   ├── report_service.py              # PDF (WeasyPrint) + Excel (openpyxl) reports
│   │   │   ├── cleanup_service.py             # Monthly data cleanup, cleanup_runs log
│   │   │   └── tenant_provisioning_service.py # Schema creation, seeding, add_carrier_to_tenant
│   │   ├── repositories/             # SQLAlchemy 2.0 async data access layer
│   │   │   ├── policy_repository.py
│   │   │   ├── ingestion_repository.py
│   │   │   ├── carrier_config_repository.py
│   │   │   ├── calc_rules_repository.py
│   │   │   ├── label_repository.py
│   │   │   ├── theme_repository.py
│   │   │   └── platform_repository.py
│   │   ├── models/                   # SQLAlchemy ORM mapped classes
│   │   │   ├── public_schema.py      # Tenants, carriers, theme_definitions, class_codes
│   │   │   ├── tenant_users.py       # Tenant-scoped users table
│   │   │   ├── policies.py           # Policies, policyholders
│   │   │   ├── ingestion.py          # ingestion_runs, _errors, _skipped_rows, _rollbacks, _field_maps
│   │   │   ├── mapping.py            # field_mapping_sessions, field_mapping_proposals
│   │   │   ├── facts.py              # premium_variance, payroll_variance_policy/class, zero/missing_payroll
│   │   │   ├── config.py             # carrier_calc_config, tenant_calc_config, calc_rules, labels, themes
│   │   │   └── cleanup.py            # cleanup_runs
│   │   ├── schemas/                  # Pydantic v2 request/response models
│   │   │   ├── auth.py               # TokenPayload, Role enum
│   │   │   ├── tenant.py             # TenantCreateRequest, TenantResponse
│   │   │   ├── policies.py           # PolicyListResponse, PolicyDetailResponse, NarrativeSection
│   │   │   ├── ingestion.py          # UploadResponse, MappingSession, MappingProposal
│   │   │   ├── calc_rules.py         # CalcRuleResponse, RuleHistoryEntry
│   │   │   ├── reports.py            # ReportRequest, ReportJobResponse
│   │   │   └── platform_schemas.py   # TenantCreateRequest, CarrierResponse
│   │   ├── rules/                    # Rules engine support
│   │   │   └── safe_names.py         # SAFE_NAMES dict + FieldDescriptor registry
│   │   └── core/                     # Config, database session factory, Redis
│   │       ├── config.py             # pydantic-settings Settings class; all env vars
│   │       ├── database.py           # AsyncEngine factory, Base, initialise_db/dispose_db
│   │       └── redis.py              # Redis client init, cache helpers
│   ├── alembic/                      # Alembic migration environment
│   │   ├── env.py                    # Multi-schema env: public first, then all tenant_{slug}
│   │   └── versions/
│   │       ├── 0001_initial_schema.py     # Phase 1: all tables (public + tenant)
│   │       ├── 0002_phase2_tenant_mgmt.py # Phase 2: provisioning tables
│   │       ├── 0003_phase3_mapping_gate.py # Phase 3: field_mapping_sessions/proposals
│   │       ├── 0004_phase4_exceptions.py  # Phase 4: ingestion_errors, skipped_rows, rollbacks
│   │       ├── 0005_phase5_reports.py     # Phase 5: report_jobs
│   │       ├── 0006_phase6_config.py      # Phase 6: cleanup_runs, labels, themes, user_prefs
│   │       └── 0007_phase7_llm_config.py  # Phase 7C: carrier_llm_config
│   └── tests/                        # pytest unit + integration tests
├── frontend/                         # React 18 + TypeScript SPA
│   └── src/
│       ├── components/               # Shared, stateless atomic UI components
│       │   ├── NaIndicator.tsx       # Renders "N/A" for NULL engine-derived fields
│       │   ├── StatusBadge.tsx       # Risk/audit status colour badges
│       │   ├── ModeToggle.tsx        # Sun/moon theme mode toggle in nav bar
│       │   └── ...
│       ├── features/                 # Feature-driven modules
│       │   ├── dashboard/            # Dashboard KPI cards, charts, target variance
│       │   ├── policies/             # Policies list + 4-tab policy detail
│       │   ├── ingestion/            # AuditRunnerPage, BulkUploadPage, FieldMappingReview, IngestionProgress
│       │   ├── carrier-config/       # 7-tab Carrier Configuration Hub
│       │   │   └── components/
│       │   │       ├── CalcRulesList.tsx       # 22-rule editor with two-step approval
│       │   │       ├── ExpressionBuilder.tsx   # Phase 7D: drag-and-drop field token builder
│       │   │       ├── theme/ThemeEditor.tsx   # Theme editor with 13 token pickers + WCAG check
│   │   │       └── ai-config/AIConfigTab.tsx  # Phase 7C: carrier-scoped LLM config (Tab 7)
│   │   ├── administration/           # TENANT_ADMIN and SUPER_ADMIN screens
│   │   │   ├── platform-admin/       # SUPER_ADMIN: tenant list, tenant detail, TenantCreationWizard
│   │   │   ├── organization/         # TENANT_ADMIN: org settings, CarrierManagementPanel
│   │   │   └── database-cleanup/     # DatabaseCleanupPage
│   │   └── user-preferences/         # UserThemePicker in avatar dropdown
│   ├── hooks/                        # Global custom hooks
│   │   ├── useLabels.ts              # Label resolution: DB overrides merged onto DEFAULT_LABELS
│   │   ├── useTheme.ts               # Theme resolution: applies 13 CSS tokens to :root
│   │   ├── useTenantFromSubdomain.ts # Reads tenant slug from window.location.hostname
│   │   └── useCarrierCalcConfig.ts   # Carrier engine mode + calc rules state
│   ├── context/                      # React Contexts
│   │   ├── AuthContext.tsx           # Authenticated user, JWT, role
│   │   ├── TenantCarrierContext.tsx  # Active tenantSlug + carrierId selection
│   │   └── ThemeContext.tsx          # Theme preference state
│   ├── routes/                       # Routing configuration
│   │   ├── AppRouter.tsx             # All route definitions
│   │   └── ProtectedRoute.tsx        # Role-based route guard
│   ├── styles/                       # Centralised CSS files (mandatory structure)
│   │   ├── tokens.css                # CSS custom property declarations ONLY
│   │   ├── typography.css            # DM Sans + DM Mono imports, font scale
│   │   ├── layout.css                # Grid, max-width, breakpoints, padding scale
│   │   ├── components.css            # BEM component styles (all colors via var())
│   │   ├── utilities.css             # Atomic helpers: pos-val, neg-val, na-indicator
│   │   └── themes.css                # Theme contract documentation (values injected by useTheme)
│   └── utils/                        # Pure helper functions
│       ├── text_utils.ts             # normalise(), truncate()
│       └── bulkUploadUtils.ts        # File grouping, ZIP extraction
├── docker-compose.yml                # Service definitions: PostgreSQL, Redis, FastAPI, React
├── .env.example                      # All environment variable placeholders
└── README.md                         # Quick-start and project structure overview
```

---

## 5. Database Schema

### 5.1 Public Schema

The `public` schema is platform-wide and is never written to by tenant users.

#### `public.tenants`

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `tenant_id` | BIGSERIAL | NOT NULL | auto | Primary key |
| `slug` | TEXT | NOT NULL | — | URL-safe identifier; also the subdomain |
| `schema_name` | TEXT | NOT NULL | — | PostgreSQL schema name: `tenant_{slug}` |
| `display_name` | TEXT | NOT NULL | — | Human-readable tenant name |
| `status` | TEXT | NOT NULL | `'INACTIVE'` | `ACTIVE`, `INACTIVE`, `DELETED` |
| `tenant_type` | TEXT | NULL | — | `AUDIT_COMPANY`, `CARRIER`, `BROKER`, `PAYROLL_COMPANY` |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | Creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL | `now()` | Last update; auto-updated by trigger |
| `deleted_at` | TIMESTAMPTZ | NULL | — | Soft-delete timestamp |

Indexes: `uq_tenants_slug` (unique on `slug`), `uq_tenants_schema_name` (unique on `schema_name`).

#### `public.carriers`

| Column | Type | Nullable | Default | Description |
|---|---|---|---|---|
| `carrier_id` | BIGSERIAL | NOT NULL | auto | Primary key |
| `name` | TEXT | NOT NULL | — | Carrier display name |
| `slug` | TEXT | NOT NULL | — | URL-safe carrier identifier |
| `ai_narrative_enabled` | BOOLEAN | NOT NULL | TRUE | Retained for historical audit; not evaluated post-Phase 7C |
| `is_active` | BOOLEAN | NOT NULL | TRUE | Soft-delete flag |
| `created_at` | TIMESTAMPTZ | NOT NULL | `now()` | |

Indexes: `uq_carriers_slug` (unique on `slug`).

#### `public.tenant_carriers`

Join table linking tenants to their assigned carriers.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `tc_id` | BIGSERIAL | NOT NULL | Primary key |
| `tenant_id` | BIGINT | NOT NULL | FK → `public.tenants` |
| `carrier_id` | BIGINT | NOT NULL | FK → `public.carriers` |
| `is_active` | BOOLEAN | NOT NULL | Soft-delete; `FALSE` = carrier removed from tenant |
| `assigned_at` | TIMESTAMPTZ | NOT NULL | Assignment timestamp |

Unique constraint: `(tenant_id, carrier_id)`.

#### `public.theme_definitions`

System-level read-only themes. TENANT_ADMIN may not write here.

| Column | Type | Description |
|---|---|---|
| `theme_id` | BIGSERIAL | Primary key |
| `theme_name` | TEXT | e.g., "Default Dark" |
| `base_mode` | TEXT | `dark` or `light` |
| `is_system` | BOOLEAN | Always TRUE for this table |
| `bg` | TEXT | Hex without `#`, e.g. `0f1117` |
| `surface` | TEXT | |
| `surface2` | TEXT | |
| `border_col` | TEXT | |
| `text_primary` | TEXT | |
| `text_muted` | TEXT | |
| `brand` | TEXT | |
| `brand_dark` | TEXT | |
| `accent` | TEXT | |
| `color_green` | TEXT | |
| `color_amber` | TEXT | |
| `color_red` | TEXT | |
| `color_blue` | TEXT | |
| `created_at` | TIMESTAMPTZ | |

Seeded system themes (hex values):

| Theme | `--bg` | `--surface` | `--brand` | Mode |
|---|---|---|---|---|
| Default Dark | `0f1117` | `181c27` | `4ade80` | dark |
| Default Light | `f8fafc` | `ffffff` | `16a34a` | light |
| Corporate Dark | `0d1117` | `161b22` | `2563eb` | dark |
| Corporate Light | `f0f4f8` | `ffffff` | `1d4ed8` | light |

#### `public.class_codes`

Platform-wide WC class code reference data. Read-only at runtime.

| Column | Type | Description |
|---|---|---|
| `class_code_id` | BIGSERIAL | Primary key |
| `code` | TEXT | e.g., `8810` |
| `description` | TEXT | e.g., "Clerical Office Employees" |
| `state_code` | CHAR(2) | 2-letter state abbreviation |

---

### 5.2 Tenant Schema (`tenant_{slug}`)

All tables below exist within each active tenant's private schema.

#### `users`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `user_id` | BIGSERIAL | NOT NULL | Primary key |
| `keycloak_id` | TEXT | NOT NULL | Keycloak subject UUID |
| `email` | TEXT | NOT NULL | |
| `role` | TEXT | NOT NULL | `TENANT_ADMIN`, `AUDITOR`, `REVIEWER` |
| `is_active` | BOOLEAN | NOT NULL | Soft-delete |
| `onboarding_completed` | BOOLEAN | NOT NULL | FALSE until Step 5 of onboarding wizard |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

#### `policies`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `policy_id` | BIGSERIAL | NOT NULL | Primary key |
| `carrier_id` | BIGINT | NOT NULL | FK → `public.carriers` |
| `policy_number` | TEXT | NOT NULL | Carrier-assigned policy number |
| `policyholder_id` | BIGINT | NULL | FK → `policyholders` |
| `effective_date` | DATE | NULL | Policy period start |
| `expiration_date` | DATE | NULL | Policy period end |
| `audit_status` | TEXT | NOT NULL | `PENDING`, `IN_PROGRESS`, `COMPLETE`, `EXCEPTION` |
| `risk_level` | TEXT | NULL | `HIGH`, `MEDIUM`, `LOW` — engine-derived |
| `created_at` | TIMESTAMPTZ | NOT NULL | |

Unique: `(carrier_id, policy_number)`.

#### `policyholders`

| Column | Type | Description |
|---|---|---|
| `policyholder_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | |
| `name` | TEXT | Insured entity name |
| `state_code` | CHAR(2) | Primary operating state |
| `created_at` | TIMESTAMPTZ | |

#### `ingestion_runs`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `run_id` | BIGSERIAL | NOT NULL | Primary key |
| `carrier_id` | BIGINT | NOT NULL | |
| `source_id` | BIGINT | NULL | FK → `ingestion_sources` |
| `status` | TEXT | NOT NULL | `awaiting_mapping`, `mapping_approved`, `processing`, `complete`, `partial`, `failed`, `rolled_back` |
| `file_type` | TEXT | NOT NULL | `xlsx`, `csv`, `xml` |
| `original_filename` | TEXT | NULL | |
| `use_calculation_engine` | BOOLEAN | NULL | Per-run override; NULL = use carrier/tenant default |
| `field_mapping_session_id` | BIGINT | NULL | FK → `field_mapping_sessions` |
| `rows_ingested` | INTEGER | NULL | Count written to fact tables |
| `rows_skipped` | INTEGER | NOT NULL | `0` |
| `rows_failed` | INTEGER | NOT NULL | `0` |
| `raw_file_bytes` | BYTEA | NULL | Dev-mode fallback; NULL in production (S3 used) |
| `s3_key` | TEXT | NULL | S3 object key for production file storage |
| `uploaded_by` | TEXT | NOT NULL | JWT `sub` of uploader |
| `skip_on_error` | BOOLEAN | NOT NULL | TRUE = skip bad rows; FALSE = abort on first error |
| `started_at` | TIMESTAMPTZ | NOT NULL | |
| `completed_at` | TIMESTAMPTZ | NULL | |

#### `field_mapping_sessions`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `session_id` | BIGSERIAL | NOT NULL | Primary key |
| `ingestion_run_id` | BIGINT | NOT NULL | FK → `ingestion_runs` |
| `carrier_id` | BIGINT | NOT NULL | |
| `file_type` | TEXT | NOT NULL | |
| `status` | TEXT | NOT NULL | `PENDING_REVIEW`, `APPROVED`, `REJECTED` |
| `auto_mapped_count` | INTEGER | NOT NULL | |
| `flagged_count` | INTEGER | NOT NULL | LOW + MEDIUM confidence count |
| `unmatched_count` | INTEGER | NOT NULL | |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `reviewed_at` | TIMESTAMPTZ | NULL | |
| `reviewed_by` | TEXT | NULL | JWT `sub` of approver/rejecter |
| `approved_at` | TIMESTAMPTZ | NULL | |
| `approved_by` | TEXT | NULL | |

#### `field_mapping_proposals`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `proposal_id` | BIGSERIAL | NOT NULL | Primary key |
| `session_id` | BIGINT | NOT NULL | FK → `field_mapping_sessions` |
| `source_field` | TEXT | NOT NULL | Column name from uploaded file |
| `source_sample` | TEXT | NULL | First non-null sample value |
| `inferred_type` | TEXT | NOT NULL | `TEXT`, `NUMERIC`, `DATE`, `BOOLEAN`, `INTEGER` |
| `proposed_target` | TEXT | NULL | Canonical DB column name |
| `confidence` | TEXT | NOT NULL | `HIGH`, `MEDIUM`, `LOW`, `UNMATCHED` |
| `score` | NUMERIC(5,3) | NOT NULL | 0.000–1.000 |
| `transform_fn` | TEXT | NOT NULL | `as-is`, `date_mdy`, `cents_to_dollars`, etc. |
| `is_excluded` | BOOLEAN | NOT NULL | TRUE = field intentionally skipped |
| `match_reason` | TEXT | NULL | Human-readable explanation of confidence |

#### `ingestion_errors`

| Column | Type | Description |
|---|---|---|
| `error_id` | BIGSERIAL | Primary key |
| `run_id` | BIGINT | FK → `ingestion_runs` |
| `row_number` | INTEGER | Source file row number |
| `source_field` | TEXT | Field that caused the error |
| `raw_value` | TEXT | The raw value that failed validation |
| `error_type` | TEXT | `TYPE_MISMATCH`, `MISSING_REQUIRED`, `PARSE_ERROR`, etc. |
| `error_message` | TEXT | Human-readable error description |
| `created_at` | TIMESTAMPTZ | |

#### `ingestion_skipped_rows`

| Column | Type | Description |
|---|---|---|
| `skip_id` | BIGSERIAL | Primary key |
| `run_id` | BIGINT | |
| `row_number` | INTEGER | |
| `skip_reason` | TEXT | |
| `raw_row_data` | JSONB | Serialised raw row for re-ingestion |
| `resolution_status` | TEXT | `PENDING`, `RESOLVED`, `DISMISSED` |
| `resolved_at` | TIMESTAMPTZ | NULL |
| `resolved_by` | TEXT | NULL |

#### `ingestion_rollbacks`

| Column | Type | Description |
|---|---|---|
| `rollback_id` | BIGSERIAL | Primary key |
| `run_id` | BIGINT | FK → `ingestion_runs` |
| `initiated_by` | TEXT | JWT `sub` |
| `initiated_at` | TIMESTAMPTZ | |
| `status` | TEXT | `IN_PROGRESS`, `COMPLETE`, `FAILED` |
| `rows_removed` | INTEGER | NULL |
| `completed_at` | TIMESTAMPTZ | NULL |
| `error_detail` | TEXT | NULL |

#### `premium_variance`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `pv_id` | BIGSERIAL | NOT NULL | Primary key |
| `policy_id` | BIGINT | NOT NULL | |
| `carrier_id` | BIGINT | NOT NULL | |
| `ingestion_run_id` | BIGINT | NOT NULL | |
| `as_of_date` | DATE | NOT NULL | |
| `est_premium_end` | NUMERIC(16,2) | NOT NULL | Estimated premium at period end |
| `actual_premium` | NUMERIC(16,2) | NOT NULL | Audited actual premium |
| `variance_amount` | NUMERIC(16,2) | NOT NULL | **GENERATED**: `actual_premium - est_premium_end` |
| `variance_pct` | NUMERIC(8,4) | NULL | Engine-derived; NULL when engine is off |

Unique: `(policy_id, ingestion_run_id)`.

#### `payroll_variance_policy`

| Column | Type | Nullable | Description |
|---|---|---|---|
| `pvp_id` | BIGSERIAL | NOT NULL | Primary key |
| `policy_id` | BIGINT | NOT NULL | |
| `carrier_id` | BIGINT | NOT NULL | |
| `ingestion_run_id` | BIGINT | NOT NULL | |
| `as_of_date` | DATE | NOT NULL | |
| `est_payroll` | NUMERIC(16,2) | NOT NULL | |
| `actual_payroll_reported` | NUMERIC(16,2) | NOT NULL | |
| `reported_over_under` | NUMERIC(16,2) | NOT NULL | **GENERATED**: `actual_payroll_reported - est_payroll` |
| `reported_pct` | NUMERIC(8,4) | NULL | Engine-derived |
| `actual_payroll_classified` | NUMERIC(16,2) | NOT NULL | |
| `classified_over_under` | NUMERIC(16,2) | NOT NULL | **GENERATED**: `actual_payroll_classified - est_payroll` |
| `classified_pct` | NUMERIC(8,4) | NULL | Engine-derived |

#### `payroll_variance_class`

Finest-grain fact table. One row per policy × state × class code × ingestion run.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `pvc_id` | BIGSERIAL | NOT NULL | Primary key |
| `policy_id` | BIGINT | NOT NULL | |
| `carrier_id` | BIGINT | NOT NULL | |
| `ingestion_run_id` | BIGINT | NOT NULL | |
| `class_code_id` | BIGINT | NOT NULL | FK → `public.class_codes` |
| `state_code` | CHAR(2) | NOT NULL | |
| `as_of_date` | DATE | NOT NULL | |
| `est_payroll` | NUMERIC(16,2) | NOT NULL | |
| `actual_reported` | NUMERIC(16,2) | NOT NULL | |
| `reported_over_under` | NUMERIC(16,2) | NOT NULL | **GENERATED** |
| `reported_pct` | NUMERIC(8,4) | NULL | Engine-derived |
| `actual_classified` | NUMERIC(16,2) | NOT NULL | |
| `classified_over_under` | NUMERIC(16,2) | NOT NULL | **GENERATED** |
| `classified_pct` | NUMERIC(8,4) | NULL | Engine-derived |

Unique: `(policy_id, state_code, class_code_id, ingestion_run_id)`.

#### `zero_payroll`

Tracks pay periods where an insured submitted zero payroll.

| Column | Type | Description |
|---|---|---|
| `zp_id` | BIGSERIAL | Primary key |
| `policy_id` | BIGINT | |
| `carrier_id` | BIGINT | |
| `ingestion_run_id` | BIGINT | |
| `report_date` | DATE | |
| `zero_payroll_reason` | TEXT | Reason code from carrier |
| `payroll_vendor` | TEXT | NULL |
| `sprs` | TEXT | NULL | SPRS reference code |
| `agency` | TEXT | NULL |

#### `missing_payroll`

Tracks expected payroll periods that were not submitted.

| Column | Type | Description |
|---|---|---|
| `mp_id` | BIGSERIAL | Primary key |
| `policy_id` | BIGINT | |
| `carrier_id` | BIGINT | |
| `ingestion_run_id` | BIGINT | |
| `expected_period_start` | DATE | |
| `expected_period_end` | DATE | |
| `days_overdue` | INTEGER | Computed at ingestion time |

#### `carrier_calc_rules`

One row per calc rule per carrier. 22 rules are seeded per carrier by `add_carrier_to_tenant()`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `rule_id` | BIGSERIAL | NOT NULL | Primary key |
| `carrier_id` | BIGINT | NOT NULL | |
| `rule_key` | TEXT | NOT NULL | Unique identifier, e.g. `variance_pct`, `risk_threshold_high` |
| `rule_label` | TEXT | NOT NULL | Human-readable label |
| `rule_description` | TEXT | NOT NULL | Plain-English description shown inline in editor |
| `expression` | TEXT | NOT NULL | `simpleeval`-evaluable expression string |
| `rule_status` | TEXT | NOT NULL | `DRAFT`, `PENDING_REVIEW`, `ACTIVE`, `DEACTIVATED` |
| `is_editable` | BOOLEAN | NOT NULL | FALSE for LOCKED rules |
| `effective_from` | TIMESTAMPTZ | NOT NULL | |
| `effective_to` | TIMESTAMPTZ | NULL | Set when superseded |
| `created_by` | TEXT | NOT NULL | |
| `approved_by` | TEXT | NULL | |
| `approved_at` | TIMESTAMPTZ | NULL | |

#### `rule_audit_log`

Immutable log of all rule state transitions.

| Column | Type | Description |
|---|---|---|
| `log_id` | BIGSERIAL | Primary key |
| `rule_id` | BIGINT | |
| `carrier_id` | BIGINT | |
| `action` | TEXT | `EDITED`, `SUBMITTED_FOR_REVIEW`, `APPROVED`, `REVERTED`, `DEACTIVATED` |
| `changed_by` | TEXT | JWT `sub` |
| `changed_at` | TIMESTAMPTZ | |
| `old_expression` | TEXT | NULL |
| `new_expression` | TEXT | NULL |

#### `carrier_calc_config`

Carrier-level calculation engine mode setting.

| Column | Type | Description |
|---|---|---|
| `config_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | Unique |
| `use_calculation_engine` | BOOLEAN | Carrier-level default |
| `updated_at` | TIMESTAMPTZ | |
| `updated_by` | TEXT | |

#### `tenant_calc_config`

Tenant-level (lowest-priority) calculation engine default.

| Column | Type | Description |
|---|---|---|
| `config_id` | BIGSERIAL | Primary key |
| `use_calculation_engine` | BOOLEAN | Default TRUE; seeded at provisioning |
| `updated_at` | TIMESTAMPTZ | |
| `updated_by` | TEXT | |

One row per tenant schema. No `carrier_id`.

#### `carrier_ui_labels`

Per-carrier label overrides applied on top of `DEFAULT_LABELS`.

| Column | Type | Description |
|---|---|---|
| `label_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | |
| `screen_key` | TEXT | Namespace, e.g. `dashboard`, `field_mapping` |
| `field_key` | TEXT | Key within namespace, e.g. `title` |
| `label_value` | TEXT | Override text |
| `updated_at` | TIMESTAMPTZ | |
| `updated_by` | TEXT | |

Unique: `(carrier_id, screen_key, field_key)`.

#### `carrier_display_config`

Column visibility and display order for policy tables.

| Column | Type | Description |
|---|---|---|
| `display_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | |
| `column_key` | TEXT | Canonical column identifier |
| `is_visible` | BOOLEAN | |
| `display_order` | INTEGER | |
| `conditional_format_rule` | JSONB | NULL; colour rules for cell values |

#### `carrier_theme_config`

Per-carrier theme assignment.

| Column | Type | Description |
|---|---|---|
| `tc_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | Unique |
| `theme_source` | TEXT | `SYSTEM` (reads `public.theme_definitions`) or `CUSTOM` (reads `tenant_themes`) |
| `theme_id` | BIGINT | FK into the appropriate theme table based on `theme_source` |
| `allow_user_override` | BOOLEAN | If FALSE, `ModeToggle` and `UserThemePicker` are hidden |
| `updated_at` | TIMESTAMPTZ | |

#### `tenant_themes`

Custom themes created by TENANT_ADMIN. Mirrors `public.theme_definitions` structure.

| Column | Type | Description |
|---|---|---|
| `theme_id` | BIGSERIAL | Primary key |
| `theme_name` | TEXT | |
| `base_mode` | TEXT | `dark` or `light` |
| `is_system` | BOOLEAN | Always FALSE |
| `bg` … `color_blue` | TEXT | Same 13-token columns as `public.theme_definitions` |
| `created_by` | TEXT | |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

Note: This table corrects a gap in V9 S11/S24. V9 referenced only `public.theme_definitions`; TENANT_ADMIN cannot write to the public schema, hence custom themes require this tenant-schema table. This correction is documented in the Theme Addendum.

#### `user_theme_prefs`

Per-user theme override. Respected only when `carrier_theme_config.allow_user_override = TRUE`.

| Column | Type | Description |
|---|---|---|
| `user_keycloak_id` | TEXT | Primary key (Keycloak subject UUID) |
| `theme_source` | TEXT | `SYSTEM` or `CUSTOM` |
| `theme_id` | BIGINT | |

#### `carrier_llm_config`

Carrier-scoped LLM provider configuration for AI narrative generation (Phase 7C).

| Column | Type | Nullable | Description |
|---|---|---|---|
| `config_id` | BIGSERIAL | NOT NULL | Primary key |
| `carrier_id` | BIGINT | NOT NULL | |
| `provider_name` | TEXT | NOT NULL | `anthropic`, `openai`, `azure_openai`, `google`, `ollama`, `openai_compatible` |
| `model_name` | TEXT | NOT NULL | e.g. `claude-sonnet-4-6`, `gpt-4o`, `llama3` |
| `api_key_enc` | TEXT | NULL | Fernet AES-256 encrypted API key; NULL for keyless providers |
| `api_base_url` | TEXT | NULL | Required for `azure_openai`, `ollama`, `openai_compatible` |
| `is_active` | BOOLEAN | NOT NULL | FALSE for placeholder rows; TRUE when configured |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `updated_at` | TIMESTAMPTZ | NOT NULL | |
| `created_by` | TEXT | NOT NULL | |

Unique partial index: one active config per carrier (`carrier_id` WHERE `is_active = TRUE`).

Seeding: `add_carrier_to_tenant()` inserts a placeholder row with all config fields NULL and `is_active = FALSE`.

#### `ingestion_sources`

Carrier-configured data source definitions.

| Column | Type | Description |
|---|---|---|
| `source_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | |
| `source_name` | TEXT | Human-readable label |
| `file_type` | TEXT | `xlsx`, `csv`, `xml` |
| `sheet_name` | TEXT | NULL; for XLSX: which sheet to read |
| `delimiter` | TEXT | NULL; for CSV: `,` or `\t` or `;` |
| `is_active` | BOOLEAN | Soft-delete |
| `created_at` | TIMESTAMPTZ | |

#### `ingestion_field_maps`

Pre-configured canonical mappings per carrier and file type (Pass 1 of AutoMappingService).

| Column | Type | Description |
|---|---|---|
| `map_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | |
| `file_type` | TEXT | |
| `source_field` | TEXT | Column name as it appears in source files |
| `target_column` | TEXT | Canonical DB column name |
| `transform_fn` | TEXT | `as-is`, `date_mdy`, `cents_to_dollars`, etc. |
| `is_active` | BOOLEAN | |

Unique: `(carrier_id, source_field)`.

#### `carrier_report_templates`

Per-carrier report branding and contact block.

| Column | Type | Description |
|---|---|---|
| `template_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | Unique |
| `logo_url` | TEXT | S3 URL for report header logo |
| `primary_colour` | TEXT | Hex; used for header fill in Excel reports |
| `secondary_colour` | TEXT | Hex |
| `contact_block` | TEXT | HTML fragment rendered in PDF footer |
| `updated_at` | TIMESTAMPTZ | |

#### `report_jobs`

Async report generation jobs.

| Column | Type | Description |
|---|---|---|
| `job_id` | BIGSERIAL | Primary key |
| `carrier_id` | BIGINT | |
| `report_type` | TEXT | `individual_audit`, `book_summary`, `class_code_variance`, `ingestion_audit_trail`, `exception_report` |
| `output_format` | TEXT | `pdf`, `xlsx` |
| `status` | TEXT | `PENDING`, `IN_PROGRESS`, `COMPLETE`, `FAILED`, `CANCELLED` |
| `s3_key` | TEXT | NULL until complete |
| `file_url` | TEXT | Pre-signed S3 URL; valid 24 hours after generation |
| `requested_by` | TEXT | |
| `requested_at` | TIMESTAMPTZ | |
| `completed_at` | TIMESTAMPTZ | NULL |
| `error_detail` | TEXT | NULL |

Idempotency: same `(policy_id, run_id, output_format)` within 24 hours returns existing `job_id`.

#### `cleanup_runs`

Permanent audit log for database cleanup operations. Never deleted by the cleanup process itself.

| Column | Type | Description |
|---|---|---|
| `cleanup_id` | BIGSERIAL | Primary key |
| `initiated_by` | TEXT | JWT `sub` |
| `initiated_at` | TIMESTAMPTZ | |
| `status` | TEXT | `IN_PROGRESS`, `COMPLETE`, `FAILED` |
| `policies_archived` | INTEGER | NULL; count of policy rows deleted |
| `completed_at` | TIMESTAMPTZ | NULL |
| `error_detail` | TEXT | NULL |

#### `tenant_profiles`, `tenant_contacts`, `tenant_branding`

Populated during the 5-step onboarding wizard. Not detailed here by column — these are standard address/contact/branding tables updated via `PUT /api/v1/tenant/profile`, `/contacts`, and `/branding`.

#### `v_dashboard_summary` (View)

A carrier-scoped aggregate view that powers the Dashboard KPI cards and charts. Always computed from fact tables; never gated by calculation engine mode. Joins `premium_variance`, `payroll_variance_policy`, `policies`, `zero_payroll`, and `missing_payroll`.

---

## 6. RBAC & Security Model

### 6.1 Role Hierarchy

| Role | Scope | Description |
|---|---|---|
| `SUPER_ADMIN` | Platform-wide (no tenant) | Creates and manages tenants, manages platform carriers, manages platform themes. `tenant_slug` in JWT is null. |
| `TENANT_ADMIN` | Within one tenant | Full administrative access within their tenant: user management, carrier configuration, field mapping approval, calc rules, cleanup. |
| `AUDITOR` | Within one tenant | Uploads data files, monitors ingestion, requests reports, re-ingests skipped rows. |
| `REVIEWER` | Within one tenant | Read-only access: dashboard, policies, reports. |

### 6.2 Permission Matrix

| Operation | REVIEWER | AUDITOR | TENANT_ADMIN | SUPER_ADMIN |
|---|---|---|---|---|
| View dashboard / policies | ✓ | ✓ | ✓ | ✓ |
| View reports | ✓ | ✓ | ✓ | — |
| Upload files / start ingestion | — | ✓ | ✓ | — |
| Request report generation | — | ✓ | ✓ | — |
| Re-ingest skipped rows | — | ✓ | ✓ | — |
| Dismiss skipped rows | — | ✓ | ✓ | — |
| Approve / reject field mapping | — | — | ✓ | — |
| Rollback ingestion run | — | — | ✓ | — |
| Configure calc engine mode | — | — | ✓ | — |
| Create / edit calc rules (DRAFT) | — | — | ✓ | — |
| Submit rule for review | — | — | ✓ | — |
| Approve & activate calc rule | — | — | ✓ | — |
| Configure data sources / field maps | — | — | ✓ | — |
| Configure UI labels | — | — | ✓ | — |
| Configure carrier theme | — | — | ✓ | — |
| Configure report templates | — | — | ✓ | — |
| Configure LLM provider | — | — | ✓ | — |
| Add / remove carriers from tenant | — | — | ✓ | — |
| Initiate database cleanup | — | — | ✓ | — |
| Manage users within tenant | — | — | ✓ | — |
| Edit organization profile / branding | — | — | ✓ | — |
| Create tenants | — | — | — | ✓ |
| Manage platform carriers | — | — | — | ✓ |
| Manage platform themes | — | — | — | ✓ |
| Activate / deactivate tenants | — | — | — | ✓ |
| View cross-tenant data | — | — | — | ✓ |

### 6.3 JWT Token Structure

`TokenPayload` fields (from `backend/app/schemas/auth.py`):

| Field | Type | Description |
|---|---|---|
| `sub` | `str` | Keycloak user UUID |
| `email` | `str` | User email |
| `role` | `str` | Single role string (one of `SUPER_ADMIN`, `TENANT_ADMIN`, `AUDITOR`, `REVIEWER`) |
| `tenant_slug` | `str \| None` | Tenant slug from JWT claim; `None` for SUPER_ADMIN |

The `role` claim is a **single string**, not an array. This is the V9 convention. Keycloak must be configured with a protocol mapper that extracts a single role string.

### 6.4 Zero-Trust Endpoint Protection

Every protected endpoint applies the following guards:

1. `get_current_user()` — decodes and validates the JWT. In production, fetches JWKS from Keycloak (Redis-cached, TTL 3600s) and verifies RS256 signature. In development, `SKIP_JWT_VERIFICATION=true` accepts any well-formed JWT.
2. `verify_role(minimum_role, token)` — raises HTTP 403 if the token role is below the required minimum.
3. `verify_tenant(request, token)` — raises HTTP 403 if `token.tenant_slug` does not match the subdomain-resolved tenant (unless token role is SUPER_ADMIN).
4. `verify_carrier_scope(carrier_id, token, db)` — raises HTTP 403 if the requested `carrier_id` is not in `tenant_carriers` for the token's tenant.

### 6.5 Carrier Scope Enforcement

Every repository method that queries tenant-schema tables includes a `WHERE carrier_id = :cid` filter. This is not optional — it is the mechanism that prevents a TENANT_ADMIN from inadvertently seeing data for a carrier not assigned to their tenant. `verify_carrier_scope()` is called in every endpoint that receives a `carrier_id` parameter before any DB query.

### 6.6 Keycloak / Entra ID Integration

- JWKS endpoint is fetched on demand and cached in Redis with TTL = 3600 seconds.
- The cache key is `jwks:keycloak`.
- On JWT decode, the `kid` in the JWT header is matched against cached JWKS keys.
- `KEYCLOAK_SKIP_VERIFICATION=true` (also surfaced as `SKIP_JWT_VERIFICATION`) bypasses signature verification for local development. Never set in production.
- Required Keycloak configuration: RSA key provider, client definitions, protocol mappers for `tenant_slug` (string claim) and `role` (single string claim), wildcard subdomain redirect URIs (`*.platform.com/*`).

### 6.7 SUPER_ADMIN vs TENANT_ADMIN Distinction

SUPER_ADMIN tokens have `tenant_slug = null`. The `TenantMiddleware` does not resolve a tenant schema for SUPER_ADMIN routes (prefixed `/platform/`). SUPER_ADMIN operations use `public` schema queries only (tenant list, carrier list, platform themes). SUPER_ADMIN cannot see any tenant's operational data — only the registry metadata.

---

## 7. Platform Features — End-to-End Flow

### 7.1 Tenant Provisioning (SUPER_ADMIN)

**Who triggers it:** SUPER_ADMIN  
**Entry point:** Platform Admin Dashboard → "New Tenant" → `TenantCreationWizard`  
**RBAC gate:** `SUPER_ADMIN` role required; `/platform/tenants` route.

**Steps:**

1. **Step 1 — Tenant Details:** Tenant name + subdomain slug. Subdomain is validated for uniqueness and URL safety.
2. **Step 2 — Admin User:** Email + name of the TENANT_ADMIN to create. Optionally send invitation email.
3. **Step 3 — Carrier Assignment (Optional):** Select from `public.carriers`. Zero carriers is valid (Phase 7A change). The original "minimum 1 carrier" gate was removed.
4. **Step 4 — Review & Activate:** Summary of all choices. "Activate" button is always enabled regardless of carrier selection.

**Backend flow on Activate (`POST /platform/tenants`):**

1. Insert `public.tenants` record with `status = ACTIVE`.
2. `TenantProvisioningService.provision()`:
   - Creates `tenant_{slug}` schema via autocommit connection.
   - Runs `alembic -x target_schema=tenant_{slug} upgrade head` as a subprocess.
   - Seeds `tenant_calc_config` (`use_calculation_engine = TRUE`).
   - For each carrier selected in Step 3 (if any): calls `add_carrier_to_tenant()`.
3. **On failure:** `DROP SCHEMA IF EXISTS "tenant_{slug}" CASCADE`; soft-deletes tenant record; logs error.

**`add_carrier_to_tenant(tenant_id, carrier_id, db)` seeding:**
- Inserts `tenant_carriers` record.
- Inserts `carrier_calc_config` (`use_calculation_engine = TRUE`).
- Seeds 22 `carrier_calc_rules` records with status `ACTIVE`.
- Inserts `carrier_llm_config` placeholder row (all config NULL, `is_active = FALSE`).

### 7.2 Tenant Onboarding (TENANT_ADMIN)

**Who triggers it:** TENANT_ADMIN on first login  
**Entry point:** Invitation email → first login redirects to `OnboardingWizard`

**Steps:**

| Step | Screen | What It Does |
|---|---|---|
| 1 | Organization Profile | Upsert `tenant_profiles`: `display_name`, `legal_name`, `address`, `phone`, `website` |
| 2 | Contact Persons | Upsert `tenant_contacts`: PRIMARY and SECONDARY contacts |
| 3 | Organization Branding | Upload logo (S3) + optional brand colour → `tenant_branding` |
| 4 | Carrier Configuration Overview | Read-only overview of assigned carriers with Calculation Engine mode badge |
| 5 | Complete | `SET users.onboarding_completed = TRUE` |

### 7.3 Carrier Self-Management (TENANT_ADMIN — Post-Phase 7A)

**Entry point:** TENANT_ADMIN → Administration → Carriers → `CarrierManagementPanel`  
**Route:** `/admin/carriers`

**Panels:**

1. **Assigned Carriers:** Table of current `tenant_carriers` with "Remove" button per row.
2. **Add a Carrier:** Search/select from `GET /api/v1/admin/carriers/available` (carriers in `public.carriers` not yet assigned). "Add" calls `POST /api/v1/admin/carriers` → `add_carrier_to_tenant()`.

**Remove:** `DELETE /api/v1/admin/carriers/{carrier_id}` → soft-delete: `tenant_carriers.is_active = FALSE`. Does not delete configuration data.

### 7.4 Carrier Configuration Hub (TENANT_ADMIN)

**Entry point:** Administration → Carrier Configuration → select carrier  
**7 tabs (post-Phase 7C):**

| Tab | Name | Persists To |
|---|---|---|
| 1 | Data Sources | `ingestion_sources` — define XLSX/CSV/XML source definitions with sheet names and delimiters |
| 2 | Field Mapping | `ingestion_field_maps` — pre-configure canonical column mappings used as Pass 1 in AutoMappingService |
| 3 | Calculation Rules + Engine Mode | `carrier_calc_config`, `carrier_calc_rules`, `rule_audit_log` |
| 4 | Labels & Display | `carrier_ui_labels`, `carrier_display_config` |
| 5 | Report Template | `carrier_report_templates` — logo, colours, contact block HTML |
| 6 | Theme | `carrier_theme_config`, `tenant_themes` — theme picker and ThemeEditor |
| 7 | AI Configuration | `carrier_llm_config` — LLM provider, model, API key (AES-256 encrypted), base URL |

### 7.5 Data Upload & Ingestion — Three Upload Types

**Entry point:** Audit Runner screen (`AuditRunnerPage`) or Bulk Upload screen (`BulkUploadPage`)

**Upload Types:**

| Type | Mode | Files Required | Description |
|---|---|---|---|
| Type 1 | Calc Engine | XML + Payroll XLSX + Audit XLSX | Full 3-file set; XML supplies policy config (class codes, exposure, dates) |
| Type 2 | Calc Engine | Payroll XLSX + Audit XLSX | 2-file set; no XML |
| Type 3 | Calc Engine | Single CSV | Single delimited file |
| Display Only | Display | Single XLSX | No calculations; read-only presentation of pre-computed data |

**Bulk Upload:**
- AUDITOR drags a ZIP archive or a folder of files onto the `BulkUploadPage` drop zone.
- Files are grouped by shared prefix: `POL001_payroll.xlsx` + `POL001_audit.xlsx` + `POL001.xml` = one policy group.
- Files with matching prefix before `_payroll`, `_audit`, or `.xml` are auto-grouped.
- Complete groups are submitted first; incomplete groups are shown with a warning.

**File type detection:**
- Filename extension is authoritative (`.xlsx`, `.xml`, `.csv`).
- `content_type` is used as a fallback only.
- `application/octet-stream` is excluded from content-type detection (extension only).

**Ingestion pipeline (upload to awaiting_mapping):**

1. `POST /api/v1/ingestion/upload` (multipart: `file`, `carrier_id`, `source_id`, `ingestion_mode`)
2. `IngestionService.run()` creates `ingestion_run` record with `status = awaiting_mapping`.
3. `AutoMappingService.run()` scores every source field column → creates `field_mapping_session` + `field_mapping_proposals`.
4. Response: `202 { run_id, status: "awaiting_mapping", session_id }`.
5. Frontend redirects AUDITOR to `FieldMappingReview` screen.

### 7.6 Auto-Mapping & Field Mapping Approval Gate

**AutoMappingService — 4-pass algorithm:**

| Pass | Confidence | Score | Condition |
|---|---|---|---|
| 1 | HIGH | 1.000 | Exact match against `ingestion_field_maps` for `(carrier_id, file_type, source_field)` |
| 2 | HIGH | 0.950 | `normalise(source_field) == normalise(target_column)` for any canonical column |
| 3 | MEDIUM | `ratio × 0.85` | `difflib.SequenceMatcher ratio ≥ 0.75` AND type-compatible |
| 3 | LOW | `ratio × 0.60` | `ratio ≥ 0.50` but type-incompatible, OR `ratio < 0.75` |
| 4 | UNMATCHED | 0.000 | No match found |

`normalise(text)`: strips whitespace, lowercases, collapses inner spaces.

**FieldMappingReview screen:**

| Tier | Visual Treatment |
|---|---|
| HIGH | Green badge; read-only rows; pre-checked |
| MEDIUM | Amber badge; editable; pencil icon |
| LOW | Orange badge; edit strongly recommended; warning icon |
| UNMATCHED | Red badge; mandatory manual assignment before approval is enabled |

**Approval gate:**

- Only TENANT_ADMIN can approve.
- "Approve Mapping" button enabled only when all source fields have a confirmed target or are marked `Excluded`.
- On approval: `field_mapping_session.status = APPROVED`; `ingestion_run.status = mapping_approved`; ingestion pipeline begins via `run_post_approval()`.
- On rejection: `status = REJECTED`; ingestion does not proceed; AUDITOR must re-upload.

### 7.7 Calculation Engine

**Three-level mode resolution (`resolve_effective_mode()`):**

Priority order (most specific wins): per-run override (`ingestion_runs.use_calculation_engine`) → carrier default (`carrier_calc_config.use_calculation_engine`) → tenant default (`tenant_calc_config.use_calculation_engine`).

**Two modes:**

- `calc_engine` (ON): `AuditCalculationService` evaluates all 22 rules and writes derived values (`variance_pct`, `reported_pct`, `classified_pct`, `risk_level`) back to fact tables.
- `display_only` (OFF): Fact tables contain only the raw ingested values. Engine-derived columns are NULL. `NaIndicator` component renders "N/A" for these fields.

**Always-on operations (never gated by engine mode):**

- PostgreSQL `GENERATED` columns: `variance_amount`, `reported_over_under`, `classified_over_under` — computed at INSERT time regardless of engine setting.
- Dashboard KPI aggregations (`v_dashboard_summary` SQL view) — always computed.

**Rules Engine:**

`AuditCalculationService.load_rules()` queries `carrier_calc_rules WHERE rule_status = 'ACTIVE'`. Rules are Redis-cached at `{schema_name}:calc_rules:{carrier_id}` (TTL 300s).

- **LOCKED rules (10):** Use hardcoded Python implementations. Their DB expressions are stored for documentation only; `simpleeval` never evaluates them.
- **EDITABLE rules (12):** The `expression` string from DB is evaluated via `simpleeval.EvalWithCompoundTypes`. `SAFE_NAMES` is the complete and only permitted namespace.

**Two-step rule approval:**

1. TENANT_ADMIN edits expression → saved as `DRAFT` (existing ACTIVE rule unchanged).
2. TENANT_ADMIN clicks "Submit for Review" → `PENDING_REVIEW`.
3. TENANT_ADMIN (same or different session) clicks "Approve & Activate" → `ACTIVE`; previous ACTIVE rule's `effective_to` is set; Redis cache invalidated.

**Seeded 22 rules (per carrier):**

The 10 LOCKED rules are: `variance_amount`, `variance_pct`, `reported_over_under`, `classified_over_under`, `reported_pct`, `classified_pct`, `est_ytd_premium`, `completion_ratio`, `premium_paid_pct`, and one more system calculation.

The 12 EDITABLE rules include: `expected_submissions`, `submission_rate`, `risk_threshold_high`, `risk_threshold_medium`, `risk_threshold_target`, `officer_max_payroll`, `officer_min_payroll`, `zero_payroll_flag`, `missing_payroll_flag`, and frequency cycle rules (`freq_cycle_*`).

### 7.8 Ingestion Exception Tracking

**Row-level error tracking:**

- `ingestion_errors`: rows that failed validation during parsing.
- `ingestion_skipped_rows`: rows skipped when `skip_on_error = TRUE` on the ingestion run. Stores the raw row data as JSONB for re-ingestion.

**Skip-on-error mode:** When `skip_on_error = TRUE` (the default), rows that fail validation are recorded to `ingestion_skipped_rows` and the run continues. The run completes with `status = partial` if any rows were skipped.

**Rollback:**

- `POST /api/v1/ingestion/runs/{run_id}/rollback` — TENANT_ADMIN only.
- `RollbackService` deletes fact table rows for that `run_id` from `premium_variance`, `payroll_variance_policy`, `payroll_variance_class`, `zero_payroll`, `missing_payroll`.
- The `ingestion_run` record is NOT deleted — it remains with `status = rolled_back` as an audit trail.
- The `ingestion_rollbacks` record is never deleted.

**Resolution workflow:**

- AUDITOR can re-ingest individual skipped rows: `POST /api/v1/ingestion/skipped-rows/{skip_id}/re-ingest`.
- AUDITOR can dismiss skipped rows: `PATCH /api/v1/ingestion/skipped-rows/{skip_id}/dismiss`.

### 7.9 AI Narrative Service (Phase 7C)

**Who triggers it:** Called automatically after a `calc_engine` run completes for a policy.  
**Entry point:** `AInarrativeService.generate(ctx, carrier_id, db, schema_name)`.

**LLM provider resolution chain (in priority order):**

1. Carrier-scoped `carrier_llm_config` (reads `provider_name`, `model_name`, `api_key_enc` decrypted via `LLMKeyVaultService`, `api_base_url`).
2. Platform-level `ANTHROPIC_API_KEY` environment variable → `AnthropicClient`.
3. Deterministic Python f-string template (fallback when both 1 and 2 fail or are unconfigured). `is_fallback = True`.

`carriers.ai_narrative_enabled` is **not consulted** in the resolution chain (Phase 7C change). The column is retained in `public.carriers` for historical audit purposes only.

**`AInarrativeService` contract:** Never raises an exception. Always returns a `NarrativeResult` (with `is_fallback = True` if the LLM call fails).

**`NarrativeSection` in `PolicyDetailResponse`:**

```python
class NarrativeSection(BaseModel):
    text: str | None
    source: Literal["llm", "fallback"] | None
    generated_at: datetime | None
    engine_was_run: bool
    provider_used: str | None  # e.g. "anthropic/claude-sonnet-4-6"
```

**NarrativePanel component states:**

| Condition | Display |
|---|---|
| `source = "fallback"` | Amber notice bar: template was used |
| `engine_was_run = False` | Info bar: engine must be enabled |
| `text = null`, run complete | Error state |
| `text = null`, run in-progress | Loading skeleton (3 line pulses) |
| Normal | Full text with provider badge and generated timestamp |

Narrative is collapsed to 4 lines by default. "Show Full Narrative ▼" expands inline. "Copy to Clipboard" uses browser Clipboard API.

### 7.10 Report Generation

**Entry point:** `POST /api/v1/reports/generate` — AUDITOR or TENANT_ADMIN.

**Report types:**

| Type | Format | Description |
|---|---|---|
| `individual_audit` | PDF | Per-policy audit report with branding, variance tables, class code breakdown |
| `book_summary` | XLSX | All policies with all columns |
| `class_code_variance` | XLSX | `payroll_variance_class` for all policies and class codes |
| `ingestion_audit_trail` | XLSX | `ingestion_runs` history |
| `exception_report` | XLSX | `ingestion_errors` + `ingestion_skipped_rows` for a run |

**Async job flow:**

1. `POST /api/v1/reports/generate` → `202 { job_id }`.
2. Background task: WeasyPrint (PDF) or openpyxl (Excel) → S3 upload.
3. `GET /api/v1/reports/{job_id}/status` → `{ status, file_url }` when complete.
4. `file_url` is a pre-signed S3 URL with 24-hour TTL.

**Branding:** Template logo: `carrier_report_templates.logo_url` → `tenant_branding.logo_url` → no logo. Colors from `carrier_report_templates.primary_colour` and `secondary_colour`.

### 7.11 Theme System

**CSS Token Architecture:** All visual colors flow through 13 CSS custom properties injected on `:root` by `useTheme()`. No component contains a hardcoded hex value.

**Complete Token Reference:**

| CSS Token | Property Name | Controls |
|---|---|---|
| `--bg` | `bg` | Outermost page background; nav background |
| `--surface` | `surface` | Card and panel backgrounds; modal backgrounds |
| `--surface2` | `surface2` | Form input backgrounds; AI Narrative textarea; tab content areas |
| `--border` | `border_col` | All borders and dividers; input borders |
| `--text` | `text_primary` | Primary readable text |
| `--muted` | `text_muted` | Labels, captions, placeholders, "N/A" indicators |
| `--brand` | `brand` | Active nav item; primary buttons; Low Risk badge; positive variance |
| `--brand-dark` | `brand_dark` | Active nav item background fill |
| `--accent` | `accent` | Provider badge; highlighted secondary elements |
| `--green` | `color_green` | Positive values; Low Risk badge |
| `--amber` | `color_amber` | Medium risk; warnings; MEDIUM confidence tier |
| `--red` | `color_red` | High risk; errors; UNMATCHED confidence tier |
| `--blue` | `color_blue` | Informational badges; neutral highlights |

**Theme resolution chain (server-side, `GET /api/v1/theme/resolved`):**

1. Check `user_theme_prefs` for the requesting user AND `carrier_theme_config.allow_user_override = TRUE`.
2. Check `carrier_theme_config` for the active carrier.
3. Fall back to Default Dark (`public.theme_definitions` where `theme_id = 1`).
4. After theme resolved: if `tenant_branding.brand_color` is set, override `--brand` token.

**Custom theme creation:**

TENANT_ADMIN creates custom themes via `ThemeEditor` (Tab 6, Carrier Config Hub). Custom themes are stored in `tenant_themes` (tenant schema). System themes are read-only from `public.theme_definitions`.

The `theme_source` column on `carrier_theme_config` and `user_theme_prefs` distinguishes between `SYSTEM` and `CUSTOM` themes.

**ThemeEditor UI:** Three-column layout — token color pickers (grouped by Background, Text & Borders, Brand, Status) / live preview panel / metadata (name, mode, based-on). WCAG contrast indicator: non-blocking amber warning when contrast ratio between `--text-primary` and `--surface` is below 4.5:1.

**Logo resolution chain:**

- Nav bar (dark): `tenant_branding.logo_url` → platform name text.
- Nav bar (light): `tenant_branding.logo_dark_url` → `logo_url` → platform name text.
- PDF report header: `carrier_report_templates.logo_url` → `tenant_branding.logo_url` → no logo.

**Theme import/export:** JSON format containing all 13 token values plus metadata. Export button → file download. Import → pre-fills ThemeEditor; saves to `tenant_themes` on save.

**Theme deletion:** Reference check before delete. If theme is in use by `carrier_theme_config` or `user_theme_prefs`: show reference warning with "Replace with…" flow. If no references: simple confirm dialog → hard delete.

**`allow_user_override = FALSE`:** `ModeToggle` is hidden entirely. `UserThemePicker` in avatar dropdown is hidden.

**Database cleanup:** Theme data (`tenant_themes`, `carrier_theme_config`, `user_theme_prefs`) is ALWAYS preserved during cleanup.

### 7.12 Database Cleanup & Monthly Processing Cycle

**Entry point:** TENANT_ADMIN → Administration → Database Cleanup → `DatabaseCleanupPage`  
**RBAC gate:** `TENANT_ADMIN` only.

**Two-step workflow:**

1. **Preview** (`POST /api/v1/database-cleanup/preview`): Read-only. Returns row counts per table that would be deleted. No writes.
2. **Execute** (`POST /api/v1/database-cleanup/execute`): Body must contain `{ "confirm": "CONFIRM" }` (exact string, case-sensitive). HTTP 422 if string does not match.

**What gets cleared:**

- Fact tables: `premium_variance`, `payroll_variance_policy`, `payroll_variance_class`, `zero_payroll`, `missing_payroll`.
- Policy master: `policies`, `policyholders`.
- Ingestion history: `ingestion_runs`, `ingestion_errors`, `ingestion_skipped_rows`, `ingestion_rollbacks`, `field_mapping_sessions`, `field_mapping_proposals`.
- Report jobs: `report_jobs` where `status IN ('COMPLETE', 'FAILED', 'CANCELLED')`.

**Always preserved:**

Configuration (`carrier_calc_rules`, `carrier_ui_labels`, `carrier_display_config`, `carrier_theme_config`, `carrier_report_templates`, `ingestion_sources`, `ingestion_field_maps`, `carrier_calc_config`, `tenant_calc_config`), tenant identity (`users`, `tenant_profiles`, `tenant_contacts`, `tenant_branding`, `tenant_carriers`), theme data (`tenant_themes`, `user_theme_prefs`), and the `cleanup_runs` audit log (never deleted by cleanup).

### 7.13 Label Management (UI Configurability)

**Entry point:** Carrier Config Hub → Tab 4 → Labels sub-tab.

**`carrier_ui_labels` table** stores per-carrier overrides keyed by `(screen_key, field_key)`.

**`useLabels(screenKey)` hook resolution:**

1. Fetches overrides via `GET /api/v1/labels?carrier_id={id}` (TanStack Query; Redis-cached at `{schema_name}:labels:{carrier_id}`, TTL 300s).
2. Merges carrier overrides onto `DEFAULT_LABELS` (flat merge; unknown keys silently ignored).
3. Returns the complete merged `LabelMap` for the requested screen namespace.
4. If API call fails: silently uses `DEFAULT_LABELS` unchanged. The hook never throws.

**`DEFAULT_LABELS` immutability rule:** Existing keys in the `DEFAULT_LABELS` registry may never be modified after initial commit. Only new keys and namespaces may be added. This ensures any carrier override referencing an existing key continues to work after platform upgrades.

**Label namespaces** include (non-exhaustive): `dashboard`, `policies`, `field_mapping`, `ingestion`, `carrier_config`, `calc_engine`, `reports`, `theme`, `narrative_panel`, `ai_config`, `platform_admin`, `shared`, and more.

---

## 8. Module-by-Module Code Documentation

### 8.1 Backend Modules

#### `backend/app/api/security.py`

**Responsibility:** JWT decoding, Keycloak RS256 signature verification, RBAC enforcement, tenant verification.

**Public functions:**

| Function | Description |
|---|---|
| `get_current_user(request, credentials)` | FastAPI dependency. Phase 1/dev: decodes JWT without RS256 check if `SKIP_JWT_VERIFICATION=true`. Phase 2/prod: fetches JWKS from Keycloak (Redis-cached), verifies RS256 signature. Returns `TokenPayload`. |
| `verify_role(required_role, token)` | Raises HTTP 403 if `token.role` is below `required_role` in the hierarchy. |
| `verify_tenant(request, token)` | Raises HTTP 403 if `token.tenant_slug` does not match the subdomain-resolved tenant. SUPER_ADMIN exempt. |
| `verify_carrier_scope(carrier_id, token, db)` | Async. Raises HTTP 403 if `carrier_id` is not in `tenant_carriers` for the token's tenant. |

#### `backend/app/api/deps.py`

**Responsibility:** Shared FastAPI dependency factories.

| Function | Description |
|---|---|
| `get_db(request)` | Async generator. Reads `request.state.tenant.schema_name`, executes `SET search_path TO "{schema}", public`, yields `AsyncSession`. |
| `get_pagination(page, page_size)` | Returns `(offset, limit)` for list endpoints. |

#### `backend/app/api/v1/platform.py`

**Responsibility:** SUPER_ADMIN routes for tenant and carrier management.

| Endpoint | Description |
|---|---|
| `GET /platform/tenants` | List all tenants with status, carrier count, user count. |
| `POST /platform/tenants` | Create tenant; runs `TenantProvisioningService.provision()`. |
| `GET /platform/tenants/{id}` | Tenant detail: identity, carriers, users, danger zone. |
| `PATCH /platform/tenants/{id}/status` | Activate / deactivate. |
| `DELETE /platform/tenants/{id}` | Soft-delete: sets `status = DELETED`. |
| `GET /platform/carriers` | List all platform carriers. |
| `POST /platform/carriers` | Create new platform carrier. |
| `GET /platform/themes` | List all system themes. |
| `POST /platform/themes` | Create platform theme variant. |
| `PUT /platform/themes/{id}` | Update theme tokens. |
| `POST /platform/themes/{id}/default` | Set as platform default. |

#### `backend/app/api/v1/ingestion.py`

**Responsibility:** File upload, mapping gate, ingestion status polling, rollback.

| Endpoint | Description |
|---|---|
| `POST /api/v1/ingestion/upload` | Multipart upload. Creates `ingestion_run`, triggers `AutoMappingService`. Returns `202 { run_id, session_id }`. |
| `GET /api/v1/ingestion/mapping/{session_id}` | Fetch `MappingSession` with all `MappingProposal` rows. |
| `PATCH /api/v1/ingestion/mapping/{session_id}/proposals/{proposal_id}` | Update a single proposal (target, transform_fn, is_excluded). |
| `POST /api/v1/ingestion/mapping/{session_id}/approve` | TENANT_ADMIN only. Triggers `run_post_approval()`. |
| `POST /api/v1/ingestion/mapping/{session_id}/reject` | TENANT_ADMIN only. |
| `GET /api/v1/ingestion/mapping/canonical-columns` | List of all canonical column names and types. |
| `GET /api/v1/ingestion/runs/{run_id}/status` | Poll run status: `{ status, rows_ingested, rows_skipped, rows_failed }`. |
| `POST /api/v1/ingestion/runs/{run_id}/rollback` | TENANT_ADMIN only. Calls `RollbackService`. |
| `GET /api/v1/ingestion/runs/{run_id}/errors` | List `ingestion_errors` for a run. |
| `GET /api/v1/ingestion/runs/{run_id}/skipped` | List `ingestion_skipped_rows` for a run. |
| `POST /api/v1/ingestion/skipped-rows/{skip_id}/re-ingest` | AUDITOR+. Re-ingests a single skipped row. |
| `PATCH /api/v1/ingestion/skipped-rows/{skip_id}/dismiss` | AUDITOR+. |

#### `backend/app/services/audit_calculation_service.py`

**Responsibility:** Evaluates all 22 calculation rules against payroll fact data for a completed ingestion run.

**Key methods:**

| Method | Description |
|---|---|
| `resolve_effective_mode(schema_name, carrier_id, run_id, db)` | Async. Reads per-run override → carrier default → tenant default. Redis-cached. |
| `load_rules(schema_name, carrier_id, db)` | Async. Queries `carrier_calc_rules WHERE rule_status='ACTIVE'`. Redis-cached at `{schema_name}:calc_rules:{carrier_id}`, TTL 300s. |
| `run(schema_name, carrier_id, run_id, db)` | Async. Resolves mode, loads rules, evaluates all 22 rules, writes derived values back to fact tables. |
| `_eval_editable_rule(expression, ctx)` | Evaluates expression string via `simpleeval.EvalWithCompoundTypes` with `SAFE_NAMES` namespace. Returns `None` and logs warning on any error. |

**SAFE_NAMES** (the complete and only permitted namespace for `simpleeval`): `actual_premium`, `est_premium_end`, `variance_amount`, `variance_pct`, `actual_payroll_reported`, `actual_payroll_classified`, `est_payroll`, `reported_over_under`, `classified_over_under`, `submitted_count`, `expected_submissions`, `missing_payrolls`, `wages`, `days_elapsed`, `cycle_days`, `policy_days`, `completion_ratio`, `days_since_last_run`, plus `abs`, `round`, `min`, `max`, `True`, `False`, `None`.

#### `backend/app/services/auto_mapping_service.py`

**Responsibility:** Produces `field_mapping_session` and `field_mapping_proposals` for an uploaded file using 4-pass confidence scoring.

**Key methods:**

| Method | Description |
|---|---|
| `run(run_id, carrier_id, file_type, file_bytes, db)` | Async. Reads file header, scores all source fields, inserts session + proposals. Returns `session_id`. |
| `_read_source_fields(file_bytes, file_type)` | Returns `list[(field_name, sample_value)]`. Reads header row from XLSX / CSV / XML. Handles multi-section XLSX audit reports (finds Employee Detail header by looking for Employee Name + Wages + Class Code in the same row). |
| `_score_field(source_field, sample_value, saved_mappings, canonical_columns)` | Applies 4-pass algorithm. Returns `(confidence, score, proposed_target, transform_fn, match_reason)`. |
| `_infer_type(sample_value)` | Returns `TEXT`, `NUMERIC`, `DATE`, `BOOLEAN`, or `INTEGER`. |
| `_get_saved_mappings(carrier_id, file_type, db)` | Queries `ingestion_field_maps`. Returns `{normalised_source: target_column}`. |

#### `backend/app/services/ai_narrative_service.py`

**Responsibility:** Generates an AI audit narrative for a policy. Never raises; always returns a `NarrativeResult`.

**Key methods:**

| Method | Description |
|---|---|
| `generate(ctx, carrier_id, db, schema_name)` | Async. Resolves LLM client via 3-step chain. Calls `client.generate(prompt)`. Returns `NarrativeResult`. |
| `_resolve_llm_client(carrier_id, tenant_schema, db)` | Async. Returns `(BaseLLMClient, provider_label)` or `(None, None)`. |
| `_build_prompt(ctx)` | Constructs the LLM prompt from `AuditNarrativeContext`. |
| `_fallback_narrative(ctx)` | Returns deterministic Python f-string template. Never raises. |

#### `backend/app/services/tenant_provisioning_service.py`

**Responsibility:** Creates tenant schemas, runs Alembic migrations, seeds initial data.

**Key methods:**

| Method | Description |
|---|---|
| `provision(tenant_id, slug, carrier_ids, db)` | Async. Full provisioning flow with rollback on failure. |
| `add_carrier_to_tenant(tenant_id, carrier_id, db)` | Async. Idempotent. Seeds `tenant_carriers`, `carrier_calc_config`, 22 `carrier_calc_rules`, `carrier_llm_config` placeholder. |
| `_create_schema(slug)` | Creates `tenant_{slug}` PostgreSQL schema via autocommit connection. |
| `_run_alembic(slug)` | Runs `alembic -x target_schema=tenant_{slug} upgrade head` as subprocess. |
| `_rollback_failed_provision(tenant_id, slug, db)` | `DROP SCHEMA IF EXISTS "tenant_{slug}" CASCADE`; soft-deletes tenant. |

#### `backend/app/services/cleanup_service.py`

**Responsibility:** Two-step monthly cleanup workflow.

**Key methods:**

| Method | Description |
|---|---|
| `preview(schema_name, db)` | Async. Read-only. Returns `dict[str, int]` of row counts per table. |
| `execute(schema_name, initiated_by, db)` | Async. Deletes operational data in dependency order within a single transaction. Logs to `cleanup_runs`. Returns `cleanup_id`. On failure: rollback; update `cleanup_runs.status = 'FAILED'`. |

#### `backend/app/services/report_service.py`

**Responsibility:** Generates PDF and Excel reports asynchronously.

**Key methods:**

| Method | Description |
|---|---|
| `generate_individual_audit(policy_id, run_id, output_format, db)` | Renders Jinja2 template → WeasyPrint PDF or openpyxl Excel. Uploads to S3. Returns `(bytes, content_type, filename)`. |
| `generate_book_summary(carrier_id, output_format, db)` | All policies with all columns. |
| `generate_class_code_variance(carrier_id, run_id, db)` | `payroll_variance_class` export. |
| `generate_ingestion_audit_trail(carrier_id, run_id, db)` | `ingestion_runs` history. |
| `generate_exception_report(carrier_id, run_id, db)` | `ingestion_errors` + `ingestion_skipped_rows`. |
| `_render_pdf(template_name, ctx)` | Jinja2 → HTML → WeasyPrint → PDF bytes. |

---

### 8.2 Frontend Feature Modules

#### `frontend/src/features/ingestion/`

**Components:**

| Component | Description |
|---|---|
| `AuditRunnerPage.tsx` | Single-file upload form. Carrier + data source selection. File drop zone. Posts to `POST /api/v1/ingestion/upload`. Redirects to `FieldMappingReview` on success. |
| `BulkUploadPage.tsx` | Multi-file / ZIP upload. Selects upload type (Type 1/2) and ingestion mode. Groups files by policy prefix. Extracts ZIP via `JSZip`. |
| `FieldMappingReview.tsx` | Displays `MappingSession` with proposals grouped by confidence tier. Inline target column dropdown for MEDIUM/LOW/UNMATCHED rows. "Approve Mapping" button (TENANT_ADMIN only). "Reject & Start Over" button. |
| `IngestionProgress.tsx` | Polls `GET /api/v1/ingestion/runs/{run_id}/status` after mapping approval. Shows progress. Links to ExceptionTracker if `status = partial`. |

**Services:** `ingestionApi.ts` — `uploadFile()`, `fetchMappingSession()`, `fetchCanonicalColumns()`, `updateMappingProposal()`, `approveMappingSession()`, `rejectMappingSession()`, `fetchRunStatus()`.

#### `frontend/src/features/carrier-config/`

**Components:**

| Component | Description |
|---|---|
| `CarrierConfigHub.tsx` | 7-tab container. Routes to each tab component. |
| `DataSourcesTab.tsx` | Tab 1: CRUD for `ingestion_sources`. Add/Edit modal with Sheet Name / Delimiter fields by type. |
| `FieldMappingTab.tsx` | Tab 2: Pre-configured `ingestion_field_maps`. |
| `CalcRulesList.tsx` | Tab 3: 22-rule editor. Two-step approval UI. Expression text input + `ExpressionBuilder` (Phase 7D). Rule history drawer. Expression tester. AI-suggest. |
| `ExpressionBuilder.tsx` | Phase 7D: Drag-and-drop field token builder. Renders `FieldPanel` (draggable tokens) + `ExpressionCanvas` (drop target). Produces expression string for parent. Falls back to raw text mode for complex expressions. |
| `LabelsDisplayTab.tsx` | Tab 4: Inline-edit label overrides. CSV import/export. Preview Mode toggle. Display Config sub-tab. |
| `ReportTemplateTab.tsx` | Tab 5: Logo upload, color pickers, contact block HTML editor. |
| `ThemeTab.tsx` + `ThemeEditor.tsx` | Tab 6: `ThemePicker` (system + custom themes). `ThemeEditor` (3-column layout, 13 token pickers, WCAG indicator, live preview). Import/export. |
| `AIConfigTab.tsx` | Tab 7 (Phase 7C): LLM provider/model/API key/base URL form. Test Connection button. Delete configuration. |

**Hooks:** `useCarrierCalcConfig.ts` — engine mode state; `useCalcRules()` — rules list + mutations; `useLabels()` + `useTheme()` consumed throughout.

#### `frontend/src/features/administration/`

| Component | Description |
|---|---|
| `platform-admin/TenantCreationWizard/WizardShell.tsx` | 4-step wizard container. Step 3 carrier assignment is optional (Phase 7A). |
| `platform-admin/TenantDetail.tsx` | Tenant detail: identity, read-only carrier list, users, danger zone (deactivate/delete). |
| `organization/CarrierManagementPanel.tsx` | Phase 7A: TENANT_ADMIN add/remove carriers. Two panels: Assigned Carriers + Add a Carrier. |
| `database-cleanup/DatabaseCleanupPage.tsx` | Preview, confirmation input, execute, history table. |

#### `frontend/src/features/policies/`

Policy list with filters (status, risk, state) + 4-tab policy detail:

1. **Policy Summary:** Premium variance cards + payroll variance cards.
2. **Missing Payrolls:** 11-column table of expected periods not submitted.
3. **Zero Payrolls:** 9-column table of zero-payroll submissions.
4. **Analysis (AI Narrative):** `NarrativePanel` component.

---

## 9. API Reference

### 9.1 Platform (SUPER_ADMIN)

| Verb | Path | Role | Description |
|---|---|---|---|
| GET | `/platform/tenants` | SUPER_ADMIN | List all tenants |
| POST | `/platform/tenants` | SUPER_ADMIN | Create tenant + provision schema |
| GET | `/platform/tenants/{id}` | SUPER_ADMIN | Tenant detail |
| PATCH | `/platform/tenants/{id}/status` | SUPER_ADMIN | Activate / deactivate |
| DELETE | `/platform/tenants/{id}` | SUPER_ADMIN | Soft-delete |
| GET | `/platform/carriers` | SUPER_ADMIN | List platform carriers |
| POST | `/platform/carriers` | SUPER_ADMIN | Create carrier |
| GET | `/platform/themes` | SUPER_ADMIN | List platform themes |
| POST | `/platform/themes` | SUPER_ADMIN | Create theme |
| PUT | `/platform/themes/{id}` | SUPER_ADMIN | Update theme tokens |
| POST | `/platform/themes/{id}/default` | SUPER_ADMIN | Set platform default theme |

### 9.2 Admin (TENANT_ADMIN)

| Verb | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/tenant/profile` | TENANT_ADMIN | Get organization profile |
| PUT | `/api/v1/tenant/profile` | TENANT_ADMIN | Update profile |
| PUT | `/api/v1/tenant/contacts` | TENANT_ADMIN | Update contact persons |
| PUT | `/api/v1/tenant/branding` | TENANT_ADMIN | Update branding (logo upload) |
| GET | `/api/v1/admin/users` | TENANT_ADMIN | List tenant users |
| POST | `/api/v1/admin/users` | TENANT_ADMIN | Create AUDITOR or REVIEWER user |
| PATCH | `/api/v1/admin/users/{id}` | TENANT_ADMIN | Update user role or status |
| GET | `/api/v1/admin/carriers/available` | TENANT_ADMIN | Platform carriers not yet assigned |
| POST | `/api/v1/admin/carriers` | TENANT_ADMIN | Add carrier to tenant (seeds 22 rules) |
| DELETE | `/api/v1/admin/carriers/{carrier_id}` | TENANT_ADMIN | Remove carrier (soft-delete) |
| GET | `/api/v1/admin/calc-config/{carrier_id}` | REVIEWER+ | Get carrier engine mode |
| PUT | `/api/v1/admin/calc-config/{carrier_id}` | TENANT_ADMIN | Set carrier engine mode |
| GET | `/api/v1/admin/tenant-calc-config` | REVIEWER+ | Get tenant-level engine default |
| PUT | `/api/v1/admin/tenant-calc-config` | TENANT_ADMIN | Set tenant-level engine default |

### 9.3 Calculation Rules

| Verb | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/admin/calc-rules?carrier_id={id}` | TENANT_ADMIN | List all 22 rules |
| GET | `/api/v1/admin/calc-rules/{rule_id}` | TENANT_ADMIN | Rule detail |
| PUT | `/api/v1/admin/calc-rules/{rule_id}` | TENANT_ADMIN | Edit rule → saved as DRAFT |
| POST | `/api/v1/admin/calc-rules/{rule_id}/submit` | TENANT_ADMIN | DRAFT → PENDING_REVIEW |
| POST | `/api/v1/admin/calc-rules/{rule_id}/approve` | TENANT_ADMIN | PENDING_REVIEW → ACTIVE |
| POST | `/api/v1/admin/calc-rules/{rule_id}/revert` | TENANT_ADMIN | PENDING_REVIEW → DRAFT |
| POST | `/api/v1/admin/calc-rules/{rule_id}/deactivate` | TENANT_ADMIN | ACTIVE → DEACTIVATED (EDITABLE only) |
| GET | `/api/v1/admin/calc-rules/{rule_id}/history` | TENANT_ADMIN | Rule audit log |
| POST | `/api/v1/admin/calc-rules/{rule_id}/test` | TENANT_ADMIN | Test expression with sample values |
| POST | `/api/v1/admin/calc-rules/ai-suggest` | TENANT_ADMIN | AI-suggested expression for a description |
| GET | `/api/v1/admin/calc-rules/available-fields?carrier_id={id}` | TENANT_ADMIN | SAFE_NAMES with labels (Phase 7D) |

### 9.4 Ingestion

| Verb | Path | Role | Description |
|---|---|---|---|
| POST | `/api/v1/ingestion/upload` | AUDITOR+ | Upload file. Returns `202 { run_id, session_id }` |
| GET | `/api/v1/ingestion/mapping/{session_id}` | AUDITOR+ | Mapping session + proposals |
| PATCH | `/api/v1/ingestion/mapping/{session_id}/proposals/{proposal_id}` | AUDITOR+ | Update single proposal |
| POST | `/api/v1/ingestion/mapping/{session_id}/approve` | TENANT_ADMIN | Approve mapping → start ingestion |
| POST | `/api/v1/ingestion/mapping/{session_id}/reject` | TENANT_ADMIN | Reject mapping |
| GET | `/api/v1/ingestion/mapping/canonical-columns` | AUDITOR+ | Canonical column list |
| GET | `/api/v1/ingestion/runs/{run_id}/status` | AUDITOR+ | Poll run status |
| POST | `/api/v1/ingestion/runs/{run_id}/rollback` | TENANT_ADMIN | Rollback run; deletes fact data |
| GET | `/api/v1/ingestion/runs/{run_id}/errors` | AUDITOR+ | Row-level errors |
| GET | `/api/v1/ingestion/runs/{run_id}/skipped` | AUDITOR+ | Skipped rows |
| POST | `/api/v1/ingestion/skipped-rows/{skip_id}/re-ingest` | AUDITOR+ | Re-ingest skipped row |
| PATCH | `/api/v1/ingestion/skipped-rows/{skip_id}/dismiss` | AUDITOR+ | Dismiss skipped row |

### 9.5 Dashboard & Policies

| Verb | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/dashboard/summary?carrier_id={id}` | REVIEWER+ | KPI cards, chart data, target variance |
| GET | `/api/v1/policies?carrier_id={id}` | REVIEWER+ | Paginated policy list with filters |
| GET | `/api/v1/policies/{policy_id}` | REVIEWER+ | Policy detail: all 4 tabs + `NarrativeSection` |

### 9.6 Reports

| Verb | Path | Role | Description |
|---|---|---|---|
| POST | `/api/v1/reports/generate` | AUDITOR+ | Start async report job. Returns `202 { job_id }` |
| GET | `/api/v1/reports/{job_id}/status` | AUDITOR+ | Poll: `{ status, file_url }` |
| GET | `/api/v1/reports?carrier_id={id}` | AUDITOR+ | List report jobs |

### 9.7 Labels & Themes

| Verb | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/labels?carrier_id={id}` | REVIEWER+ | All label overrides for carrier |
| GET | `/api/v1/labels/{screen_key}?carrier_id={id}` | REVIEWER+ | Labels for one screen namespace |
| PUT | `/api/v1/admin/ui-labels` | TENANT_ADMIN | Create or update label override |
| DELETE | `/api/v1/admin/ui-labels/{label_id}` | TENANT_ADMIN | Delete override (resets to DEFAULT_LABELS) |
| GET | `/api/v1/theme/resolved?carrier_id={id}` | REVIEWER+ | Resolved 13-token set for current user + carrier |
| GET | `/api/v1/admin/themes` | TENANT_ADMIN | List tenant's custom themes |
| POST | `/api/v1/admin/themes` | TENANT_ADMIN | Create custom theme |
| PUT | `/api/v1/admin/themes/{theme_id}` | TENANT_ADMIN | Update theme tokens |
| DELETE | `/api/v1/admin/themes/{theme_id}` | TENANT_ADMIN | Delete (checks references first) |
| PUT | `/api/v1/admin/carrier-theme-config/{carrier_id}` | TENANT_ADMIN | Set carrier default theme |
| PUT | `/api/v1/user/theme-preference` | REVIEWER+ | Set user theme preference |

### 9.8 LLM Configuration

| Verb | Path | Role | Description |
|---|---|---|---|
| GET | `/api/v1/admin/llm-config?carrier_id={id}` | TENANT_ADMIN | Get active LLM config (no API key in response) |
| POST | `/api/v1/admin/llm-config` | TENANT_ADMIN | Create/update LLM config (encrypts key) |
| PUT | `/api/v1/admin/llm-config/{config_id}` | TENANT_ADMIN | Update (re-encrypts key if provided) |
| DELETE | `/api/v1/admin/llm-config/{config_id}` | TENANT_ADMIN | Soft-delete: `is_active = FALSE` |
| POST | `/api/v1/admin/llm-config/test` | TENANT_ADMIN | Test connection; returns latency + provider |

### 9.9 Cleanup

| Verb | Path | Role | Description |
|---|---|---|---|
| POST | `/api/v1/database-cleanup/preview` | TENANT_ADMIN | Read-only row count preview |
| POST | `/api/v1/database-cleanup/execute` | TENANT_ADMIN | Body: `{ "confirm": "CONFIRM" }` |
| GET | `/api/v1/database-cleanup/history` | TENANT_ADMIN | Last 20 cleanup runs |

### 9.10 Health

| Verb | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Returns `{ status, schema, phase }` |

---

## 10. Input File Specifications

### 10.1 Supported File Formats

| Format | Extension | Detection Method |
|---|---|---|
| Excel | `.xlsx` | Filename extension (authoritative); `content_type` fallback |
| XML | `.xml` | Filename extension (authoritative) |
| CSV | `.csv` | Filename extension (authoritative) |

`application/octet-stream` content type is excluded from detection (extension only).

### 10.2 Upload Types & File Combinations

| Upload Type | Mode | Files Required | Description |
|---|---|---|---|
| Type 1 | Calc Engine | XML + Payroll XLSX + Audit XLSX | Full 3-file set. XML supplies policy config (class codes, exposure, dates, policy number, insured name). |
| Type 2 | Calc Engine | Payroll XLSX + Audit XLSX | 2-file set. No XML. Policy identity comes from XLSX fields. |
| Type 3 | Calc Engine | Single CSV | Single delimited file. |
| Display Only | Display | Single XLSX | No calculations. Pre-computed data presented read-only. |

### 10.3 File Naming Conventions (Bulk Upload)

Policies are grouped by shared filename prefix:

| Pattern | Role |
|---|---|
| `{PREFIX}_payroll.xlsx` | Payroll Detail file for policy `PREFIX` |
| `{PREFIX}_audit.xlsx` | Audit Summary Report file for policy `PREFIX` |
| `{PREFIX}.xml` | XML policy config for policy `PREFIX` |

All files with the same `PREFIX` form one policy group. Groups missing required files for their upload type are marked incomplete and shown with a warning. Complete groups are submitted first.

Bulk upload container: ZIP archive or folder drag-and-drop. ZIP files are extracted client-side via JSZip. Files starting with `.` or `__MACOSX` are skipped.

### 10.4 XLSX File Structure

**Payroll Detail XLSX (canonical source columns):**

| Source Column | Canonical Target | Data Type |
|---|---|---|
| `Client Name` / `Insured Name` | `policyholder_name` | TEXT |
| `Policy Number` | `policy_number` | TEXT |
| `CheckDate` / `Check Date` | `as_of_date` | DATE |
| `EE No` / `Employee Number` | `employee_id` | TEXT |
| `Employee Name` | `employee_name` | TEXT |
| `St.` / `State` | `state_code` | TEXT |
| `Class Code` | `class_code` | TEXT |
| `Wages` | `wages` | NUMERIC |
| `OT` / `Overtime` | `overtime` | NUMERIC |
| `DT` / `Double Time` | `double_time` | NUMERIC |
| `Tips` | `tips` | NUMERIC |
| `Net` | `net_wages` | NUMERIC |
| `Exposure` | `exposure` | NUMERIC |
| `Net Rate` | `net_rate` | NUMERIC |
| `Earned Prem.` / `Earned Premium` | `earned_premium` | NUMERIC |

**Audit Summary Report XLSX (canonical source columns):**

| Source Column | Canonical Target | Data Type |
|---|---|---|
| `Est. Payroll` / `Estimated Payroll` | `est_payroll` | NUMERIC |
| `Actual Payroll As Reported` | `actual_payroll_reported` | NUMERIC |
| `Actual Payroll As Classified` | `actual_payroll_classified` | NUMERIC |
| `Actual Reported Over (Under) Estimated` | `reported_over_under` | NUMERIC (GENERATED) |
| `Actual Reported % of Estimated` | `reported_pct` | NUMERIC |
| `Est Premium End Date` / `Est. Premium End` | `est_premium_end` | NUMERIC |
| `Actual Premium` | `actual_premium` | NUMERIC |
| `Variance` | `variance_amount` | NUMERIC (GENERATED) |
| `State` | `state_code` | TEXT |
| `Class Code` | `class_code` | TEXT |

The `AutoMappingService` reads all sheets in a multi-sheet XLSX. For audit report files, it identifies the Employee Detail section by locating a header row that contains "Employee Name", "Wages", AND "Class Code" in the same row.

### 10.5 XML File Structure

Required elements (vary slightly by carrier — AutoMappingService handles variants):

```xml
<PolicyData>
  <PolicyNumber>WC-2024-00123</PolicyNumber>
  <InsuredName>Acme Corp</InsuredName>
  <EffectiveDate>2024-01-01</EffectiveDate>
  <ExpirationDate>2024-12-31</ExpirationDate>
  <PremiumWritten>15000.00</PremiumWritten>
  <PayrollFrequency>MONTHLY</PayrollFrequency>
  <StateCode>CA</StateCode>
  <ClassCodeData>
    <ClassCode>8810</ClassCode>
    <Exposure>250000.00</Exposure>
  </ClassCodeData>
</PolicyData>
```

Three known XML variants from sample files: AM-PM Air Conditioning (`<Policy><PolicyData>` nesting), AUSPICE Home Care (different element names), Bakeland LLC (third variant). The auto-mapping algorithm handles field name differences across these variants.

### 10.6 CSV File Structure

- Header row required (first row).
- Supported delimiters: `,` (comma), `\t` (tab), `;` (semicolon). Auto-detected by `csv.Sniffer`.
- Column mapping: same 4-pass auto-mapping pipeline as XLSX.

### 10.7 Auto-Mapping Pipeline

| Pass | Confidence | Score Formula | Condition |
|---|---|---|---|
| 1 | HIGH | 1.000 | Exact match in `ingestion_field_maps` for `(carrier_id, file_type, source_field)` |
| 2 | HIGH | 0.950 | `normalise(source_field) == normalise(target_column)` |
| 3 | MEDIUM | `ratio × 0.85` | `difflib.SequenceMatcher ratio ≥ 0.75` AND type-compatible |
| 3 | LOW | `ratio × 0.60` | `ratio ≥ 0.50` (any type compatibility) |
| 4 | UNMATCHED | 0.000 | No match |

**Mandatory approval gate:** After scoring, the mapping is presented for TENANT_ADMIN review. Ingestion does not proceed until `field_mapping_session.status = APPROVED`. This gate cannot be bypassed regardless of confidence level.

### 10.8 Sample Files Reference

The following sample files are present in the project and were used as canonical references during development:

| File | Type | Company | Contents |
|---|---|---|---|
| `AM-PM_Air_Conditioning_Inc_2026_02_24.xml` | XML | AM-PM Air Conditioning Inc | Policy export: `<Policy>`, `<PolicyData>`, `<PolicyNumber>`, `<InsuredName>`, `<Premium>`, `<PayrollFrequency>`, `<ClassCodeData>` nodes |
| `AUSPICE_HOME_CARE_SOLUTIONS_LLC_2026_02_24.xml` | XML | AUSPICE Home Care Solutions LLC | Second XML variant with different element naming |
| `Bakeland_LLC_2026_02_24.xml` | XML | Bakeland LLC | Third XML variant |
| `AMPM_Air_Conditioning_Inc_2026_2_24.xlsx` | XLSX (Payroll) | AM-PM Air Conditioning Inc | Payroll data: Client Name, Policy Number, CheckDate, EE No, Employee Name, State, Class Code, Wages, OT, DT, Tips, Net, Exposure, Net Rate, Earned Prem., Census Rate, Census Prem. |
| `AMPM_Air_Conditioning_Inc_auditReport_2026_2_24.xlsx` | XLSX (Audit Report) | AM-PM Air Conditioning Inc | Pre-calculated audit summary: premium and payroll variance |
| `Bakeland_LLC_2026_2_24.xlsx` | XLSX (Payroll) | Bakeland LLC | Payroll detail file |
| `Bakeland_LLC_auditReport_2026_2_24.xlsx` | XLSX (Audit Report) | Bakeland LLC | Audit summary |
| `AUSPICE_HOME_CARE_SOLUTIONS_LLC_2026_2_24.xlsx` | XLSX (Payroll) | AUSPICE Home Care Solutions LLC | Payroll detail |
| `AUSPICE_HOME_CARE_SOLUTIONS_LLC_auditReport_2026_2_24.xlsx` | XLSX (Audit Report) | AUSPICE Home Care Solutions LLC | Audit summary |
| `Premum_Var.xlsx` | XLSX (Premium Variance) | Reference | Premium variance format: est/actual premium, variance columns |
| `Pr_var.xlsx` | XLSX (Payroll Variance) | Reference | Payroll variance: est payroll, reported payroll, classified payroll |
| `Payroll_Var.xlsx` | XLSX (Payroll Variance by Class) | Reference | Payroll variance by class code |
| `Missing_Pr.xlsx` | XLSX (Missing Payroll) | Reference | Missing payroll: Insured, Policy Number, Expected Period Start/End, Days Overdue |
| `Zero_Pr.xlsx` | XLSX (Zero Payroll) | Reference | Zero payroll: Policyholder, Policy Number, Report Date, Zero Payroll Reason, Payroll Vendor, SPRS, Agency |
| `Winkelmann_Darryl_DBA_Enoteca_2026_3_19.xlsx` | XLSX (Payroll) | Winkelmann, Darryl DBA Enoteca | Per-policy audit payroll data |
| `Winkelmann_Darryl_DBA_Enoteca_auditReport_2026_3_19.xlsx` | XLSX (Audit Report) | Winkelmann, Darryl DBA Enoteca | Pre-calculated audit report; display-only data profile |
| `Williams_Air_and_Services_LLC_DBA_Matthew_Michael_Williams_auditReport_2026_3_19.xlsx` | XLSX (Audit Report) | Williams Air and Services LLC | Audit report |
| `Yoders_Heating__Cooling_LLC_2026_3_19.xlsx` | XLSX (Payroll) | Yoder's Heating & Cooling LLC | Payroll data |
| `Yoders_Heating__Cooling_LLC_auditReport_2026_3_19.xlsx` | XLSX (Audit Report) | Yoder's Heating & Cooling LLC | Audit report |
| `Mudd_Turf_Specialties_a_corp_DBA_Mudd_Landscapes_2026_3_19.xlsx` | XLSX (Payroll) | Mudd Turf Specialties / Mudd Landscapes | Payroll data |
| `Mudd_Turf_Specialties_a_corp_DBA_Mudd_Landscapes_auditReport_2026_3_19.xlsx` | XLSX (Audit Report) | Mudd Turf Specialties / Mudd Landscapes | Audit report |
| `Mose_Rodney_an_individual_DBA_Rod_Mose__Company_auditReport_2026_3_19.xlsx` | XLSX (Audit Report) | Rod Mose & Company | Audit report |
| `Oakdale_Development_LLC_2026_3_19.xlsx` | XLSX (Payroll) | Oakdale Development LLC | Payroll data |
| `Oakdale_Development_LLC_auditReport_2026_3_19.xlsx` | XLSX (Audit Report) | Oakdale Development LLC | Audit report |
| `Oasis_Inc._2026_3_19.xlsx` | XLSX (Payroll) | Oasis Inc. | Payroll data |
| `Oasis_Inc._auditReport_2026_3_19.xlsx` | XLSX (Audit Report) | Oasis Inc. | Audit report |

---

## 11. Deployment Guide

### 11.1 Docker Compose (Local / Staging)

**Prerequisites:**
- Docker Desktop ≥ 24 with Compose v2
- Node.js 20+ (for local frontend development outside Docker)
- Python 3.12+ (for local backend development outside Docker)

**Steps:**

```bash
# 1. Copy and populate environment variables
cp .env.example .env
# Edit .env — fill in ANTHROPIC_API_KEY and any required secrets

# 2. Start all services
docker compose up --build

# 3. Run database migrations (first run only)
docker compose exec backend alembic upgrade head

# Services available at:
#   Frontend:  http://localhost:5173
#   Backend:   http://localhost:8000
#   API Docs:  http://localhost:8000/docs  (dev only)
#   Health:    http://localhost:8000/health
```

**Services defined in `docker-compose.yml`:**

| Service | Image | Port | Description |
|---|---|---|---|
| `db` | `postgres:16-alpine` | 5432 | PostgreSQL 16 with health check |
| `redis` | `redis:7-alpine` | 6380→6379 | Redis 7 |
| `api` | `./backend/Dockerfile` | 8000 | FastAPI backend; bind-mounted `./backend:/app` |
| `frontend` | `node:20-alpine` | 5173 | Vite dev server; bind-mounted `./frontend:/app` |

### 11.2 Environment Variables Reference

| Variable | Required | Description | Example |
|---|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL async DSN | `postgresql+asyncpg://auditai:auditai@db:5432/auditai` |
| `REDIS_URL` | Yes | Redis DSN | `redis://redis:6379/0` |
| `ANTHROPIC_API_KEY` | Yes* | Platform-level API key for AI narratives. *Optional if all carriers have carrier-scoped LLM config. | `sk-ant-...` |
| `ANTHROPIC_MODEL` | No | Default Anthropic model | `claude-sonnet-4-6` (default) |
| `ANTHROPIC_TIMEOUT_SECONDS` | No | LLM call timeout | `10` (default) |
| `KEYCLOAK_SERVER_URL` | Prod | Keycloak server URL | `https://auth.platform.com` |
| `KEYCLOAK_REALM` | Prod | Keycloak realm name | `audit-platform` |
| `KEYCLOAK_CLIENT_ID` | Prod | Keycloak client ID | `audit-api` |
| `SKIP_JWT_VERIFICATION` | Dev only | Bypass RS256 verification | `true` (never in prod) |
| `S3_BUCKET_NAME` | Prod | S3 bucket for file uploads | `audit-platform-uploads` |
| `S3_REGION` | Prod | AWS region | `us-east-1` |
| `S3_ACCESS_KEY_ID` | Prod | AWS access key | |
| `S3_SECRET_ACCESS_KEY` | Prod | AWS secret key | |
| `UPLOAD_DIR` | Dev | Local upload directory (dev fallback) | `/tmp/auditai_uploads` |
| `LLM_KEY_ENCRYPTION_SECRET` | Yes | Fernet key for encrypting LLM API keys | Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ENVIRONMENT` | No | `development` or `production` | `development` |
| `ALLOWED_ORIGINS` | No | CORS origins | `http://localhost:5173` |
| `LOG_LEVEL` | No | Logging level | `INFO` |
| `VITE_API_URL` | Frontend | Backend base URL for Vite | `http://localhost:8000` |

### 11.3 Database Migration Management

```bash
# Apply all pending migrations (all active tenant schemas)
alembic upgrade head

# Apply to a specific tenant schema
alembic -x target_schema=tenant_demo upgrade head

# Create a new migration
alembic revision --autogenerate -m "description_of_change"

# Rollback one step
alembic downgrade -1
```

**Multi-schema strategy:**

`alembic/env.py` works as follows:
1. On first run (schema = `public`): creates `public` schema tables (`tenants`, `carriers`, `theme_definitions`, `class_codes`).
2. On subsequent runs: queries `public.tenants WHERE status != 'DELETED'`, extracts all `schema_name` values, and runs the migration against each tenant schema.
3. Migration files use a `_s()` helper to get the current target schema and wrap DDL in `IF NOT EXISTS` guards for idempotency.

### 11.4 Production Deployment Considerations

**Stateless backend:** The FastAPI backend is fully stateless (no in-process session state). Horizontal scaling via Kubernetes deployments is supported. All shared state lives in PostgreSQL (data) and Redis (cache).

**Redis:** Required in production for JWKS caching (prevents Keycloak from being hammered on every request), calc rules cache, labels cache, theme cache, and rate-limiting. Redis must be accessible from all backend pods.

**S3-compatible storage:** Required for file uploads and report downloads in production. The `raw_file_bytes` column on `ingestion_runs` is a development-only fallback; production routes all files through S3. Reports are never served directly from the API — only pre-signed S3 URLs are returned.

**Keycloak realm configuration:**
- RSA key provider configured.
- Client definitions for the API.
- Protocol mapper for `tenant_slug` claim (string type, maps from a user attribute).
- Protocol mapper for `role` claim (single string, NOT an array — critical).
- Wildcard subdomain redirect URIs: `https://*.platform.com/*`.

**Health check endpoint:** `GET /health` returns `200 { status: "ok", schema, phase }`. Use this for Kubernetes liveness probes.

---

## 12. Testing Strategy

### 12.1 Playwright E2E Test Suite

**Baseline:** 22 specs (Phases 1–6) + 3 Phase 7BCD additions = 25 total.

**Running all E2E specs:**

```bash
cd tests-integrated/e2e
BASE_URL=http://localhost:5173 npx playwright test --reporter=html
npx playwright show-report
```

**Running only Phase 7BCD specs:**

```bash
npx playwright test tests-integrated-phase7bcd/e2e/
# spec 23: 23-ai-narrative-display.spec.ts
# spec 24: 24-llm-config.spec.ts
# spec 25: 25-field-builder.spec.ts
```

**Phase 6 E2E specs (17–21):**
- `17-database-cleanup.spec.ts`
- `18-labels-tab.spec.ts`
- `19-theme-editor.spec.ts`
- `20-user-theme-preference.spec.ts`
- `21-monthly-cycle.spec.ts` — full operational loop: ingest → process → cleanup → verify config preserved → re-ingest → verify data restored.

**Phase 7A E2E spec:**
- `22-tenant-carrier-management.spec.ts` — zero-carrier tenant provisioning, CarrierManagementPanel add/remove.

### 12.2 Backend pytest Suite

```bash
cd backend
SKIP_JWT_VERIFICATION=true pytest tests/ -v --tb=short \
  --cov=app --cov-report=term-missing

# Phase 7BCD tests
SKIP_JWT_VERIFICATION=true pytest tests-integrated-phase7bcd/backend/ -v
```

**Coverage targets:** 90%+ for all new service classes.

**Key test files:**
- `test_cleanup_service.py` — CleanupService preview + execute + preserved data verification.
- `test_label_service.py` — Label resolution chain, merge logic.
- `test_theme_service.py` — Theme resolution chain, deletion reference check.
- `test_llm_key_vault_service.py` — Fernet encrypt/decrypt.
- `test_llm_client_factory.py` — One test per provider (8 cases).
- `test_llm_config_api.py` — CRUD + test connection.
- `test_ai_narrative_service_updated.py` — New resolution chain (8 cases; `ai_narrative_enabled` not consulted).
- `test_tenant_carrier_management.py` — `add_carrier_to_tenant()` idempotency + seeding.

### 12.3 RBAC Test Suite

**File:** `scripts/RABC_testsuite.py`

Tests every endpoint against all 4 roles (anonymous, SUPER_ADMIN, TENANT_ADMIN, AUDITOR/REVIEWER) and verifies the expected HTTP status code for each combination.

```bash
python scripts/RABC_testsuite.py
```

### 12.4 Phase 7A Completion Gates (Final Baseline)

Before Phase 7BCD was implemented, the following gates were required to pass:

- [x] Zero-carrier tenant provisioning works (Step 3 optional; Activate button always enabled).
- [x] `CarrierManagementPanel` accessible under TENANT_ADMIN > Administration > Carriers.
- [x] `add_carrier_to_tenant()` seeds 22 calc rules + `carrier_llm_config` placeholder row.
- [x] `POST /api/v1/admin/carriers`, `DELETE /api/v1/admin/carriers/{carrier_id}`, and `GET /api/v1/admin/carriers/available` pass their test suites.
- [x] All 22 existing Playwright E2E specs pass.
- [x] `TenantDetail` shows carrier list as read-only.

### 12.5 Quality Checks

```bash
# Naming violations
grep -ri "auditai\|smartpay" backend/ frontend/ \
  --include="*.py" --include="*.ts" --include="*.tsx" \
  --exclude-dir=node_modules \
  && echo "FAIL: naming violation" || echo "PASS"

# No LangGraph / LangChain
grep -r "langgraph\|langchain" backend/ \
  && echo "FAIL" || echo "PASS"

# No hardcoded hex outside useTheme.ts
grep -rn "#[0-9a-fA-F]\{3,6\}" frontend/src/ \
  --include="*.tsx" --include="*.ts" \
  | grep -v "useTheme.ts" \
  && echo "FAIL: hardcoded hex found" || echo "PASS"

# No raw fetch()
grep -r "= await fetch\|= fetch(" frontend/src/ \
  && echo "FAIL: raw fetch" || echo "PASS"

# Type checking
cd backend && python -m mypy app --strict
cd frontend && npx tsc --noEmit
```

---

## 13. Known Gaps & Future Work

### 13.1 S3 File Storage (Production)

The `raw_file_bytes` column on `ingestion_runs` stores file bytes as PostgreSQL BYTEA in development mode. In production, files must be routed through S3. The `s3_key` column exists on `ingestion_runs` for the production path. The infrastructure for S3 upload is implemented in `IngestionService` but the development fallback (`raw_file_bytes`) remains the default when `S3_BUCKET_NAME` is not configured.

**Status:** Specified in V9; infrastructure implemented; production S3 routing requires `S3_BUCKET_NAME` env var to be set.

### 13.2 Exception Report Generation

The `generate_exception_report()` method in `ReportService` was stubbed in Phase 4 and fully implemented in Phase 5. The `report_jobs` table and async job flow are complete.

**Status:** Implemented in Phase 5.

### 13.3 Post-Phase 7 UX Remediation

The `Post_Phase7_UX_Remediation_Implementation_Plan.md` document in the project files identifies UX improvement items identified after Phase 7 was complete. These are additive changes and do not affect existing functionality.

[Specified in post-Phase 7 plan — not confirmed in repository; verify before documenting]

### 13.4 `carriers.ai_narrative_enabled` Column

This column in `public.carriers` is retained for backward compatibility but is no longer evaluated in `AInarrativeService` after Phase 7C. Any existing data in this column has no operational effect. A future cleanup migration could safely drop this column.

### 13.5 Multi-Format Ingestion — XML Variant Handling

The `AutoMappingService` handles three known XML variants (AM-PM, AUSPICE, Bakeland). Additional carrier XML variants may require extending the XML field extraction logic in `_read_source_fields()`.

### 13.6 Display Config `conditional_format_rule`

The `carrier_display_config.conditional_format_rule` column (JSONB) is defined in the schema and ORM model but the UI for configuring conditional formatting rules (e.g., colour a cell red when variance exceeds 30%) is not yet implemented.

[Specified in V9 S15 — schema present; UI not confirmed in repository]

### 13.7 `TENANT_ADMIN` Two-Person Approval

The two-step calc rule approval workflow (DRAFT → PENDING_REVIEW → ACTIVE) can be completed by a single TENANT_ADMIN. V9's original intent was to require a second human approval, but this was resolved in Decision #6 as "self-approval within the TENANT_ADMIN role." A future enhancement could enforce two-person approval by requiring two distinct Keycloak user UUIDs in the approval chain.

### 13.8 Keycloak `multi-step` Admin UI

The current `TenantProvisioningService` creates Keycloak users via the Keycloak Admin API. The implementation details of this step (error handling, retry logic, invitation email sending) are not confirmed in the repository from project files alone.

[Specified in V9 S12 — implementation details not confirmed in repository; verify against live code]

### 13.9 Playwright Test Environment Requirements

The Phase 7BCD Playwright tests require:
- `LLM_KEY_ENCRYPTION_SECRET` set to a valid Fernet key.
- `ANTHROPIC_API_KEY` for live LLM tests (tagged `@live`; skipped in CI by default unless `RUN_LIVE_LLM_TESTS=true`).
- Playwright browsers installed: `npx playwright install`.

### 13.10 Known TODOs in Codebase

Search the repository for `# TODO` and `// TODO` markers. Phase-specific stubs were placed in:
- `ingestion_service.py` — Phase 3 and Phase 4 entry points (resolved in respective phases).
- `useLabels.ts` — `// Phase 3: TODO — merge carrier_ui_labels overrides from API` (resolved in Phase 6).
- `useTheme.ts` — `// Phase 6: full dynamic useTheme()` (resolved in Phase 6).
- `CarrierConfigHub.tsx` — `case 4` and `case 6` rendered `<ComingSoonTab>` (resolved in Phase 6).

---

*This document was generated from the V9 Architecture Document and the live repository at https://github.com/Sudheer7183/workmencompMerged. Where the repository is authoritative.*
