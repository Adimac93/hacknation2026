import type { Report } from "../api/types";
import styles from "./ReportPanel.module.css";

const STAGES: Record<string, string> = {
  ingest: "Odczyt pliku",
  heuristics: "Reguły",
  llm: "Model",
  compile: "Kompilacja",
  lint: "Kontrola",
};

/** Lint results, dictionary proposals, mode and stage timings. */
export function ReportPanel({ report }: { report: Report }) {
  const errors = report.lint.filter((l) => l.severity === "error").length;
  const warnings = report.lint.length - errors;
  const total = Object.values(report.timings_ms).reduce((a, b) => a + b, 0);

  return (
    <section aria-labelledby="report-title" className={styles.panel}>
      <h2 id="report-title">Raport</h2>

      <p className={styles.summary}>
        Tryb: <strong>{report.mode === "llm" ? "model językowy" : "reguły"}</strong>
        {report.model ? (
          <>
            {" "}
            (<span className="mono">{report.model}</span>)
          </>
        ) : null}
        . Rozpoznano <strong>{report.fields.length}</strong> pól.
        {report.lint.length === 0
          ? " Kontrola nie zgłosiła uwag."
          : ` Kontrola: ${errors} błędów, ${warnings} ostrzeżeń.`}
      </p>

      <h3>Kontrola zgodności</h3>
      {report.lint.length === 0 ? (
        <p>Brak uwag.</p>
      ) : (
        <table>
          <caption className="visually-hidden">
            Wyniki kontroli zgodności z regułami technicznymi
          </caption>
          <thead>
            <tr>
              <th scope="col">Kod</th>
              <th scope="col">Poziom</th>
              <th scope="col">Opis</th>
              <th scope="col">Miejsce</th>
            </tr>
          </thead>
          <tbody>
            {report.lint.map((item) => (
              <tr key={`${item.code}-${item.path}`}>
                <td className="mono">{item.code}</td>
                <td>
                  <span className={styles.tag} data-severity={item.severity}>
                    {item.severity === "error" ? "Błąd" : "Ostrzeżenie"}
                  </span>
                  {item.fixed ? (
                    <span className={styles.fixed}> naprawiono automatycznie</span>
                  ) : null}
                </td>
                <td>{item.message}</td>
                <td className="mono">{item.path}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h3>Proponowane słowniki</h3>
      {report.dictionary_proposals.length === 0 ? (
        <p>Brak propozycji.</p>
      ) : (
        <ul className={styles.list}>
          {report.dictionary_proposals.map((d) => (
            <li key={d.name}>
              <strong>{d.name}</strong>: {d.items.join(", ")}
              {d.fields.length > 0 ? (
                <>
                  {" "}
                  (pola: <span className="mono">{d.fields.join(", ")}</span>)
                </>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      <h3>Czas przetwarzania</h3>
      <table>
        <caption className="visually-hidden">Czas poszczególnych etapów w milisekundach</caption>
        <thead>
          <tr>
            <th scope="col">Etap</th>
            <th scope="col" className={styles.num}>
              ms
            </th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(report.timings_ms).map(([stage, ms]) => (
            <tr key={stage}>
              <th scope="row">{STAGES[stage] ?? stage}</th>
              <td className={`mono ${styles.num}`}>{ms}</td>
            </tr>
          ))}
          <tr>
            <th scope="row">Razem</th>
            <td className={`mono ${styles.num}`}>{total}</td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}
