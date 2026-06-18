

import JSZip from "jszip";



export type BulkSlotType = "xml" | "payroll" | "audit" | "display" | "csv";

export interface BulkFileEntry {
  slotType: BulkSlotType;
  file: File;
}

export interface PolicyFileGroup {
  policyKey: string;
  files: BulkFileEntry[];
  isComplete: boolean;
}

export interface GroupingResult {
  groups: PolicyFileGroup[];
  unmatched: File[];
}

// ─────────────────────────────────────────────────────────────────────────────
// Regex constants
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Matches a date suffix at the end of a stem:
 *   _YYYY_M_D                     e.g.  _2026_3_19
 *   _YYYY_MM_DD                   e.g.  _2026_02_24
 *   followed optionally by _updated, _v2, etc.
 */
const RE_DATE_SUFFIX = /_\d{4}_\d{1,2}_\d{1,2}(?:_\w+)*$/i;

/** Marks this file as the audit report. */
const RE_AUDIT_MARKER = /_auditreport/i;

/** Legacy short-form keyword suffixes (no date). */
const RE_LEGACY_PAYROLL = /_payroll$|_pay$/i;
const RE_LEGACY_AUDIT   = /_audit$|_auditreport$|_report$/i;

/**
 * Matches OS-generated copy suffixes added when duplicate filenames exist:
 *   " (1)"  " (2)"  "_(1)"  "_(2)"
 * These appear when users copy files or when macOS/Windows ZIP archives
 * contain files extracted with auto-renamed duplicates.
 */
const RE_COPY_SUFFIX = /[\s_]+\(\d+\)$/;

// ─────────────────────────────────────────────────────────────────────────────
// Core parsing — returns (policyKey, rawSlot)
// rawSlot "payroll_or_display" means the caller picks based on mode.
// ─────────────────────────────────────────────────────────────────────────────

type RawSlot = BulkSlotType | "payroll_or_display";

function parseFilename(filename: string): { key: string; raw: RawSlot } | null {
  const lower = filename.toLowerCase();

  // ── Extension-based hard classification ───────────────────────────────────
  if (lower.endsWith(".xml")) {
    const stem = filename.replace(/\.xml$/i, "")
      .replace(RE_COPY_SUFFIX, "")   // strip " (1)" copy suffix before normalising
      .replace(/ /g, "_");
    const key  = RE_DATE_SUFFIX.test(stem)
      ? stem.replace(RE_DATE_SUFFIX, "")
      : stem.replace(RE_LEGACY_AUDIT, "").replace(RE_LEGACY_PAYROLL, "");
    return { key: key.replace(/[_]+$/, ""), raw: "xml" };
  }
  if (lower.endsWith(".csv")) {
    return { key: filename.replace(/\.csv$/i, ""), raw: "csv" };
  }
  if (!lower.endsWith(".xlsx")) return null;

  // ── XLSX: strip copy suffix first, then normalise spaces ─────────────────
  const stem = filename.replace(/\.xlsx$/i, "")
    .replace(RE_COPY_SUFFIX, "")     // strip " (1)", " (2)" etc before key extraction
    .replace(/ /g, "_");

  // Strategy A — date-convention filenames
  if (RE_DATE_SUFFIX.test(stem)) {
    const withoutDate = stem.replace(RE_DATE_SUFFIX, "");
    if (RE_AUDIT_MARKER.test(withoutDate)) {
      // e.g. "Oasis_Inc._auditReport"  →  key="Oasis_Inc."
      const key = withoutDate.replace(RE_AUDIT_MARKER, "").replace(/[_]+$/, "");
      return { key, raw: "audit" };
    }
    // e.g. "Oasis_Inc."  →  key="Oasis_Inc."
    const key = withoutDate.replace(/[_]+$/, "");
    return { key, raw: "payroll_or_display" };
  }

  // Strategy B — legacy short-form (no date)
  if (RE_LEGACY_PAYROLL.test(stem)) {
    return { key: stem.replace(RE_LEGACY_PAYROLL, ""), raw: "payroll" };
  }
  if (RE_LEGACY_AUDIT.test(stem)) {
    return { key: stem.replace(RE_LEGACY_AUDIT, ""), raw: "audit" };
  }

  // Strategy C — no recognised marker → treat as policy detail file
  return { key: stem, raw: "payroll_or_display" };
}

