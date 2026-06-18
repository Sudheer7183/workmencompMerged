/**
 * ReportTemplateTab.test.tsx — Phase 5 unit tests.
 *
 * Tests for the ReportTemplateTab component: all form fields, save flow,
 * logo upload, colour validation, PDF preview, RBAC-free rendering,
 * no hardcoded hex, labels from useLabels.
 *
 * Per Phase 5 prompt Section 7 test spec.
 */

import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, test, expect, vi, beforeEach } from "vitest";
import { ReportTemplateTab } from "@/features/carrier-config/components/ReportTemplateTab";
import * as reportsApi from "@/features/reports/services/reportsApi";

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("@/hooks/useLabels", () => ({
  useLabels: () => ({
    loading: "Loading…",
    saving: "Saving…",
    uploading: "Uploading…",
    saved: "✓ Saved",
    remove: "Remove",
    report_template_logo_section: "Report Logo",
    report_template_colours_section: "Brand Colours",
    report_contact_block_section: "Footer Contact Block (HTML)",
    report_primary_colour: "Primary Colour",
    report_secondary_colour: "Secondary Colour",
    report_save_template: "Save Template",
    report_pdf_preview: "PDF Preview",
    report_logo_upload: "Upload Logo",
    report_logo_using_tenant: "Using tenant branding logo (not set)",
    report_colour_invalid: "Must be a 6-character hex code",
    report_contact_block_char_limit: " / 1000 characters.",
    report_template_load_error: "Failed to load template.",
    report_template_save_error: "Failed to save template.",
    report_logo_upload_error: "Failed to upload logo.",
    report_preview_failed: "PDF preview failed.",
  }),
}));

vi.mock("@/features/reports/services/reportsApi", () => ({
  getReportTemplate: vi.fn(),
  putReportTemplate: vi.fn(),
  uploadReportLogo: vi.fn(),
  generateReport: vi.fn(),
  getReportStatus: vi.fn(),
}));

const mockGetTemplate = vi.mocked(reportsApi.getReportTemplate);
const mockPutTemplate = vi.mocked(reportsApi.putReportTemplate);
const mockUploadLogo = vi.mocked(reportsApi.uploadReportLogo);
const mockGenerateReport = vi.mocked(reportsApi.generateReport);
const mockGetStatus = vi.mocked(reportsApi.getReportStatus);

