import { useState } from "react";
import type { Report } from "../api/types";
import styles from "./SourcePanel.module.css";

/** Document text with the lines a chosen field came from highlighted. */
export function SourcePanel({ report }: { report: Report }) {
  const [active, setActive] = useState<string | null>(null);
  const origin = report.fields.find((f) => f.techName === active);
  const lit = new Set(origin?.src);

  return (
    <section aria-labelledby="source-title" className={styles.panel}>
      <h2 id="source-title">Tekst dokumentu</h2>
      <div className={styles.picker}>
        <label htmlFor="origin-field">Pokaż źródło pola</label>
        <select
          id="origin-field"
          value={active ?? ""}
          onChange={(e) => setActive(e.target.value || null)}
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
      {report.document.pages.map((page) => (
        <div key={page.number} className={styles.page}>
          <h3 className="kicker">Strona {page.number}</h3>
          <ol className={styles.lines}>
            {page.lines.map((line) => (
              <li key={line.id} data-kind={line.kind} data-lit={lit.has(line.id)}>
                <span className={`mono ${styles.id}`}>{line.id}</span>
                <span>{line.text}</span>
                {lit.has(line.id) ? <span className="visually-hidden"> (źródło pola)</span> : null}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </section>
  );
}
