import { useEffect, useState } from "react";
import { formatSize } from "../api/validate";
import buttons from "../renderer/buttons.module.css";
import styles from "./Queue.module.css";

export type JobStatus = "waiting" | "limited" | "running" | "done" | "error";

export interface Job {
  id: number;
  name: string;
  size: number;
  status: JobStatus;
  error?: string;
  /** The File is still held, so "Spróbuj ponownie" works. */
  canRetry?: boolean;
  /** Epoch ms when a rate-limited job is retried (status "limited"). */
  retryAt?: number;
}

const LABEL: Record<JobStatus, string> = {
  waiting: "Czeka",
  limited: "Czeka na limit",
  running: "Analiza",
  done: "Gotowe",
  error: "Błąd",
};

/** Seconds since `active` became true; resets when it turns false. */
function useElapsed(active: boolean): number {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (!active) return;
    setSeconds(0);
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [active]);
  return seconds;
}

/** Whole seconds left until `at`, ticking every second. */
function useCountdown(at: number | undefined): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (at === undefined) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [at]);
  return at === undefined ? 0 : Math.max(0, Math.ceil((at - now) / 1000));
}

interface Props {
  jobs: Job[];
  selected: number | null;
  onSelect: (id: number) => void;
  onRemove: (id: number) => void;
  onRetry: (id: number) => void;
  onClearFinished: () => void;
  onRemoveAll: () => void;
}

/** Queue of uploaded files (batch mode); the status is text, not only colour. */
export function Queue({
  jobs,
  selected,
  onSelect,
  onRemove,
  onRetry,
  onClearFinished,
  onRemoveAll,
}: Props) {
  const done = jobs.filter((j) => j.status === "done" || j.status === "error").length;
  const count = (s: JobStatus) => jobs.filter((j) => j.status === s).length;
  const ready = count("done");
  const failed = count("error");
  const pending = jobs.length - ready - failed;
  const running = jobs.find((j) => j.status === "running");
  const elapsed = useElapsed(Boolean(running));
  const limited = jobs.find((j) => j.status === "limited");
  const left = useCountdown(limited?.retryAt);
  return (
    <section aria-labelledby="queue-title" className={styles.queue}>
      <h2 id="queue-title">Kolejka plików</h2>
      <div
        className={styles.track}
        role="progressbar"
        aria-label="Postęp analizy"
        aria-valuemin={0}
        aria-valuemax={jobs.length}
        aria-valuenow={done}
        aria-valuetext={
          running
            ? `Plik ${done + 1} z ${jobs.length}: analiza`
            : `Zakończono ${done} z ${jobs.length}`
        }
      >
        <div className={styles.bar} style={{ width: `${(done / jobs.length) * 100}%` }} />
        {running ? <div className={styles.working} /> : null}
      </div>
      {running ? (
        <p className={styles.status}>
          Analizuję plik {done + 1} z {jobs.length}: {running.name}. Trwa to {elapsed} s. Zdjęcia,
          skany i analiza z udziałem modelu zwykle zajmują 15-60 sekund, większe pliki nawet kilka
          minut. Nie zamykaj tej strony.
        </p>
      ) : null}
      {limited ? (
        <p className={styles.status}>
          Czeka na limit, ponowienie za {left} s: {limited.name}. Usługa przyjmuje do 10 plików na
          minutę, ponowię automatycznie.
        </p>
      ) : null}
      <p className="visually-hidden" aria-live="polite">
        {limited
          ? `${limited.name}: czeka na limit zapytań, ponowienie za około ${Math.ceil(left / 10) * 10} s`
          : running
            ? `Analizuję plik ${done + 1} z ${jobs.length}`
            : `Zakończono ${done} z ${jobs.length}`}
      </p>
      <p className={styles.summary}>
        Gotowe: {ready}, błędy: {failed}, w kolejce: {pending}
      </p>
      <div className={styles.bulk}>
        <button
          type="button"
          className={buttons.secondary}
          onClick={onClearFinished}
          disabled={ready + failed === 0}
        >
          Wyczyść zakończone
        </button>
        <button
          type="button"
          className={buttons.secondary}
          onClick={onRemoveAll}
          disabled={Boolean(running)}
        >
          Usuń wszystkie
        </button>
      </div>
      <table>
        <caption className="visually-hidden">Pliki w kolejce i ich stan</caption>
        <thead>
          <tr>
            <th scope="col">Plik</th>
            <th scope="col">Rozmiar</th>
            <th scope="col">Stan</th>
            <th scope="col">
              <span className="visually-hidden">Akcje</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {jobs.map((job) => (
            <tr key={job.id} aria-current={job.id === selected ? "true" : undefined}>
              <th scope="row" className={styles.name}>
                {job.status === "done" ? (
                  <button type="button" className={buttons.link} onClick={() => onSelect(job.id)}>
                    {job.name}
                  </button>
                ) : (
                  job.name
                )}
              </th>
              <td className="mono">{formatSize(job.size)}</td>
              <td>
                <span className={styles.tag} data-status={job.status}>
                  {LABEL[job.status]}
                </span>
                {job.status === "running" ? <span className="mono"> {elapsed} s</span> : null}
                {job.status === "limited" ? <span className="mono"> za {left} s</span> : null}
                {job.error ? (
                  <p className={styles.error} role="alert">
                    {job.error}
                  </p>
                ) : null}
              </td>
              <td>
                {job.status === "error" && job.canRetry ? (
                  <button
                    type="button"
                    className={`${buttons.link} ${buttons.small}`}
                    onClick={() => onRetry(job.id)}
                  >
                    Spróbuj ponownie<span className="visually-hidden">: {job.name}</span>
                  </button>
                ) : null}{" "}
                <button
                  type="button"
                  className={`${buttons.link} ${buttons.small}`}
                  onClick={() => onRemove(job.id)}
                  disabled={job.status === "running"}
                >
                  Usuń<span className="visually-hidden"> {job.name} z kolejki</span>
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
