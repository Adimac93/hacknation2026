import { useEffect, useRef, useState } from "react";
import { ApiError, analyzeFile } from "../api/client";
import { demoResult } from "../api/demo";
import { retryDelay } from "../api/retry";
import type { AnalysisResult } from "../api/types";
import { validateUpload } from "../api/validate";
import { AppHeader } from "../brand/AppHeader";
import { ConfigError, normalizeConfig } from "../form/parse";
import type { FormConfig } from "../form/types";
import { CompareView } from "./CompareView";
import { JsonPanel } from "./JsonPanel";
import { type Job, Queue } from "./Queue";
import { ReportPanel } from "./ReportPanel";
import { Upload } from "./Upload";
import styles from "./Workspace.module.css";

type View = "compare" | "json" | "report";

const VIEWS: { id: View; label: string }[] = [
  { id: "compare", label: "Dokument i formularz" },
  { id: "json", label: "JSON" },
  { id: "report", label: "Raport" },
];

let nextId = 1;

/** Clerk workstation: upload, queue, and three result views for the selected file. */
export function Workspace() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [view, setView] = useState<View>("compare");
  const [token, setToken] = useState("");
  const results = useRef(new Map<number, AnalysisResult>());
  const files = useRef(new Map<number, File>());
  const running = useRef(false);
  const attempts = useRef(new Map<number, number>());

  const patch = (id: number, change: Partial<Job>) =>
    setJobs((all) => all.map((j) => (j.id === id ? { ...j, ...change } : j)));

  const addFiles = (picked: File[]) => {
    const problems: string[] = [];
    const accepted: Job[] = [];
    for (const file of picked) {
      const problem = validateUpload(file);
      if (problem) {
        problems.push(`${file.name}: ${problem}`);
        continue;
      }
      const id = nextId++;
      files.current.set(id, file);
      accepted.push({ id, name: file.name, size: file.size, status: "waiting" });
    }
    setRejected(problems);
    if (accepted.length > 0) setJobs((all) => [...all, ...accepted]);
  };

  const addDemo = async () => {
    const id = nextId++;
    setJobs((all) => [
      ...all,
      { id, name: "przyklad-5.json (dane przykładowe)", size: 1, status: "running" },
    ]);
    try {
      results.current.set(id, await demoResult());
      patch(id, { status: "done" });
      setSelected(id);
    } catch {
      patch(id, { status: "error", error: "Nie udało się wczytać danych przykładowych." });
    }
  };

  // Files are sent one by one: the API is synchronous and stateless, batch mode is client-side.
  // biome-ignore lint/correctness/useExhaustiveDependencies: patch only calls a stable setter.
  useEffect(() => {
    if (running.current) return;
    if (jobs.some((j) => j.status === "limited")) return; // wait out the rate limit first
    const job = jobs.find((j) => j.status === "waiting");
    const file = job && files.current.get(job.id);
    if (!job || !file) return;
    running.current = true;
    patch(job.id, { status: "running" });
    analyzeFile(file, token || undefined)
      .then((result) => {
        results.current.set(job.id, result);
        files.current.delete(job.id);
        patch(job.id, { status: "done" });
        setSelected((cur) => cur ?? job.id);
      })
      .catch((e: unknown) => {
        const tries = attempts.current.get(job.id) ?? 0;
        const delay = e instanceof ApiError ? retryDelay(e.status, e.retryAfter, tries) : null;
        if (delay === null) {
          files.current.delete(job.id);
          patch(job.id, {
            status: "error",
            error: e instanceof Error ? e.message : "Błąd analizy.",
          });
          return;
        }
        attempts.current.set(job.id, tries + 1);
        patch(job.id, { status: "limited", retryAt: Date.now() + delay * 1000 });
        setTimeout(() => {
          // A removed job has no file any more; nothing to wake then.
          if (files.current.has(job.id)) patch(job.id, { status: "waiting", retryAt: undefined });
        }, delay * 1000);
      })
      .finally(() => {
        running.current = false;
        setJobs((all) => [...all]); // wake the effect for the next waiting file
      });
  }, [jobs, token]);

  // A new file adds a queue row below the fold; bring it into view so progress is visible.
  const queued = jobs.length;
  // biome-ignore lint/correctness/useExhaustiveDependencies: only react to the count growing.
  useEffect(() => {
    if (queued > 0) document.getElementById("queue-title")?.scrollIntoView({ block: "start" });
  }, [queued]);

  const remove = (id: number) => {
    results.current.delete(id);
    files.current.delete(id);
    attempts.current.delete(id);
    setJobs((all) => all.filter((j) => j.id !== id));
    setSelected((cur) => (cur === id ? null : cur));
  };

  const job = jobs.find((j) => j.id === selected);
  const result = selected === null ? undefined : results.current.get(selected);
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
          <Upload onFiles={addFiles} onDemo={() => void addDemo()} busy={false} />
          <details className={styles.token}>
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
          <Queue jobs={jobs} selected={selected} onSelect={setSelected} onRemove={remove} />
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
