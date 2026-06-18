/**
 * ColorPickerInput.test.tsx — Phase 6
 *
 * 5 test cases for the colour picker component.
 */

import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ColorPickerInput } from "@/features/carrier-config/components/theme/ColorPickerInput";

describe("ColorPickerInput", () => {
  it("renders the hex input with the current value", () => {
    render(
      <ColorPickerInput
        value="4ade80"
        onChange={vi.fn()}
        baseValue="4ade80"
        label="Brand"
      />
    );
    const input = screen.getByRole("textbox") as HTMLInputElement;
    expect(input.value).toBe("4ADE80");
  });

  it("calls onChange with lowercase hex on valid input", () => {
    const onChange = vi.fn();
    render(
      <ColorPickerInput
        value="4ade80"
        onChange={onChange}
        baseValue="4ade80"
        label="Brand"
      />
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "FF5733" } });
    expect(onChange).toHaveBeenCalledWith("ff5733");
  });

  it("does not call onChange on invalid hex input", () => {
    const onChange = vi.fn();
    render(
      <ColorPickerInput
        value="4ade80"
        onChange={onChange}
        baseValue="4ade80"
        label="Brand"
      />
    );
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "GGGGGG" } });
    expect(onChange).not.toHaveBeenCalled();
  });

  it("shows reset button when value differs from base", () => {
    render(
      <ColorPickerInput
        value="ff5733"
        onChange={vi.fn()}
        baseValue="4ade80"
        label="Brand"
      />
    );
    expect(screen.getByTitle(/reset/i)).toBeInTheDocument();
  });

  it("hides reset button when value matches base", () => {
    render(
      <ColorPickerInput
        value="4ade80"
        onChange={vi.fn()}
        baseValue="4ade80"
        label="Brand"
      />
    );
    expect(screen.queryByTitle(/reset/i)).not.toBeInTheDocument();
  });
});
