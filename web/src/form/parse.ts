// Turns untrusted JSON into a FormConfig the renderer can walk without crashing.
// Only structural problems are fatal; content problems (unknown field types, broken
// conditions) are left for the renderer to show in place.

import type { FormConfig, FormField, GridItem, SectionField, Tab } from "./types";

export class ConfigError extends Error {}

type Json = Record<string, unknown>;

function isObject(value: unknown): value is Json {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asArray(value: unknown, where: string): unknown[] {
  if (value === undefined || value === null) return [];
  if (!Array.isArray(value)) throw new ConfigError(`${where} musi być listą.`);
  return value;
}

/** Lenient variant for field-level lists: reference 1 has `"validation": {}`. */
function asList(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asNumber(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function normalizeField(raw: unknown, where: string): FormField {
  if (!isObject(raw)) throw new ConfigError(`${where}: brak obiektu „field”.`);
  return {
    ...raw,
    id: asString(raw.id),
    type: asString(raw.type),
    techName: asString(raw.techName),
    title: asString(raw.title),
    description: asString(raw.description),
    options: asList(raw.options)
      .filter(isObject)
      .map((o) => ({
        ...o,
        id: asString(o.id ?? o.name),
        name: asString(o.name ?? o.id),
      })),
    validation: asList(raw.validation) as FormField["validation"],
    states: asList(raw.states)
      .filter(isObject)
      .map((s) => ({ type: asString(s.type), query: asString(s.query) })),
    repeatingSectionGrid: asArray(raw.repeatingSectionGrid, `${where}.repeatingSectionGrid`).map(
      (item, i) => normalizeItem(item, `${where}.repeatingSectionGrid[${i}]`),
    ),
  } as FormField;
}

function normalizeItem(raw: unknown, where: string): GridItem<FormField> {
  if (!isObject(raw)) throw new ConfigError(`${where} nie jest obiektem.`);
  return {
    x: asNumber(raw.x, 0),
    y: asNumber(raw.y, 0),
    rows: Math.max(1, asNumber(raw.rows, 1)),
    cols: Math.max(1, asNumber(raw.cols, 3)),
    field: normalizeField(raw.field, where),
  };
}

function normalizeTab(raw: unknown, index: number): Tab {
  const where = `tabs[${index}]`;
  if (!isObject(raw)) throw new ConfigError(`${where} nie jest obiektem.`);
  return {
    id: asString(raw.id) || `tab-${index}`,
    title: asString(raw.title),
    type: asString(raw.type),
    questions: asArray(raw.questions, `${where}.questions`).map(
      (q, i) => normalizeItem(q, `${where}.questions[${i}]`) as GridItem<SectionField>,
    ),
  };
}

/** Validates the shape of a parsed JSON value; throws ConfigError with a Polish message. */
export function normalizeConfig(raw: unknown): FormConfig {
  if (!isObject(raw)) throw new ConfigError("Plik nie zawiera obiektu konfiguracji formularza.");
  if (!Array.isArray(raw.tabs)) {
    throw new ConfigError("Brak listy stron „tabs”. To nie jest konfiguracja formularza COI.");
  }
  const tabs = raw.tabs.map(normalizeTab);
  if (tabs.length === 0) throw new ConfigError("Formularz nie ma żadnej strony.");
  const flow = isObject(raw.flow) ? raw.flow : {};
  return {
    title: asString(raw.title),
    tabs,
    flow: {
      links: asArray(flow.links, "flow.links")
        .filter(isObject)
        .map((l) => ({
          id: asString(l.id),
          source: asString(l.source),
          target: asString(l.target),
        })),
    },
  };
}

/** Parses JSON text into a FormConfig; throws ConfigError on invalid JSON or shape. */
export function parseConfig(text: string): FormConfig {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch (error) {
    const detail = error instanceof Error ? ` (${error.message})` : "";
    throw new ConfigError(`Plik nie jest poprawnym JSON-em${detail}.`);
  }
  return normalizeConfig(raw);
}
