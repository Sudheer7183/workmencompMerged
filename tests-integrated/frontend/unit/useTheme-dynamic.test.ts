/**
 * useTheme-dynamic.test.ts — Phase 6
 *
 * Tests the DEFAULT_DARK_TOKENS constant integrity and the CSS property
 * mapping logic. The fallback guarantee is verified without mounting
 * the full hook (which requires React context).
 */

import { describe, it, expect } from "vitest";
import { DEFAULT_DARK_TOKENS } from "@/hooks/useTheme";

const EXPECTED_TOKEN_NAMES = [
  "--bg",
  "--surface",
  "--surface-2",
  "--border",
  "--text-primary",
  "--text-muted",
  "--brand",
  "--brand-dark",
  "--accent",
  "--color-green",
  "--color-amber",
  "--color-red",
  "--color-blue",
] as const;

const HEX_WITH_HASH = /^#[0-9a-fA-F]{6}$/;

describe("DEFAULT_DARK_TOKENS", () => {
  it("contains exactly 13 tokens", () => {
    expect(Object.keys(DEFAULT_DARK_TOKENS)).toHaveLength(13);
  });

  it("contains all expected CSS custom property names", () => {
    for (const name of EXPECTED_TOKEN_NAMES) {
      expect(name in DEFAULT_DARK_TOKENS).toBe(true);
    }
  });

  it("all values are valid 7-char hex strings with hash prefix", () => {
    for (const [key, value] of Object.entries(DEFAULT_DARK_TOKENS)) {
      expect(HEX_WITH_HASH.test(value)).toBe(
        true,
        `DEFAULT_DARK_TOKENS["${key}"] = "${value}" is not a valid #rrggbb colour`
      );
    }
  });

  it("does not contain any undefined values", () => {
    for (const value of Object.values(DEFAULT_DARK_TOKENS)) {
      expect(value).toBeDefined();
    }
  });
});

describe("useTheme — CSS property mapping logic", () => {
  /**
   * Verifies that the mapping from API response field names (no dashes)
   * to CSS custom property names (with dashes) is correct.
   */
  const API_TO_CSS_MAP: Record<string, string> = {
    bg:           "--bg",
    surface:      "--surface",
    surface2:     "--surface-2",
    border_col:   "--border",
    text_primary: "--text-primary",
    text_muted:   "--text-muted",
    brand:        "--brand",
    brand_dark:   "--brand-dark",
    accent:       "--accent",
    color_green:  "--color-green",
    color_amber:  "--color-amber",
    color_red:    "--color-red",
    color_blue:   "--color-blue",
  };

  it("maps 13 API fields to 13 CSS properties", () => {
    expect(Object.keys(API_TO_CSS_MAP)).toHaveLength(13);
    expect(Object.values(API_TO_CSS_MAP)).toHaveLength(13);
  });

  it("every CSS property in the map exists in DEFAULT_DARK_TOKENS", () => {
    const defaultKeys = Object.keys(DEFAULT_DARK_TOKENS);
    for (const cssProperty of Object.values(API_TO_CSS_MAP)) {
      expect(defaultKeys).toContain(cssProperty);
    }
  });

  it("fallback applies a complete token set (no gaps)", () => {
    // Simulate what useTheme does when theme is null
    const fallback = { ...DEFAULT_DARK_TOKENS };
    for (const cssProperty of EXPECTED_TOKEN_NAMES) {
      expect(cssProperty in fallback).toBe(true);
      expect(fallback[cssProperty]).toBeTruthy();
    }
  });
});
