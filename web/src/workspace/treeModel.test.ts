import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import {
  allContainerIds,
  childId,
  defaultExpanded,
  flatten,
  highlightParts,
  MAX_STRING,
  search,
  summarize,
} from "./treeModel";

const doc = { tabs: [{ techName: "a/b", type: "MAIN" }, { techName: "c" }], n: 1, ok: true };

describe("jsonTree", () => {
  it("builds escaped paths", () => {
    expect(childId("", "a/b")).toBe("/a~1b");
    expect(childId("/tabs", "0")).toBe("/tabs/0");
  });

  it("summarizes containers", () => {
    expect(summarize([1, 2, 3, 4, 5])).toBe("[5]");
    expect(summarize({ a: 1 })).toBe("{ 1 klucz }");
    expect(summarize({ a: 1, b: 2 })).toBe("{ 2 klucze }");
    expect(summarize(Object.fromEntries(Array.from({ length: 8 }, (_, i) => [i, i])))).toBe(
      "{ 8 kluczy }",
    );
  });

  it("expands two levels by default and hides deeper rows", () => {
    const exp = defaultExpanded(doc);
    expect([...exp].sort()).toEqual(["", "/tabs"]);
    const rows = flatten(doc, exp);
    expect(rows.map((r) => r.id)).toEqual(["", "/tabs", "/tabs/0", "/tabs/1", "/n", "/ok"]);
    expect(rows[2]).toMatchObject({ level: 3, posInSet: 1, setSize: 2, expanded: false });
    expect(rows[2]?.summary).toBe("{ 2 klucze }");
  });

  it("truncates long strings until expanded", () => {
    const long = { s: "x".repeat(MAX_STRING + 10) };
    const closed = flatten(long, new Set([""]));
    expect(closed[1]).toMatchObject({ expandable: true, expanded: false });
    expect(closed[1]?.text.length).toBe(MAX_STRING + 1);
    expect(flatten(long, new Set(["", "/s"]))[1]?.text).toBe(long.s);
  });

  it("searches keys and values, revealing ancestors", () => {
    const { matches, reveal } = search(doc, "TECHNAME");
    expect([...matches].sort()).toEqual(["/tabs/0/techName", "/tabs/1/techName"]);
    expect(reveal.has("/tabs/0")).toBe(true);
    expect(reveal.has("")).toBe(true);
    expect(search(doc, "main").matches.has("/tabs/0/type")).toBe(true);
    expect(search(doc, "").matches.size).toBe(0);
  });

  it("highlights case-insensitively", () => {
    expect(highlightParts("Imię i imiona", "imi")).toEqual([
      { text: "Imi", hit: true },
      { text: "ę i ", hit: false },
      { text: "imi", hit: true },
      { text: "ona", hit: false },
    ]);
  });

  it("handles the largest generated form quickly", () => {
    const form: unknown = JSON.parse(
      readFileSync(
        // vitest runs from web/
        resolve("../outputs/9-wniosek-o-przyznanie-stypendium-sportowego-rady-miasta-zgierza.json"),
        "utf8",
      ),
    );
    const t = performance.now();
    const all = flatten(form, allContainerIds(form));
    search(form, "techName");
    expect(all.length).toBeGreaterThan(100);
    expect(performance.now() - t).toBeLessThan(500);
    expect(flatten(form, defaultExpanded(form)).length).toBeLessThan(all.length);
  });
});
