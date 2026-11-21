import { useEffect, useState } from "react";
import { formatSize } from "../api/validate";
import buttons from "../renderer/buttons.module.css";
import styles from "./Queue.module.css";

export type JobStatus = "waiting" | "running" | "done" | "error";

export interface Job {
  id: number;
  name: string;
  size: number;
  status: JobStatus;
  error?: string;
}

const LABEL: Record<JobStatus, string> = {
  waiting: "Czeka",
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

interface Props {
  jobs: Job[];
  selected: number | null;
  onSelect: (id: number) => void;
  onRemove: (id: number) => void;
}

/** Queue of uploaded files (batch mode); the status is text, not only colour. */
export function Queue({ jobs, selected, onSelect, onRemove }: Props) {
  const done = jobs.filter((j) => j.status === "done" || j.status === "error").length;
  const running = jobs.find((j) => j.status === "running");
  const elapsed = useElapsed(Boolean(running));
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
          Analizuję plik {done + 1} z {jobs.length}: {running.name}. Trwa to {elapsed} s. Duże pliki
          i skany mogą potrzebować nawet kilku minut, nie zamykaj tej strony.
        </p>
      ) : null}
      <p className="visually-hidden" aria-live="polite">
        {running
          ? `Analizuję plik ${done + 1} z ${jobs.length}`
          : `Zakończono ${done} z ${jobs.length}`}
      </p>
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
                {job.error ? <p className={styles.error}>{job.error}</p> : null}
              </td>
              <td>
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
