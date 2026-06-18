/**
 * ColorPickerInput — Phase 6 Theme Editor component.
 *
 * Addendum S6.2: Colour swatch (24×24px) + hex text input (6 chars, no '#')
 * + click-swatch popover with native colour wheel.
 * Reset button (↺) restores the base theme value; amber dot when value
 * differs from base.
 *
 * All colours flow through CSS custom properties — no hardcoded hex
 * outside DEFAULT_DARK_TOKENS in useTheme.ts.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";

const HEX_RE = /^[0-9a-fA-F]{6}$/;

interface ColorPickerInputProps {
  /** Current 6-char hex value (no '#'). */
  value: string;
  /** Called with new 6-char hex (no '#') when value changes. */
  onChange: (hex: string) => void;
  /** Base theme value — used for the ↺ reset button. */
  baseValue: string;
  /** Accessible label for the input. */
  label: string;
}

export function ColorPickerInput({
  value,
  onChange,
  baseValue,
  label,
}: ColorPickerInputProps): React.JSX.Element {
  const [open, setOpen] = useState(false);
  const [hexInput, setHexInput] = useState(value.toUpperCase());
  const popoverRef = useRef<HTMLDivElement>(null);
  const swatchRef = useRef<HTMLButtonElement>(null);

  // Keep hex input in sync when parent value changes.
  useEffect(() => {
    setHexInput(value.toUpperCase());
  }, [value]);

  // Close popover on outside click.
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        swatchRef.current &&
        !swatchRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const handleHexBlur = useCallback(() => {
    const trimmed = hexInput.trim().replace(/^#/, "");
    if (HEX_RE.test(trimmed)) {
      onChange(trimmed.toLowerCase());
    } else {
      // Reset display to last valid value.
      setHexInput(value.toUpperCase());
    }
  }, [hexInput, onChange, value]);

  const handleHexChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/^#/, "");
    setHexInput(raw.toUpperCase());
    if (HEX_RE.test(raw)) {
      onChange(raw.toLowerCase());
    }
  };

  const handleNativeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Native colour picker returns "#rrggbb" — strip the '#'.
    const hex = e.target.value.slice(1).toLowerCase();
    onChange(hex);
    setHexInput(hex.toUpperCase());
  };

  const isInvalid = !HEX_RE.test(hexInput.replace(/^#/, ""));
  const isModified = value.toLowerCase() !== baseValue.toLowerCase();

  return (
    <div className="color-picker-input">
      {/* Swatch button — opens popover */}
      <button
        ref={swatchRef}
        type="button"
        className={`color-picker-input__swatch${isModified ? " color-picker-input__swatch--modified" : ""}`}
        style={{ backgroundColor: `#${value}` }}
        onClick={() => setOpen((v) => !v)}
        aria-label={`Open colour picker for ${label}`}
        aria-expanded={open}
      />

      {/* Hex text input */}
      <input
        type="text"
        className={`color-picker-input__hex${isInvalid ? " color-picker-input__hex--invalid" : ""}`}
        value={hexInput}
        maxLength={6}
        onChange={handleHexChange}
        onBlur={handleHexBlur}
        aria-label={`Hex colour value for ${label}`}
        spellCheck={false}
      />

      {/* Reset button — shown when value differs from base */}
      {isModified && (
        <button
          type="button"
          className="color-picker-input__reset"
          onClick={() => onChange(baseValue)}
          title={`Reset to base theme value (#${baseValue})`}
          aria-label={`Reset ${label} to base theme value`}
        >
          ↺
        </button>
      )}

      {/* Colour wheel popover */}
      {open && (
        <div
          ref={popoverRef}
          className="color-picker-input__popover"
          role="dialog"
          aria-label={`Colour wheel for ${label}`}
        >
          <input
            type="color"
            className="color-picker-input__native"
            value={`#${value}`}
            onChange={handleNativeChange}
            aria-label={`Native colour picker for ${label}`}
          />
          <p
            style={{
              margin: "var(--space-2) 0 0",
              fontSize: "0.7rem",
              color: "var(--text-muted)",
              textAlign: "center",
            }}
          >
            #{value.toUpperCase()}
          </p>
        </div>
      )}
    </div>
  );
}