// ─────────────────────────────────────────────────────────────────────────────
// Public helpers (kept for backwards-compat with any direct callers)
// ─────────────────────────────────────────────────────────────────────────────

export function detectSlotType(filename: string): BulkSlotType | null {
  const result = parseFilename(filename);
  if (!result) return null;
  return result.raw === "payroll_or_display" ? "payroll" : result.raw;
}

export function extractPolicyKey(filename: string): string {
  return parseFilename(filename)?.key ?? filename;
}

// ─────────────────────────────────────────────────────────────────────────────
// Main grouping function
// ─────────────────────────────────────────────────────────────────────────────

export function groupFilesIntoPolicies(
  files: File[],
  ingestionMode: "calc_engine" | "display_only",
  uploadType: "type1" | "type2" = "type2",
): GroupingResult {
  const groupMap = new Map<string, BulkFileEntry[]>();
  const unmatched: File[] = [];

  // Deduplicate files by name to handle ZIP archives that contain duplicates
  // (e.g. macOS ZIP files with both original and __MACOSX copies, or
  // Windows " (1)" duplicates that were already stripped to the same key).
  const seenFileNames = new Set<string>();
  const dedupedFiles = files.filter((f) => {
    // Normalise name for dedup comparison: strip copy suffix, lowercase
    const normName = f.name.replace(/[\s_]+\(\d+\)\./, ".").toLowerCase();
    if (seenFileNames.has(normName)) return false;
    seenFileNames.add(normName);
    return true;
  });

  for (const file of dedupedFiles) {
    const parsed = parseFilename(file.name);

    if (!parsed) {
      unmatched.push(file);
      continue;
    }

    // Resolve ambiguous "payroll_or_display" based on selected mode
    const slotType: BulkSlotType =
      parsed.raw === "payroll_or_display"
        ? ingestionMode === "display_only" ? "display" : "payroll"
        : parsed.raw;

    // In display_only mode, skip XML and plain payroll files
    if (ingestionMode === "display_only" && (slotType === "xml" || slotType === "csv")) {
      unmatched.push(file);
      continue;
    }

    const key = parsed.key;
    const arr = groupMap.get(key) ?? [];
    arr.push({ slotType, file });
    groupMap.set(key, arr);
  }

  const groups: PolicyFileGroup[] = [];

  for (const [policyKey, entries] of groupMap.entries()) {
    const slotTypes = new Set(entries.map((e) => e.slotType));

    let isComplete: boolean;
    if (ingestionMode === "display_only") {
      isComplete = slotTypes.has("display");
    } else if (uploadType === "type1") {
      isComplete =
        slotTypes.has("xml") && slotTypes.has("payroll") && slotTypes.has("audit");
    } else {
      // Type 2: payroll + audit
      isComplete = slotTypes.has("payroll") && slotTypes.has("audit");
    }

    groups.push({ policyKey, files: entries, isComplete });
  }

  // Complete groups first, then alphabetical
  groups.sort((a, b) => {
    if (a.isComplete !== b.isComplete) return a.isComplete ? -1 : 1;
    return a.policyKey.localeCompare(b.policyKey);
  });

  return { groups, unmatched };
}

// ─────────────────────────────────────────────────────────────────────────────
// ZIP extraction
// ─────────────────────────────────────────────────────────────────────────────

export async function extractZipFiles(zipFile: File): Promise<File[]> {
  const zip = await JSZip.loadAsync(zipFile);
  const extracted: File[] = [];

  const promises = Object.entries(
    zip.files as Record<string, {
      dir: boolean;
      name: string;
      async: (type: string) => Promise<Uint8Array>;
    }>
  ).map(async ([, entry]) => {
    if (entry.dir) return;
    const name = entry.name.split("/").pop() ?? entry.name;
    if (name.startsWith(".") || name.startsWith("__MACOSX")) return;
    if (!/\.(xlsx|xml|csv)$/i.test(name)) return;

    const uint8 = await entry.async("uint8array");
    // Set the correct MIME type based on extension so the backend content_type
    // fallback path also works correctly (filename check is now authoritative).
    const mimeType = name.toLowerCase().endsWith(".xlsx")
      ? "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
      : name.toLowerCase().endsWith(".xml")
        ? "application/xml"
        : name.toLowerCase().endsWith(".csv")
          ? "text/csv"
          : "application/octet-stream";
    extracted.push(new File([new Blob([uint8], { type: mimeType })], name, { type: mimeType }));
  });

  await Promise.all(promises);
  return extracted;
}