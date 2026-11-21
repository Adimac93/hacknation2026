import { describe, expect, it } from "vitest";
import vectors from "../../../fixtures/validators.json";
import { TEXT_VALIDATORS } from "./validators";

describe.each(Object.entries(vectors))("%s", (name, { valid, invalid }) => {
  const validate = TEXT_VALIDATORS[name as keyof typeof TEXT_VALIDATORS];

  it("has a validator", () => {
    expect(validate).toBeTypeOf("function");
  });

  it.each(valid)("accepts %s", (value) => {
    expect(validate?.(value)).toBe(true);
  });

  it.each(invalid)("rejects %s", (value) => {
    expect(validate?.(value)).toBe(false);
  });

  it("treats empty input as valid (REQUIRED handles emptiness)", () => {
    expect(validate?.("")).toBe(true);
  });
});
