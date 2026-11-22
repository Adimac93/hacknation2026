import { describe, expect, it } from "vitest";
import { validateUpload } from "./validate";

const ok = { name: "wniosek.pdf", size: 1000 };

describe("validateUpload", () => {
  it.each([
    ["accepts a plain pdf", ok, false],
    ["accepts uppercase extension", { ...ok, name: "WNIOSEK.DOC" }, false],
    ["accepts the organiser's .JPE sample", { ...ok, name: "wniosek.JPE" }, false],
    ["rejects unsupported extension", { ...ok, name: "a.exe" }, true],
    ["rejects missing extension", { ...ok, name: "wniosek" }, true],
    ["rejects forbidden character", { ...ok, name: "a;b.pdf" }, true],
    ["rejects name over 250 chars", { ...ok, name: `${"a".repeat(247)}.pdf` }, true],
    ["rejects empty file", { ...ok, size: 0 }, true],
    ["rejects oversize file", { ...ok, size: 21 * 1024 * 1024 }, true],
  ])("%s", (_label, file, rejected) => {
    expect(validateUpload(file) !== null).toBe(rejected);
  });
});
