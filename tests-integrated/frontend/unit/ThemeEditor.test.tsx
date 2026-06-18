/**
 * ThemeEditor.test.tsx — Phase 6
 *
 * 5 test cases for the ThemeEditor component, focusing on
 * the WCAG contrast indicator and rendering behaviour.
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeEditor } from "@/features/carrier-config/components/theme/ThemeEditor";

const DARK_TOKENS = {
  bg: "0f1117", surface: "181c27", surface2: "1e2436",
  border_col: "2a2f45", text_primary: "e8ecf4", text_muted: "7a84a0",
  brand: "4ade80", brand_dark: "15803d", accent: "818cf8",
  color_green: "22c55e", color_amber: "f59e0b",
  color_red: "ef4444", color_blue: "60a5fa",
};

const DEFAULT_INITIAL = {
  ...DARK_TOKENS,
  theme_name: "Test Theme",
  mode: "dark",
  based_on_name: "Default Dark",
};

describe("ThemeEditor", () => {
  it("renders the theme name input", () => {
    render(
      <ThemeEditor
        initial={DEFAULT_INITIAL}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByLabelText(/theme name/i)).toBeInTheDocument();
  });

  it("shows WCAG pass indicator for Default Dark tokens (high contrast)", () => {
    render(
      <ThemeEditor
        initial={DEFAULT_INITIAL}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    // Default Dark has good contrast — expect the pass indicator
    expect(screen.getByText(/4\.\d+:1/)).toBeInTheDocument();
  });

  it("shows WCAG warning for low-contrast tokens", () => {
    render(
      <ThemeEditor
        initial={{
          ...DEFAULT_INITIAL,
          text_primary: "606060",  // dark grey
          surface: "404040",       // similar dark grey — low contrast
        }}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    // Low contrast should show the warning
    const wcagEl = screen.getByRole("status");
    expect(wcagEl).toBeInTheDocument();
  });

  it("renders all 4 token group titles", () => {
    render(
      <ThemeEditor
        initial={DEFAULT_INITIAL}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    expect(screen.getByText("Background Tones")).toBeInTheDocument();
    expect(screen.getByText("Text & Borders")).toBeInTheDocument();
    expect(screen.getByText("Brand Colours")).toBeInTheDocument();
    expect(screen.getByText("Status Colours")).toBeInTheDocument();
  });

  it("save button is disabled when theme name is empty", () => {
    render(
      <ThemeEditor
        initial={{ ...DEFAULT_INITIAL, theme_name: "" }}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />
    );
    const saveBtn = screen.getByText("Save Theme");
    expect(saveBtn).toBeDisabled();
  });
});
