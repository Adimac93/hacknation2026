import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const css = readFileSync("src/styles/tokens.css", "utf8");
const token = (name: string): string => {
  const m = css.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, "i"));
  if (!m?.[1]) throw new Error(`missing token ${name}`);
  return m[1];
};

const lum = (hex: string): number => {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = Number.parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const ratio = (a: string, b: string): number => {
  const [x, y] = [lum(a), lum(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
};

// Foreground/background pairs actually used by the CSS modules (text needs 4.5, UI parts 3).
const TEXT: [string, string][] = [
  ["text", "bg"],
  ["text", "surface"],
  ["text", "accent-tint"],
  ["accent-text", "bg"],
  ["accent-text", "surface"],
  ["accent-text", "accent-tint"],
  ["text-muted", "bg"],
  ["text-muted", "surface"],
  ["text-muted", "white"],
  ["text-muted", "accent-tint"],
  ["success", "bg"],
  ["success", "surface"],
  ["warning", "bg"],
  ["warning", "surface"],
  ["white", "accent-text"],
  ["white", "accent-hover"],
  ["bg", "text"],
];
const UI: [string, string][] = [
  ["accent", "bg"],
  ["accent", "white"],
  ["border-input", "white"],
];

describe("contrast of token pairs", () => {
  it.each(TEXT)("text %s on %s >= 4.5", (fg, bg) => {
    expect(ratio(token(fg), token(bg))).toBeGreaterThanOrEqual(4.5);
  });
  it.each(UI)("ui %s on %s >= 3", (fg, bg) => {
    expect(ratio(token(fg), token(bg))).toBeGreaterThanOrEqual(3);
  });
});
