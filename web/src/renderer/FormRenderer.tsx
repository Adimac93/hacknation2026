import { ArrowRight } from "lucide-react";
import { useEffect, useMemo, useReducer, useRef, useState } from "react";
import {
  type Conditions,
  compileConditions,
  evaluateConditions,
  pendingHidden,
} from "../form/conditions";
import {
  byPosition,
  fieldInstances,
  initialValue,
  isEmptyAnswer,
  isExternal,
  isFinish,
  labelOf,
  locateField,
  orderTabs,
  rowsOf,
  templateKey,
} from "../form/model";
import { formReducer, initialFormState } from "../form/state";
import type { Answer, FormConfig, FormField } from "../form/types";
import { validateField } from "../form/validation";
import buttons from "./buttons.module.css";
import { type RendererApi, RendererContext } from "./context";
import { type ErrorItem, ErrorSummary } from "./ErrorSummary";
import styles from "./FormRenderer.module.css";
import { Section } from "./Section";
import { Summary } from "./Summary";

export interface FocusRequest {
  techName: string;
  /** Badge text shown on the marked field, e.g. "Źródło: L7, L8". */
  badge: string;
  /** Changes on every request, so the same field can be focused again. */
  seq: number;
}

interface Props {
  config: FormConfig;
  /** Marks a field and, when `seq` changes, moves to its step and focuses it. */
  focusField?: FocusRequest | null;
  /** Shifts all heading levels (aria-level) when the form sits under other headings. */
  headingOffset?: number;
}

const domId = (key: string) => `pole-${key.replace(/\W/g, "_")}`;

/**
 * Renders a COI form configuration as a step-by-step e-form. Independent of the API: it
 * takes a parsed config and keeps all answers in memory.
 */
