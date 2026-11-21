// Dynamic states (SHOW, READ_ONLY) evaluated with JSONata, the way the COI generator does:
// every query runs against a copy of the configuration in which each field carries its
// current answer as `__userAnswer`. Expressions are compiled once per configuration.

import jsonata from "jsonata";
import {
  initialValue,
  instanceKey,
  isRepeating,
  rowsOf,
  sectionKey,
  templateKey,
  toUserAnswer,
} from "./model";
import type { Answer, FormConfig, FormField } from "./types";

type Expression = ReturnType<typeof jsonata>;

export interface CompiledStates {
  show: Expression[];
  readOnly: Expression[];
  /** Queries that failed to compile; such a state is ignored (the element stays visible). */
  errors: string[];
}

/** Compiled states keyed by section key ("t.q") or field template key ("t.q.g"). */
export type CompiledConditions = Map<string, CompiledStates>;

function compileStates(states: FormField["states"]): CompiledStates | undefined {
  if (!states || states.length === 0) return undefined;
  const compiled: CompiledStates = { show: [], readOnly: [], errors: [] };
  for (const state of states) {
    const target =
      state.type === "SHOW" ? compiled.show : state.type === "READ_ONLY" ? compiled.readOnly : null;
    if (!target) continue;
    try {
      target.push(jsonata(state.query));
    } catch (error) {
      compiled.errors.push(error instanceof Error ? error.message : String(error));
    }
  }
  return compiled;
}

export function compileConditions(config: FormConfig): CompiledConditions {
  const out: CompiledConditions = new Map();
  config.tabs.forEach((tab, t) => {
    tab.questions.forEach((section, q) => {
      const own = compileStates(section.field.states);
      if (own) out.set(sectionKey(t, q), own);
      (section.field.repeatingSectionGrid ?? []).forEach((cell, g) => {
        const states = compileStates(cell.field.states);
        if (states) out.set(templateKey(t, q, g), states);
      });
    });
  });
  return out;
}

export interface Conditions {
  /** Instance or section keys hidden by SHOW. */
  hidden: Set<string>;
  /** Instance keys made read-only by READ_ONLY. */
  readOnly: Set<string>;
}

/**
 * Before the first asynchronous evaluation finishes, anything with a SHOW state is
 * treated as hidden, so conditional sections do not flash on screen.
 */
export function pendingHidden(compiled: CompiledConditions, template: string): boolean {
  return (compiled.get(template)?.show.length ?? 0) > 0;
}

export type AnswerLookup = (field: FormField, key: string) => Answer;

export function answerLookup(answers: Record<string, Answer>): AnswerLookup {
  return (field, key) => answers[key] ?? initialValue(field);
}

/** Copy of the configuration with `__userAnswer` on every section and field. */
export function buildEvaluationDocument(
  config: FormConfig,
  answerOf: AnswerLookup,
  repeats: Record<string, number[]>,
  hidden: Set<string>,
): unknown {
  return {
    ...config,
    tabs: config.tabs.map((tab, t) => ({
      ...tab,
      questions: tab.questions.map((section, q) => {
        const sKey = sectionKey(t, q);
        const sectionHidden = hidden.has(sKey);
        const grid = section.field.repeatingSectionGrid ?? [];
        // Hidden elements contribute no answer, like an empty field.
        const valueAt = (field: FormField, g: number, rowId?: number) => {
          const key = instanceKey(t, q, g, rowId);
          return sectionHidden || hidden.has(key)
            ? undefined
            : toUserAnswer(field, answerOf(field, key));
        };

        if (!isRepeating(section)) {
          return {
            ...section,
            field: {
              ...section.field,
              repeatingSectionGrid: grid.map((cell, g) => ({
                ...cell,
                field: { ...cell.field, __userAnswer: valueAt(cell.field, g) },
              })),
            },
          };
        }

        // Repeating section, as in the COI rules:
        // field.__userAnswer[$repeatingSectionIndex]['pole' in fieldTechName].answers
        const rows = rowsOf(repeats, sKey);
        return {
          ...section,
          field: {
            ...section.field,
            __userAnswer: rows.map((rowId) =>
              grid.map((cell, g) => ({
                fieldTechName: cell.field.techName,
                answers: valueAt(cell.field, g, rowId),
              })),
            ),
            repeatingSectionGrid: grid.map((cell, g) => ({
              ...cell,
              field: {
                ...cell.field,
                __userAnswer: rows.map((rowId) => valueAt(cell.field, g, rowId)),
              },
            })),
          },
        };
      }),
    })),
  };
}

async function holds(
  expressions: Expression[],
  doc: unknown,
  bindings: Record<string, unknown> | undefined,
  mode: "all" | "any",
): Promise<boolean> {
  const results = await Promise.all(
    expressions.map(async (expression) => {
      try {
        return Boolean(await expression.evaluate(doc, bindings));
      } catch {
        // A query that fails at runtime must not hide the element.
        return mode === "all";
      }
    }),
  );
  return mode === "all" ? results.every(Boolean) : results.some(Boolean);
}

const MAX_PASSES = 5;

/**
 * Evaluates SHOW and READ_ONLY for every section and field instance. Hiding an element
 * removes its answer from the document, which can change other conditions, so this
 * iterates until visibility settles.
 */
export async function evaluateConditions(
  config: FormConfig,
  compiled: CompiledConditions,
  answerOf: AnswerLookup,
  repeats: Record<string, number[]>,
): Promise<Conditions> {
  let hidden = new Set<string>();
  let readOnly = new Set<string>();

  for (let pass = 0; pass < MAX_PASSES; pass++) {
    const doc = buildEvaluationDocument(config, answerOf, repeats, hidden);
    const nextHidden = new Set<string>();
    const nextReadOnly = new Set<string>();
    const jobs: Promise<void>[] = [];

    config.tabs.forEach((tab, t) => {
      tab.questions.forEach((section, q) => {
        const sKey = sectionKey(t, q);
        const own = compiled.get(sKey);
        if (own && own.show.length > 0) {
          jobs.push(
            holds(own.show, doc, undefined, "all").then((shown) => {
              if (!shown) nextHidden.add(sKey);
            }),
          );
        }
        const rows = isRepeating(section) ? rowsOf(repeats, sKey) : [undefined];
        (section.field.repeatingSectionGrid ?? []).forEach((_, g) => {
          const states = compiled.get(templateKey(t, q, g));
          if (!states) return;
          rows.forEach((rowId, rowIndex) => {
            const key = instanceKey(t, q, g, rowId);
            const bindings = rowId === undefined ? undefined : { repeatingSectionIndex: rowIndex };
            if (states.show.length > 0) {
              jobs.push(
                holds(states.show, doc, bindings, "all").then((shown) => {
                  if (!shown) nextHidden.add(key);
                }),
              );
            }
            if (states.readOnly.length > 0) {
              jobs.push(
                holds(states.readOnly, doc, bindings, "any").then((locked) => {
                  if (locked) nextReadOnly.add(key);
                }),
              );
            }
          });
        });
      });
    });

    await Promise.all(jobs);
    const settled =
      nextHidden.size === hidden.size && [...nextHidden].every((key) => hidden.has(key));
    hidden = nextHidden;
    readOnly = nextReadOnly;
    if (settled) break;
  }
  return { hidden, readOnly };
}