function defaultTemplate() {
  return {
    carrier_id: 1,
    logo_url: null,
    primary_colour: "1A3C5E",
    secondary_colour: "2E86C1",
    contact_block: "",
  };
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe("ReportTemplateTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetTemplate.mockResolvedValue(defaultTemplate());
    mockPutTemplate.mockResolvedValue(defaultTemplate());
  });

  test("renders logo upload zone", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("logo-upload-btn"));
    expect(screen.getByTestId("logo-upload-btn")).toBeTruthy();
  });

  test("renders primary colour hex input and swatch", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("primary-colour-input"));
    const input = screen.getByTestId("primary-colour-input") as HTMLInputElement;
    expect(input).toBeTruthy();
    expect(input.value).toBe("1A3C5E");
    // Swatch should be present (adjacent span with background)
    const swatch = input
      .closest(".report-template-tab__colour-input-row")
      ?.querySelector(".report-template-tab__colour-swatch");
    expect(swatch).toBeTruthy();
  });

  test("renders secondary colour hex input and swatch", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("secondary-colour-input"));
    const input = screen.getByTestId(
      "secondary-colour-input"
    ) as HTMLInputElement;
    expect(input.value).toBe("2E86C1");
  });

  test("renders contact block textarea", async () => {
    mockGetTemplate.mockResolvedValue({
      ...defaultTemplate(),
      contact_block: "<p>Existing footer</p>",
    });
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("contact-block-input"));
    const textarea = screen.getByTestId(
      "contact-block-input"
    ) as HTMLTextAreaElement;
    expect(textarea.value).toBe("<p>Existing footer</p>");
  });

  test("Save Template button calls PUT endpoint", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("save-template-btn"));
    fireEvent.click(screen.getByTestId("save-template-btn"));

    await waitFor(() => {
      expect(mockPutTemplate).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ primary_colour: "1A3C5E" })
      );
    });
  });

  test("save success toast shown after successful save", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("save-template-btn"));
    fireEvent.click(screen.getByTestId("save-template-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("save-success-toast")).toBeTruthy();
    });
  });

  test("logo upload calls POST report-logo endpoint", async () => {
    mockUploadLogo.mockResolvedValue({
      logo_url: "http://minio/bucket/logo.png",
    });

    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("logo-upload-btn"));

    // Simulate file input change
    const fileInput = document
      .querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File([new Uint8Array(100)], "logo.png", {
      type: "image/png",
    });
    Object.defineProperty(fileInput, "files", {
      value: [file],
      writable: false,
    });
    fireEvent.change(fileInput);

    await waitFor(() => {
      expect(mockUploadLogo).toHaveBeenCalledWith(1, file);
    });
  });

  test("logo preview shown when logo_url is set", async () => {
    mockGetTemplate.mockResolvedValue({
      ...defaultTemplate(),
      logo_url: "http://minio/bucket/carrier-logo.png",
    });

    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => {
      const img = document.querySelector(
        ".report-template-tab__logo-preview"
      ) as HTMLImageElement;
      expect(img).toBeTruthy();
      expect(img.src).toContain("carrier-logo.png");
    });
  });

  test("primary colour input validates 6-char hex — invalid disables save", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("primary-colour-input"));

    fireEvent.change(screen.getByTestId("primary-colour-input"), {
      target: { value: "ZZZZZZ" },
    });

    await waitFor(() => {
      const saveBtn = screen.getByTestId("save-template-btn");
      expect(saveBtn).toBeDisabled();
    });
  });

  test("PDF Preview button calls generate with book_summary + pdf format", async () => {
    mockGenerateReport.mockResolvedValue({ job_id: "preview-job-uuid" });
    mockGetStatus.mockResolvedValue({
      job_id: "preview-job-uuid",
      status: "COMPLETE",
      file_url: "http://minio/bucket/preview.pdf",
      report_type: "book_summary",
      output_format: "pdf",
      requested_at: null,
      completed_at: null,
      error_detail: null,
    });

    const openSpy = vi.spyOn(window, "open").mockImplementation(() => null);

    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("pdf-preview-btn"));
    fireEvent.click(screen.getByTestId("pdf-preview-btn"));

    await waitFor(() => {
      expect(mockGenerateReport).toHaveBeenCalledWith(
        expect.objectContaining({
          carrier_id: 1,
          report_type: "book_summary",
          output_format: "pdf",
        })
      );
    });
  });

  test("no hardcoded hex in rendered output", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("save-template-btn"));

    const { container } = render(<ReportTemplateTab carrierId={1} />);
    const html = container.innerHTML;

    // Colour swatch uses inline style with background — that's the only allowed hex
    // Strip the swatch styles and check the rest
    const htmlWithoutSwatches = html.replace(
      /style="background-color: #[0-9a-fA-F]{6}"/g,
      ""
    );
    expect(htmlWithoutSwatches).not.toMatch(/style="[^"]*#[0-9a-fA-F]{3,6}/);
  });

  test("all labels from useLabels — no raw string literals in buttons", async () => {
    render(<ReportTemplateTab carrierId={1} />);
    await waitFor(() => screen.getByTestId("save-template-btn"));

    // Button text should come from useLabels
    expect(screen.getByTestId("save-template-btn").textContent).toBe(
      "Save Template"
    );
    expect(screen.getByTestId("pdf-preview-btn").textContent).toBe(
      "PDF Preview"
    );
    expect(screen.getByTestId("logo-upload-btn").textContent).toBe(
      "Upload Logo"
    );
  });
});
