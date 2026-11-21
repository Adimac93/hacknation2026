import { parseConfig } from "../form/parse";
import type { AnalysisResult, DocLine, FieldOrigin, LintItem, Report } from "./types";

/** Builds sample data from a reference configuration, so the views work without the backend. */
export async function demoResult(): Promise<AnalysisResult> {
  const text = await (await fetch("/examples/przyklad-5.json")).text();
  const config = parseConfig(text);
  const pages: Report["document"]["pages"] = [];
  const fields: FieldOrigin[] = [];
  let n = 0;
  config.tabs.forEach((tab, i) => {
    const lines: DocLine[] = [{ id: `L${++n}`, text: tab.title, kind: "HEADING" }];
    for (const section of tab.questions) {
      lines.push({ id: `L${++n}`, text: section.field.title, kind: "HEADING" });
      for (const cell of section.field.repeatingSectionGrid) {
        const id = `L${++n}`;
        lines.push({ id, text: cell.field.title || cell.field.techName, kind: "TEXT" });
        fields.push({ techName: cell.field.techName, src: [id], confidence: 0.9 });
      }
    }
    pages.push({ number: i + 1, lines });
  });
  const lint: LintItem[] = [
    {
      code: "L005",
      severity: "error",
      message: "Pole leżało poza sekcją",
      path: "tabs[1].questions[0]",
      fixed: true,
    },
    {
      code: "L012",
      severity: "warning",
      message: "Tytuł pola ma ponad 120 znaków. Rozważ skrócenie.",
      path: "tabs[0].questions[1]",
    },
  ];
  return {
    demo: true,
    form: JSON.parse(text),
    report: {
      mode: "rules",
      timings_ms: { ingest: 120, heuristics: 4, compile: 3, lint: 2 },
      lint,
      fields,
      document: { pages },
      dictionary_proposals: [
        { name: "Rodzaj nieruchomości", items: ["Budynek", "Lokal", "Działka"], fields: [] },
      ],
    },
  };
}
