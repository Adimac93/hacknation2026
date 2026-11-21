import { describe, expect, it } from "vitest";
import type { FieldOrigin } from "../api/types";
import { locateField } from "../form/model";
import type { FormConfig } from "../form/types";
import { fieldsForLine, lowConfidence, pickForLine } from "./origin";

const fields: FieldOrigin[] = [
  { techName: "a", src: ["L1"], confidence: 0.9 },
  { techName: "b", src: ["L2", "L3"], confidence: 0.6 },
  { techName: "c", src: ["L3"], confidence: 0.3 },
  { techName: "d", src: ["L4"], confidence: 0.7 },
];

describe("origin mapping", () => {
  it("lists fields below 0.7, lowest first", () => {
    expect(lowConfidence(fields).map((f) => f.techName)).toEqual(["c", "b"]);
    expect(lowConfidence([fields[0] as FieldOrigin])).toEqual([]);
  });

  it("maps a line to its fields and cycles on repeated clicks", () => {
    expect(fieldsForLine(fields, "L3").map((f) => f.techName)).toEqual(["b", "c"]);
    expect(pickForLine(fields, "L3", null)).toBe("b");
    expect(pickForLine(fields, "L3", "b")).toBe("c");
    expect(pickForLine(fields, "L3", "c")).toBe("b");
    expect(pickForLine(fields, "L9", null)).toBeNull();
  });

  it("locates a techName in the config", () => {
    const cell = (techName: string) => ({ x: 0, y: 0, rows: 1, cols: 1, field: { techName } });
    const config = {
      tabs: [
        { questions: [] },
        { questions: [{ field: { repeatingSectionGrid: [cell("x"), cell("y")] } }] },
      ],
    } as unknown as FormConfig;
    expect(locateField(config, "y")).toEqual({ t: 1, q: 0, g: 1 });
    expect(locateField(config, "zz")).toBeNull();
  });
});
