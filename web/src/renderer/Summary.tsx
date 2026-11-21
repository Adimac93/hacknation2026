import { displayValue, fieldInstances, labelOf, PRESENTATIONAL_TYPES } from "../form/model";
import type { FormConfig } from "../form/types";
import buttons from "./buttons.module.css";
import { useLevel, useRenderer } from "./context";
import styles from "./FormRenderer.module.css";

interface Props {
  config: FormConfig;
  /** Tab indexes of the pages to summarise, in flow order. */
  tabs: number[];
  repeats: Record<string, number[]>;
  onEdit: (tabIndex: number) => void;
}

/** Answers from every visible field, page by page, for the FINISH page. */
export function Summary({ config, tabs, repeats, onEdit }: Props) {
  const api = useRenderer();
  const level = useLevel(2);
  return (
    <div className={styles.summary}>
      {tabs.map((t) => {
        const tab = config.tabs[t];
        const rows = fieldInstances(config, t, repeats).filter(
          (inst) =>
            !PRESENTATIONAL_TYPES.has(inst.field.type) &&
            !api.isHidden(inst.sectionKey, inst.sectionKey) &&
            !api.isHidden(inst.key, inst.template),
        );
        return (
          <section key={t} className={styles.summaryCard} aria-labelledby={`summary-${t}`}>
            <div className={styles.summaryHeader}>
              <h2 id={`summary-${t}`} {...level}>
                {tab?.title}
              </h2>
              <button
                type="button"
                className={`${buttons.link} ${buttons.small}`}
                onClick={() => onEdit(t)}
              >
                Zmień<span className="visually-hidden">: {tab?.title}</span>
              </button>
            </div>
            <dl>
              {rows.map((inst) => {
                const value = displayValue(inst.field, api.answerOf(inst.field, inst.key));
                return (
                  <div key={inst.key} className={styles.summaryRow}>
                    <dt>{labelOf(inst.field) || "Oświadczenia"}</dt>
                    <dd>{value || <span className={styles.empty}>Nie podano</span>}</dd>
                  </div>
                );
              })}
            </dl>
          </section>
        );
      })}
    </div>
  );
}
