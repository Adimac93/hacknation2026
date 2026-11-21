// Renderer state, driven by useReducer. Answers are stored only once the user changes a
// field; until then the field shows initialValue(). Removing a repeating row drops its id,
// which orphans that row's answers without renumbering the others.

import type { Answer } from "./types";

export interface FormState {
  answers: Record<string, Answer>;
  /** Row ids per REPEATING_SECTION key; absent means one row with id 0. */
  repeats: Record<string, number[]>;
  nextRowId: number;
  /** Position in the ordered page list (not an index into `tabs`). */
  step: number;
  errors: Record<string, string>;
  /** Bumped on each failed "Dalej" so the error summary can take focus again. */
  errorAttempt: number;
  notice: string | null;
}

export type FormAction =
  | { type: "answer"; key: string; value: Answer }
  | { type: "addRow"; section: string }
  | { type: "removeRow"; section: string; rowId: number }
  | { type: "goTo"; step: number }
  | { type: "fail"; errors: Record<string, string> }
  | { type: "notice"; message: string | null }
  | { type: "reset"; notice?: string };

export const initialFormState: FormState = {
  answers: {},
  repeats: {},
  nextRowId: 1,
  step: 0,
  errors: {},
  errorAttempt: 0,
  notice: null,
};

export function formReducer(state: FormState, action: FormAction): FormState {
  switch (action.type) {
    case "answer": {
      const { [action.key]: _cleared, ...errors } = state.errors;
      return { ...state, answers: { ...state.answers, [action.key]: action.value }, errors };
    }
    case "addRow": {
      const rows = state.repeats[action.section] ?? [0];
      return {
        ...state,
        repeats: { ...state.repeats, [action.section]: [...rows, state.nextRowId] },
        nextRowId: state.nextRowId + 1,
      };
    }
    case "removeRow": {
      const rows = state.repeats[action.section] ?? [0];
      if (rows.length <= 1) return state;
      return {
        ...state,
        repeats: { ...state.repeats, [action.section]: rows.filter((id) => id !== action.rowId) },
      };
    }
    case "goTo":
      return { ...state, step: action.step, errors: {}, notice: null };
    case "fail":
      return { ...state, errors: action.errors, errorAttempt: state.errorAttempt + 1 };
    case "notice":
      return { ...state, notice: action.message };
    case "reset":
      return { ...initialFormState, notice: action.notice ?? null };
  }
}
