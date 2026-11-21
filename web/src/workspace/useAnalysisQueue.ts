import { useEffect, useRef, useState } from "react";
import { ApiError, analyzeFile } from "../api/client";
import { demoResult } from "../api/demo";
import { retryDelay } from "../api/retry";
import type { AnalysisResult } from "../api/types";
import { validateUpload } from "../api/validate";
import type { Job } from "./Queue";

let nextId = 1;

interface Options {
  token: string;
  /** Called when the API answers 401, so the UI can reveal the token field. */
  onAuthRequired?: () => void;
}

/** Batch queue state: files are analysed one by one, results and Files live in refs. */
export function useAnalysisQueue({ token, onAuthRequired }: Options) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const results = useRef(new Map<number, AnalysisResult>());
  // A File is kept only while its job can still run or be retried (waiting, error), then dropped.
  const files = useRef(new Map<number, File>());
  const running = useRef(false);
  const attempts = useRef(new Map<number, number>());
  const authCallback = useRef(onAuthRequired);
  authCallback.current = onAuthRequired;

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
    patch(job.id, { status: "running", error: undefined, canRetry: false });
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
          if (e instanceof ApiError && e.status === 401) authCallback.current?.();
          patch(job.id, {
            status: "error",
            error: e instanceof Error ? e.message : "Błąd analizy. Spróbuj ponownie.",
            canRetry: true,
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

  /** Drops the given jobs; when the selection goes with them, the next done job is selected. */
  const drop = (ids: Set<number>) => {
    for (const id of ids) {
      results.current.delete(id);
      files.current.delete(id);
      attempts.current.delete(id);
    }
    const rest = jobs.filter((j) => !ids.has(j.id));
    setJobs(rest);
    setSelected((cur) => {
      if (cur === null || !ids.has(cur)) return cur;
      const at = jobs.findIndex((j) => j.id === cur);
      const done = rest.filter((j) => j.status === "done");
      const next = done.find((j) => jobs.findIndex((x) => x.id === j.id) > at) ?? done.at(-1);
      return next?.id ?? null;
    });
  };

  const retry = (id: number) => {
    if (!files.current.has(id)) return;
    attempts.current.delete(id);
    patch(id, { status: "waiting", error: undefined, canRetry: false });
  };

  return {
    jobs,
    rejected,
    selected,
    select: setSelected,
    resultOf: (id: number | null) => (id === null ? undefined : results.current.get(id)),
    addFiles,
    addDemo,
    retry,
    remove: (id: number) => drop(new Set([id])),
    clearFinished: () =>
      drop(
        new Set(jobs.filter((j) => j.status === "done" || j.status === "error").map((j) => j.id)),
      ),
    removeAll: () => drop(new Set(jobs.map((j) => j.id))),
  };
}
