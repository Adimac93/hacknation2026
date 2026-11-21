// Addressing and value helpers shared by conditions, validation and the renderer.
//
// Keys are positional, so they stay unique even when a config repeats a techName:
//   section          "t.q"            (tab index, question index)
//   field            "t.q.g"          (g = index in repeatingSectionGrid)
//   field in a row   "t.q#r.g"        (r = stable row id of a REPEATING_SECTION)
// A field's *template key* is always "t.q.g"; conditions are compiled per template.

import { sampleDictionary, sampleRegisterValue } from "./sampleData";
import type { Answer, FieldOption, FileEntry, FormConfig, FormField, GridItem, Tab } from "./types";

export const sectionKey = (t: number, q: number) => `${t}.${q}`;
export const templateKey = (t: number, q: number, g: number) => `${t}.${q}.${g}`;
export const instanceKey = (t: number, q: number, g: number, rowId?: number) =>
  rowId === undefined ? templateKey(t, q, g) : `${t}.${q}#${rowId}.${g}`;

/** Field types that collect no data. */
export const PRESENTATIONAL_TYPES = new Set(["TEXT_BLOCK", "INFO_SECTION"]);

export function isRepeating(item: GridItem<{ type: string }>): boolean {
  return item.field.type === "REPEATING_SECTION";
}

/** Grid items sorted into visual (and therefore DOM and tab) order. */
export function byPosition<T extends { x: number; y: number }>(items: T[]): T[] {
  return [...items].sort((a, b) => a.y - b.y || a.x - b.x);
}

/**
 * Page order from flow.links: start at the page no link points to and follow source ->
 * target. Pages the chain does not reach are appended in `tabs` order, so a broken flow
 * never hides a page.
 */
export function orderTabs(config: FormConfig): number[] {
  const indexById = new Map(config.tabs.map((tab, i) => [tab.id, i]));
  const next = new Map<string, string>();
  for (const link of config.flow.links) {
    if (!next.has(link.source)) next.set(link.source, link.target);
  }
  const targets = new Set(config.flow.links.map((l) => l.target));
  const start = config.tabs.find((tab) => next.has(tab.id) && !targets.has(tab.id));

  const order: number[] = [];
  const seen = new Set<string>();
  let current = start?.id;
  while (current !== undefined && !seen.has(current) && indexById.has(current)) {
    seen.add(current);
    order.push(indexById.get(current) as number);
    current = next.get(current);
  }
  config.tabs.forEach((tab, i) => {
    if (!seen.has(tab.id)) order.push(i);
  });
  // The FINISH page closes the form even when the flow says otherwise.
  const finish = order.filter((i) => isFinish(config.tabs[i]));
  return [...order.filter((i) => !isFinish(config.tabs[i])), ...finish];
}

export function isFinish(tab: Tab | undefined): boolean {
  return tab?.type === "FINISH";
}

export function isExternal(field: FormField): boolean {
  return field.defaultValueType === "EXTERNAL_SYSTEM" && typeof field.defaultValue === "string";
}

/** Value a field starts with: register sample, configured default or empty. */
export function initialValue(field: FormField, registers = true): Answer {
  const dv = field.defaultValue;
  if (isExternal(field)) return registers ? sampleRegisterValue(dv as string) : "";
  switch (field.type) {
    case "CHECKBOX":
      return Array.isArray(dv) ? dv.filter((v) => typeof v === "string") : [];
    case "FILE_UPLOADER":
      return [];
    case "CONSENT_SECTION":
      return (field.consentSectionConfig?.consents ?? []).map(() => false);
    case "SELECT":
    case "RADIO":
      return Array.isArray(dv) ? (dv.find((v) => typeof v === "string") ?? "") : (dv ?? "");
    default:
      return typeof dv === "string" ? dv : "";
  }
}

/** Options from the config, or from the sample dictionary when the field names one. */
export function optionsOf(field: FormField): FieldOption[] {
  if (field.options && field.options.length > 0) return field.options;
  const dictionary = sampleDictionary(field.dictionaryName);
  return dictionary ? dictionary.entries.map((entry) => ({ id: entry, name: entry })) : [];
}

