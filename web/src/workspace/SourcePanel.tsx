import type { Report } from "../api/types";
import { fieldsForLine, pickForLine } from "./origin";
import styles from "./SourcePanel.module.css";

interface Props {
  report: Report;
  /** techName of the selected field, shared with the review list and the form. */
  active: string | null;
  onSelect: (techName: string | null) => void;
}

/** Document text with the lines a selected field came from highlighted; lines are clickable. */
export function SourcePanel({ report, active, onSelect }: Props) {
  const origin = report.fields.find((f) => f.techName === active);
  const lit = new Set(origin?.src);

  return (
    <section aria-labelledby="source-title" className={styles.panel}>
      <h2 id="source-title">Tekst dokumentu</h2>
      {report.document.pages.length === 0 ? (
        <p>Usługa nie zwróciła tekstu dokumentu, więc nie ma czego podświetlać.</p>
      ) : null}
      <div className={styles.picker}>
        <label htmlFor="origin-field">Pokaż źródło pola</label>
        <select
          id="origin-field"
          value={active ?? ""}
          onChange={(e) => onSelect(e.target.value || null)}
        >
          <option value="">Nie wybrano</option>
          {report.fields.map((f) => (
            <option key={f.techName} value={f.techName}>
              {f.techName}
            </option>
          ))}
        </select>
      </div>
      {origin ? (
        <p className={styles.confidence} aria-live="polite">
          Pewność rozpoznania: <span className="mono">{Math.round(origin.confidence * 100)}%</span>
          {origin.confidence < 0.7 ? " (sprawdź to pole przed eksportem)" : ""}
        </p>
      ) : null}
      <p className={styles.hint}>Kliknij wiersz, aby zobaczyć pole utworzone z tego tekstu.</p>
      {report.document.pages.map((page) => (
        <div key={page.number} className={styles.page}>
          <h3 className="kicker">Strona {page.number}</h3>
          <ol className={styles.lines}>
            {page.lines.map((line) => {
              const isLit = lit.has(line.id);
              const linked = fieldsForLine(report.fields, line.id);
              const inner = (
                <>
                  <span className={`mono ${styles.id}`}>{line.id}</span>
                  <span>{line.text}</span>
                  {isLit ? <span className="visually-hidden"> (źródło pola)</span> : null}
                </>
              );
              return (
                <li key={line.id} data-kind={line.kind} data-lit={isLit}>
                  {linked.length > 0 ? (
                    <button
                      type="button"
                      className={styles.line}
                      aria-pressed={isLit}
                      title={`Pola: ${linked.map((f) => f.techName).join(", ")}`}
                      onClick={() => onSelect(pickForLine(report.fields, line.id, active))}
                    >
                      {inner}
                    </button>
                  ) : (
                    <div className={styles.line}>{inner}</div>
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </section>
  );
}
