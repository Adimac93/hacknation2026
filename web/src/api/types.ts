// Response contract of POST /api/v1/forms?details=true (ARCHITECTURE.md, 8.1).

export interface LintItem {
  code: string;
  severity: "error" | "warning";
  message: string;
  path: string;
  fixed?: boolean;
}

export type LineKind = "TEXT" | "HEADING" | "CHECKBOX" | "TABLE_ROW";

export interface DocLine {
  id: string;
  text: string;
  kind: LineKind;
}

export interface FieldOrigin {
  techName: string;
  /** Ids of source lines the field came from. */
  src: string[];
  confidence: number;
}

export interface DictionaryProposal {
  name: string;
  items: string[];
  fields: string[];
}

export interface Report {
  mode: "llm" | "rules";
  model?: string;
  timings_ms: Record<string, number>;
  lint: LintItem[];
  fields: FieldOrigin[];
  document: { pages: { number: number; lines: DocLine[] }[] };
  dictionary_proposals: DictionaryProposal[];
}

export interface AnalysisResult {
  form: unknown;
  report: Report;
  /** True for locally built sample data (no backend call). */
  demo?: boolean;
}