/** Visible label: dictionary-backed fields titled with the raw dictionary name get a real one. */
export function labelOf(field: FormField): string {
  if (field.dictionaryName && field.title === field.dictionaryName) {
    return sampleDictionary(field.dictionaryName)?.label ?? field.title;
  }
  return field.title;
}

export function isEmptyAnswer(value: Answer | undefined): boolean {
  if (value === undefined) return true;
  if (typeof value === "string") return value.trim() === "";
  return !value.some((v) => v !== false);
}

/** Parses a number typed the Polish way ("1 250,50") or the JS way ("1250.50"). */
export function parseNumber(value: string): number | undefined {
  const normalized = value.replace(/[\s ]/g, "").replace(",", ".");
  if (!/^-?\d+(\.\d+)?$/.test(normalized)) return undefined;
  return Number(normalized);
}

/** The value exposed to JSONata as `__userAnswer`. */
export function toUserAnswer(field: FormField, value: Answer | undefined): unknown {
  if (value === undefined || isEmptyAnswer(value)) return undefined;
  switch (field.type) {
    case "NUMBER":
      return typeof value === "string" ? (parseNumber(value) ?? value) : value;
    case "FILE_UPLOADER":
      return (value as FileEntry[]).map((f) => f.name);
    default:
      return value;
  }
}

/** Human-readable value for the summary page. */
export function displayValue(field: FormField, value: Answer | undefined): string {
  if (value === undefined || isEmptyAnswer(value)) return "";
  const nameOf = (id: string) => optionsOf(field).find((o) => o.id === id)?.name ?? id;
  switch (field.type) {
    case "RADIO":
    case "SELECT":
      return nameOf(value as string);
    case "CHECKBOX":
      return (value as string[]).map(nameOf).join(", ");
    case "FILE_UPLOADER":
      return (value as FileEntry[]).map((f) => f.name).join(", ");
    case "CONSENT_SECTION": {
      const flags = value as boolean[];
      return `Zaakceptowano ${flags.filter(Boolean).length} z ${flags.length}`;
    }
    case "DATEPICKER": {
      const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value as string);
      return m ? `${m[3]}.${m[2]}.${m[1]}` : (value as string);
    }
    default:
      return value as string;
  }
}

export interface FieldInstance {
  key: string;
  template: string;
  sectionKey: string;
  field: FormField;
  item: GridItem<FormField>;
  /** Row id inside a REPEATING_SECTION, undefined in a plain section. */
  rowId?: number;
  rowIndex?: number;
}

/** Row ids of a section; a plain section has one implicit row. */
export function rowsOf(repeats: Record<string, number[]>, key: string): number[] {
  return repeats[key] ?? [0];
}

/** Position of the first field with this techName, as indices into config.tabs. */
export function locateField(
  config: FormConfig,
  techName: string,
): { t: number; q: number; g: number } | null {
  for (const [t, tab] of config.tabs.entries()) {
    for (const [q, section] of tab.questions.entries()) {
      const g = (section.field.repeatingSectionGrid ?? []).findIndex(
        (c) => c.field.techName === techName,
      );
      if (g >= 0) return { t, q, g };
    }
  }
  return null;
}

/** Every field instance on one tab, in visual order. */
export function fieldInstances(
  config: FormConfig,
  t: number,
  repeats: Record<string, number[]>,
): FieldInstance[] {
  const tab = config.tabs[t];
  if (!tab) return [];
  const out: FieldInstance[] = [];
  for (const section of byPosition(tab.questions.map((item, q) => ({ ...item, q })))) {
    const { q } = section;
    const sKey = sectionKey(t, q);
    const grid = (section.field.repeatingSectionGrid ?? []).map((item, g) => ({ ...item, g }));
    const rows = isRepeating(section) ? rowsOf(repeats, sKey) : [undefined];
    rows.forEach((rowId, rowIndex) => {
      for (const cell of byPosition(grid)) {
        out.push({
          key: instanceKey(t, q, cell.g, rowId),
          template: templateKey(t, q, cell.g),
          sectionKey: sKey,
          field: cell.field,
          item: cell,
          rowId,
          rowIndex: rowId === undefined ? undefined : rowIndex,
        });
      }
    });
  }
  return out;
}
