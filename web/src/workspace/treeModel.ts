/** Pure model of the JSON tree view: ids, summaries, flattening and search. No DOM here. */

export type NodeKind = "object" | "array" | "string" | "number" | "boolean" | "null";

export interface TreeRow {
  /** JSON-pointer-like path; "" is the document root. */
  id: string;
  parentId: string | null;
  /** Object key or array index; null for the root. */
  label: string | null;
  level: number;
  posInSet: number;
  setSize: number;
  kind: NodeKind;
  /** Containers and long strings can be toggled. */
  expandable: boolean;
  expanded: boolean;
  /** Collapsed one-liner for containers, e.g. `[5]` or `{ 8 kluczy }`. */
  summary: string;
  /** Primitive value as displayed (strings truncated unless expanded). */
  text: string;
  /** Raw string for primitives, used by search highlighting. */
  raw: string;
}

export const MAX_STRING = 80;

/** Keys whose values are worth spotting at a glance, with the text tag shown next to them. */
export const IMPORTANT_KEYS: Record<string, string> = {
  techName: "nazwa techniczna",
  type: "typ",
};

export const kindOf = (v: unknown): NodeKind =>
  v === null ? "null" : Array.isArray(v) ? "array" : (typeof v as NodeKind);

const isContainer = (v: unknown): v is Record<string, unknown> | unknown[] =>
  typeof v === "object" && v !== null;

const entries = (v: Record<string, unknown> | unknown[]): [string, unknown][] =>
  Array.isArray(v) ? v.map((x, i) => [String(i), x]) : Object.entries(v);

export const childId = (parentId: string, key: string): string =>
  `${parentId}/${key.replaceAll("~", "~0").replaceAll("/", "~1")}`;

function keysWord(n: number): string {
  if (n === 1) return "klucz";
  const last = n % 10;
  return last >= 2 && last <= 4 && (n % 100 < 10 || n % 100 >= 20) ? "klucze" : "kluczy";
}

export function summarize(v: unknown): string {
  if (Array.isArray(v)) return `[${v.length}]`;
  if (isContainer(v)) {
    const n = Object.keys(v).length;
    return `{ ${n} ${keysWord(n)} }`;
  }
  return JSON.stringify(v) ?? String(v);
}

const isLongString = (v: unknown): v is string => typeof v === "string" && v.length > MAX_STRING;

/** Containers at depth < `depth` (root is depth 0). */
export function defaultExpanded(root: unknown, depth = 2): Set<string> {
  const out = new Set<string>();
  const walk = (v: unknown, id: string, d: number) => {
    if (!isContainer(v) || d >= depth) return;
    out.add(id);
    for (const [k, c] of entries(v)) walk(c, childId(id, k), d + 1);
  };
  walk(root, "", 0);
  return out;
}

export function allContainerIds(root: unknown): Set<string> {
  return defaultExpanded(root, Number.POSITIVE_INFINITY);
}

/** Visible rows only: children of collapsed nodes are never built (lazy rendering). */
export function flatten(root: unknown, expanded: ReadonlySet<string>): TreeRow[] {
  const rows: TreeRow[] = [];
  const walk = (
    v: unknown,
    id: string,
    parentId: string | null,
    label: string | null,
    level: number,
    posInSet: number,
    setSize: number,
  ) => {
    const kind = kindOf(v);
    const container = isContainer(v);
    const long = isLongString(v);
    const open = expanded.has(id);
    const raw = container ? "" : typeof v === "string" ? v : JSON.stringify(v);
    rows.push({
      id,
      parentId,
      label,
      level,
      posInSet,
      setSize,
      kind,
      expandable: container || long,
      expanded: open,
      summary: container ? summarize(v) : "",
      text: long && !open ? `${raw.slice(0, MAX_STRING)}…` : raw,
      raw,
    });
    if (container && open) {
      const kids = entries(v);
      kids.forEach(([k, c], i) => {
        walk(c, childId(id, k), id, k, level + 1, i + 1, kids.length);
      });
    }
  };
  walk(root, "", null, null, 1, 1, 1);
  return rows;
}

export const matchesText = (text: string, query: string): boolean =>
  query !== "" && text.toLowerCase().includes(query.toLowerCase());

/**
 * Ids matching `query` on key or primitive value, plus `reveal`: ancestors of matches
 * and long strings that match (so the full text is shown). Linear in document size.
 */
export function search(
  root: unknown,
  query: string,
): { matches: Set<string>; reveal: Set<string> } {
  const matches = new Set<string>();
  const reveal = new Set<string>();
  if (query === "") return { matches, reveal };
  const walk = (v: unknown, id: string, key: string | null, ancestors: string[]) => {
    const container = isContainer(v);
    const valueHit = !container && matchesText(typeof v === "string" ? v : String(v), query);
    if ((key !== null && matchesText(key, query)) || valueHit) {
      matches.add(id);
      for (const a of ancestors) reveal.add(a);
      if (valueHit && isLongString(v)) reveal.add(id);
    }
    if (container) {
      for (const [k, c] of entries(v)) walk(c, childId(id, k), k, [...ancestors, id]);
    }
  };
  walk(root, "", null, []);
  return { matches, reveal };
}

/** Splits `text` into alternating plain and matching segments for highlighting. */
export function highlightParts(text: string, query: string): { text: string; hit: boolean }[] {
  if (query === "") return [{ text, hit: false }];
  const parts: { text: string; hit: boolean }[] = [];
  const lower = text.toLowerCase();
  const q = query.toLowerCase();
  let from = 0;
  for (let i = lower.indexOf(q); i !== -1; i = lower.indexOf(q, from)) {
    if (i > from) parts.push({ text: text.slice(from, i), hit: false });
    parts.push({ text: text.slice(i, i + q.length), hit: true });
    from = i + q.length;
  }
  if (from < text.length) parts.push({ text: text.slice(from), hit: false });
  return parts.length ? parts : [{ text, hit: false }];
}
