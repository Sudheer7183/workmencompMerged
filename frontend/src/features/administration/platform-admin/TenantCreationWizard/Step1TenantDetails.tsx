/**
 * Step1TenantDetails — Tenant name, subdomain, tenant type.
 *
 * V9 S12.2:
 * - Auto-generates slug from tenant name (lowercase, spaces→hyphens, strip specials)
 * - Validates regex ^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$
 * - Checks reserved subdomain list
 * - Live uniqueness check: GET /platform/tenants/{slug} (404 = available, 200 = taken)
 * - Subdomain preview: {slug}.{VITE_PLATFORM_DOMAIN}
 * - Immutability note displayed below the field
 *
 * Fix: replaced label_shared("platform_wizard_step", "platform_wizard_step")1
 * with label_platform_admin("step1.title", "Tenant Details") per V9 S23.3.
 */

import React, { useState, useCallback, useEffect, useRef } from "react";
import axios from "axios";
import { useLabels } from "@/hooks/useLabels";

export interface Step1Data {
  tenantName: string;
  slug: string;
  tenantType: string;
}

interface Props {
  initial: Step1Data | null;
  onNext: (data: Step1Data) => void;
}

const RESERVED_SUBDOMAINS = new Set([
  "www", "api", "app", "admin", "platform", "mail",
  "auth", "health", "docs", "redoc", "cdn", "assets", "static",
]);

const SLUG_REGEX = /^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$/;
const PLATFORM_DOMAIN = import.meta.env.VITE_PLATFORM_DOMAIN ?? "platform.local";

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-|-$/g, "");
}

type SlugStatus = "idle" | "checking" | "available" | "taken" | "reserved" | "invalid";

export function Step1TenantDetails({ initial, onNext }: Props): React.JSX.Element {
  const label_platform_admin = useLabels("platform_admin");
  const label_shared = useLabels("shared");
  const [tenantName, setTenantName] = useState(initial?.tenantName ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [tenantType, setTenantType] = useState(initial?.tenantType ?? "AUDIT_COMPANY");
  const [slugStatus, setSlugStatus] = useState<SlugStatus>("idle");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-generate slug from tenant name
  useEffect(() => {
    if (!initial) {
      const generated = slugify(tenantName);
      setSlug(generated);
    }
  }, [tenantName, initial]);

  // Live uniqueness check with debounce
  const checkSlug = useCallback((value: string) => {
    if (!value) { setSlugStatus("idle"); return; }
    if (!SLUG_REGEX.test(value)) { setSlugStatus("invalid"); return; }
    if (RESERVED_SUBDOMAINS.has(value)) { setSlugStatus("reserved"); return; }

    setSlugStatus("checking");
    axios
      .get(`/platform/tenants/${value}`)
      .then(() => setSlugStatus("taken"))   // 200 = already exists
      .catch((err: unknown) => {
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          setSlugStatus("available");
        } else {
          setSlugStatus("idle");
        }
      });
  }, []);

  const handleSlugChange = (value: string): void => {
    setSlug(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => checkSlug(value), 500);
  };

  const slugErrorMsg =
    slugStatus === "taken"
      ? label_platform_admin("subdomain.taken", "This subdomain is already taken.")
      : slugStatus === "reserved"
      ? label_platform_admin("subdomain.reserved", "This subdomain is reserved.")
      : slugStatus === "invalid"
      ? "Must match pattern [a-z0-9][a-z0-9-]{1,61}[a-z0-9]"
      : null;

  const canProceed =
    tenantName.trim().length > 0 &&
    slug.length > 0 &&
    (slugStatus === "available" || slugStatus === "idle") &&
    !slugErrorMsg;

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    if (!canProceed) return;
    onNext({ tenantName: tenantName.trim(), slug, tenantType });
  };

  return (
    <form className="wizard-step" onSubmit={handleSubmit}>
      {/* FIX: was label_shared("platform_wizard_step", "platform_wizard_step")1 */}
      <h2 className="wizard-step__title">
        {label_platform_admin("step1.title", "Tenant Details")}
      </h2>

      <div className="form-field">
        <label className="form-field__label" htmlFor="tenant-name">
          {label_platform_admin("field.tenant_name", "Tenant Name")}
        </label>
        <input
          id="tenant-name"
          className="form-field__input"
          type="text"
          value={tenantName}
          onChange={(e) => setTenantName(e.target.value)}
          required
        />
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="tenant-slug">
          {label_platform_admin("field.subdomain", "Subdomain")}
        </label>
        <input
          id="tenant-slug"
          className={`form-field__input ${slugErrorMsg ? "form-field__input--error" : ""}`}
          type="text"
          value={slug}
          onChange={(e) => handleSlugChange(e.target.value)}
        />
        {slugStatus === "checking" && (
          <p className="form-field__hint">{label_shared("loading", "Loading…")}</p>
        )}
        {slugStatus === "available" && (
          <p className="form-field__hint form-field__hint--success">Available</p>
        )}
        {slugErrorMsg && (
          <p className="form-field__error" role="alert">
            {slugErrorMsg}
          </p>
        )}
        <p className="form-field__hint">
          <span className="subdomain-preview">
            {slug || "your-tenant"}.{PLATFORM_DOMAIN}
          </span>
        </p>
        <p className="form-field__note">
          {label_platform_admin("subdomain.immutable_note", "Cannot be changed after creation.")}
        </p>
      </div>

      <div className="form-field">
        <label className="form-field__label" htmlFor="tenant-type">
          {label_platform_admin("field.tenant_type", "Tenant Type")}
        </label>
        <select
          id="tenant-type"
          className="form-field__select"
          value={tenantType}
          onChange={(e) => setTenantType(e.target.value)}
        >
          <option value="AUDIT_COMPANY">Audit Company</option>
          <option value="CARRIER">Carrier</option>
          <option value="BROKER">Broker</option>
        </select>
      </div>

      <div className="wizard-step__actions">
        <button type="submit" className="btn btn--primary" disabled={!canProceed}>
          {label_platform_admin("btn.next", "Next")}
        </button>
      </div>
    </form>
  );
}