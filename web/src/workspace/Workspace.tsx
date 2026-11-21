import { useEffect, useRef, useState } from "react";
import { AppHeader } from "../brand/AppHeader";
import { ConfigError, normalizeConfig } from "../form/parse";
import type { FormConfig } from "../form/types";
import { CompareView } from "./CompareView";
import { JsonPanel } from "./JsonPanel";
import { Queue } from "./Queue";
import { ReportPanel } from "./ReportPanel";
import { Upload } from "./Upload";
import { useAnalysisQueue } from "./useAnalysisQueue";
import styles from "./Workspace.module.css";

type View = "compare" | "json" | "report";

const VIEWS: { id: View; label: string }[] = [
  { id: "compare", label: "Dokument i formularz" },
  { id: "json", label: "JSON" },
  { id: "report", label: "Raport" },
];

/** Clerk workstation: upload, queue, and three result views for the selected file. */
export function Workspace() {
  const [view, setView] = useState<View>("compare");
  const [token, setToken] = useState("");
  const [tokenOpen, setTokenOpen] = useState(false);
  const queue = useAnalysisQueue({ token, onAuthRequired: () => setTokenOpen(true) });
  const { jobs, rejected, selected } = queue;

  // A new file adds a queue row below the fold; bring it into view so progress is visible.
  const queued = jobs.length;
  const shown = useRef(0);
  useEffect(() => {
    if (queued > shown.current)
      document.getElementById("queue-title")?.scrollIntoView({ block: "start" });
    shown.current = queued;
  }, [queued]);

  const job = jobs.find((j) => j.id === selected);
  const result = queue.resultOf(selected);
  let config: FormConfig | null = null;
  let configError = "";
  if (result) {
    try {
      config = normalizeConfig(result.form);
    } catch (e) {
      configError = e instanceof ConfigError ? e.message : "Wynik nie jest poprawną konfiguracją.";
    }
  }

  return (
    <>
      <AppHeader>
        <a href="/podglad">Podgląd pliku JSON</a>
      </AppHeader>
      <main className={styles.main}>
        <h1>Cyfryzacja formularzy</h1>
        <p className={styles.lead}>
          Wgraj blankiet, a Biurokratka zaproponuje formularz elektroniczny. Sprawdź wynik obok
          dokumentu, zanim pobierzesz JSON.
        </p>

        <div className={styles.intake}>
          <Upload onFiles={queue.addFiles} onDemo={() => void queue.addDemo()} busy={false} />
          <details
            className={styles.token}
            open={tokenOpen}
            onToggle={(e) => setTokenOpen(e.currentTarget.open)}
          >
            <summary>Uwierzytelnianie (opcjonalne)</summary>
            <label htmlFor="jwt">Token JWT</label>
            <input
              id="jwt"
              type="password"
              autoComplete="off"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <p>Wpisz token tylko wtedy, gdy usługa wymaga logowania. Nie jest zapamiętywany.</p>
          </details>
        </div>

        {rejected.length > 0 ? (
          <div className={styles.alert} role="alert">
            <h2>Nie dodano {rejected.length} plików</h2>
            <ul>
              {rejected.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {jobs.length > 0 ? (
          <Queue
            jobs={jobs}
            selected={selected}
            onSelect={queue.select}
            onRemove={queue.remove}
            onRetry={queue.retry}
            onClearFinished={queue.clearFinished}
            onRemoveAll={queue.removeAll}
          />
        ) : null}

        {result && job ? (
          <section aria-labelledby="result-title" className={styles.result}>
            <h2 id="result-title">Wynik: {job.name}</h2>
            {result.demo ? (
              <p className={styles.demo}>
                To dane przykładowe zbudowane z referencyjnego JSON-a, bez udziału usługi.
              </p>
            ) : null}
            <div role="tablist" aria-label="Widok wyniku" className={styles.tabs}>
              {VIEWS.map((v) => (
                <button
                  key={v.id}
                  type="button"
                  role="tab"
                  id={`tab-${v.id}`}
                  aria-selected={view === v.id}
                  aria-controls={`panel-${v.id}`}
                  tabIndex={view === v.id ? 0 : -1}
                  onClick={() => setView(v.id)}
                  onKeyDown={(e) => {
                    const i = VIEWS.findIndex((x) => x.id === view);
                    const step = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
                    if (!step) return;
                    const next = VIEWS[(i + step + VIEWS.length) % VIEWS.length];
                    if (!next) return;
                    setView(next.id);
                    document.getElementById(`tab-${next.id}`)?.focus();
                  }}
                >
                  {v.label}
                </button>
              ))}
            </div>
            <div role="tabpanel" id={`panel-${view}`} aria-labelledby={`tab-${view}`}>
              {view === "compare" ? (
                config ? (
                  <CompareView key={selected} report={result.report} config={config} />
                ) : (
                  <p role="alert">{configError}</p>
                )
              ) : null}
              {view === "json" ? <JsonPanel form={result.form} fileName={job.name} /> : null}
              {view === "report" ? <ReportPanel report={result.report} /> : null}
            </div>
          </section>
        ) : null}
      </main>
    </>
  );
}