export function FormRenderer({ config, focusField, headingOffset = 0 }: Props) {
  const order = useMemo(() => orderTabs(config), [config]);
  const compiled = useMemo(() => compileConditions(config), [config]);
  const [state, dispatch] = useReducer(formReducer, initialFormState);
  // Register data is made up; it stays off until the user asks for it, so the form starts as
  // empty as the paper blank.
  const [registers, setRegisters] = useState(false);
  const [conditions, setConditions] = useState<Conditions | null>(null);
  const evaluation = useRef(0);
  const pageTitle = useRef<HTMLHeadingElement>(null);
  const firstRender = useRef(true);

  const answerOf = (field: FormField, key: string): Answer =>
    state.answers[key] ?? initialValue(field, registers);

  // Conditions are asynchronous in jsonata; a newer evaluation supersedes older ones.
  // biome-ignore lint/correctness/useExhaustiveDependencies: answerOf reads state.answers.
  useEffect(() => {
    const run = ++evaluation.current;
    evaluateConditions(config, compiled, answerOf, state.repeats).then((result) => {
      if (run === evaluation.current) setConditions(result);
    });
  }, [config, compiled, state.answers, state.repeats, registers]);

  // Move focus to the new page title on every step change, but not on first render. The page
  // does not jump to the top: the reviewer keeps their place in the workstation.
  // biome-ignore lint/correctness/useExhaustiveDependencies: runs on step change only.
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    pageTitle.current?.focus({ preventScroll: true });
  }, [state.step]);

  // Review request: switch to the field's step first, focus it once it is rendered.
  const target = useMemo(
    () => (focusField ? locateField(config, focusField.techName) : null),
    [config, focusField],
  );
  const handled = useRef(0);
  const targetStep = target ? order.indexOf(target.t) : -1;
  // biome-ignore lint/correctness/useExhaustiveDependencies: runs per request and step change.
  useEffect(() => {
    if (!focusField || !target || targetStep < 0 || handled.current === focusField.seq) return;
    if (targetStep !== Math.min(state.step, order.length - 1)) {
      dispatch({ type: "goTo", step: targetStep });
      return;
    }
    const id = domId(templateKey(target.t, target.q, target.g));
    const cell = document.querySelector<HTMLElement>(`[data-cell="${id}"]`);
    if (!cell) return; // hidden by a condition, or conditions still pending
    handled.current = focusField.seq;
    const el =
      document.getElementById(id) ??
      cell.querySelector<HTMLElement>("input,select,textarea,button");
    (el ?? cell).scrollIntoView?.({ block: "center" });
    el?.focus({ preventScroll: true });
  }, [focusField?.seq, state.step, conditions]);

  const isHidden = (key: string, template: string) =>
    conditions ? conditions.hidden.has(key) : pendingHidden(compiled, template);

  const isReadOnly = (field: FormField, key: string) =>
    isExternal(field) || field.readOnly === true || Boolean(conditions?.readOnly.has(key));

  const api: RendererApi = {
    answerOf,
    setAnswer: (key, value) => dispatch({ type: "answer", key, value }),
    isHidden,
    isReadOnly,
    errorOf: (key) => state.errors[key],
    domId,
    marked:
      focusField && target
        ? { template: templateKey(target.t, target.q, target.g), badge: focusField.badge }
        : undefined,
    rowsOf: (key) => rowsOf(state.repeats, key),
    addRow: (section) => dispatch({ type: "addRow", section }),
    removeRow: (section, rowId) => dispatch({ type: "removeRow", section, rowId }),
    headingOffset,
  };

  const step = Math.min(state.step, order.length - 1);
  const t = order[step] ?? 0;
  const tab = config.tabs[t];
  const finish = isFinish(tab);
  const isLast = step === order.length - 1;

  const visibleInstances = (tabIndex: number) =>
    fieldInstances(config, tabIndex, state.repeats).filter(
      (inst) => !isHidden(inst.sectionKey, inst.sectionKey) && !isHidden(inst.key, inst.template),
    );

  // This is a preview of a generated configuration: required fields and consents do not block
  // "Dalej", so the whole form can be browsed. A value that is filled in and wrong (e.g. a bad
  // PESEL) still stops the step, which shows the validators at work.
  const next = () => {
    const errors: Record<string, string> = {};
    for (const inst of visibleInstances(t)) {
      const answer = answerOf(inst.field, inst.key);
      if (inst.field.type === "CONSENT_SECTION" || isEmptyAnswer(answer)) continue;
      const message = validateField(inst.field, answer, isReadOnly(inst.field, inst.key));
      if (message) errors[inst.key] = message;
    }
    if (Object.keys(errors).length > 0) dispatch({ type: "fail", errors });
    else dispatch({ type: "goTo", step: step + 1 });
  };

  const errorItems: ErrorItem[] = fieldInstances(config, t, state.repeats)
    .filter((inst) => state.errors[inst.key])
    .map((inst) => ({
      id: domId(inst.key),
      label:
        inst.rowIndex === undefined
          ? labelOf(inst.field)
          : `${labelOf(inst.field)} (pozycja ${inst.rowIndex + 1})`,
      message: state.errors[inst.key] ?? "",
    }));

  const sections = byPosition((tab?.questions ?? []).map((item, q) => ({ ...item, q })));
  const summarised = order.slice(0, step).filter((i) => !isFinish(config.tabs[i]));

  return (
    <RendererContext.Provider value={api}>
      <div className={styles.form}>
        {config.title ? <p className={styles.formTitle}>{config.title}</p> : null}

        <div className={styles.registers}>
          <label className={styles.registersLabel}>
            <input
              type="checkbox"
              checked={registers}
              onChange={(e) => setRegisters(e.target.checked)}
            />
            Pokaż przykładowe dane z rejestrów
          </label>
          <p>
            Blankiet jest pusty. W prawdziwej e-usłudze część pól (np. imię, nazwisko, PESEL, adres,
            telefon) zostałaby uzupełniona danymi z rejestrów zalogowanego obywatela. Tutaj są to
            wymyślone dane przykładowe.
          </p>
        </div>

        <nav aria-label="Kroki formularza" className={styles.steps}>
          <p className={styles.stepCount}>
            Krok {step + 1} z {order.length}
          </p>
          <div
            className={styles.track}
            role="progressbar"
            aria-valuemin={1}
            aria-valuemax={order.length}
            aria-valuenow={step + 1}
            aria-valuetext={`Krok ${step + 1} z ${order.length}`}
            aria-label="Postęp wypełniania"
          >
            <div
              className={styles.bar}
              style={{ width: `${((step + 1) / order.length) * 100}%` }}
            />
          </div>
          <ol>
            {order.map((i, s) => (
              <li
                key={config.tabs[i]?.id ?? i}
                aria-current={s === step ? "step" : undefined}
                data-done={s < step}
              >
                {config.tabs[i]?.title || `Strona ${s + 1}`}
              </li>
            ))}
          </ol>
        </nav>

        <h1
          ref={pageTitle}
          tabIndex={-1}
          className={styles.pageTitle}
          aria-level={headingOffset > 0 ? 1 + headingOffset : undefined}
        >
          {tab?.title || `Strona ${step + 1}`}
        </h1>

        {state.notice ? (
          <p className={styles.notice} role="status">
            {state.notice}
          </p>
        ) : null}

        {errorItems.length > 0 ? (
          <ErrorSummary items={errorItems} attempt={state.errorAttempt} />
        ) : null}

        <form
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            if (!isLast) next();
            else dispatch({ type: "notice", message: SUBMIT_NOTICE });
          }}
        >
          <div className={styles.page}>
            {sections.map((item) => (
              <Section key={item.q} item={item} t={t} q={item.q} />
            ))}
          </div>

          {finish ? (
            <Summary
              config={config}
              tabs={summarised}
              repeats={state.repeats}
              onEdit={(tabIndex) => dispatch({ type: "goTo", step: order.indexOf(tabIndex) })}
            />
          ) : null}

          <div className={styles.actions}>
            {step > 0 ? (
              <button
                type="button"
                className={buttons.secondary}
                onClick={() => dispatch({ type: "goTo", step: step - 1 })}
              >
                Wstecz
              </button>
            ) : null}
            <button type="submit" className={buttons.primary}>
              {isLast ? "Wyślij wniosek" : "Dalej"}
              <ArrowRight
                aria-hidden="true"
                size={20}
                strokeWidth={2}
                strokeLinecap="square"
                strokeLinejoin="miter"
              />
            </button>
          </div>
        </form>

        <p className={styles.abort}>
          <button
            type="button"
            className={buttons.link}
            onClick={() => dispatch({ type: "reset", notice: ABORT_NOTICE })}
          >
            Przerwij wypełnianie
          </button>
        </p>
      </div>
    </RendererContext.Provider>
  );
}

const SUBMIT_NOTICE = "To jest podgląd formularza. Wniosek nie został nigdzie wysłany.";
const ABORT_NOTICE = "Przerwano wypełnianie. Wprowadzone dane zostały usunięte.";
