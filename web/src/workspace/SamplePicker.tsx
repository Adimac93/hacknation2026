import { useState } from "react";
import buttons from "../renderer/buttons.module.css";
import styles from "./SamplePicker.module.css";

interface SampleFile {
  format: string;
  path: string;
  name: string;
  bytes: number;
}

interface SampleForm {
  form: string;
  title: string;
  reference: boolean;
  files: SampleFile[];
}

interface Props {
  onFiles: (files: File[]) => void;
}

/** Loads one sample file served next to the app and hands it over like an uploaded file. */
export async function fetchSample(file: SampleFile): Promise<File> {
  const response = await fetch(`/${file.path}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const blob = await response.blob();
  return new File([blob], file.name, { type: blob.type });
}

/** The organiser's sample blanks (Docs/, built by devtools/build_samples.py), every format. */
export function SamplePicker({ onFiles }: Props) {
  const [forms, setForms] = useState<SampleForm[]>([]);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [state, setState] = useState<"idle" | "loading" | "ready" | "failed">("idle");

  // Loaded only when the list is opened, so the workstation fetches nothing it does not need.
  const load = () => {
    if (state !== "idle") return;
    setState("loading");
    fetch("/samples/index.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: { forms?: SampleForm[] }) => {
        setForms(data.forms ?? []);
        setState("ready");
      })
      .catch(() => setState("failed"));
  };

  const pick = async (file: SampleFile) => {
    setLoading(file.path);
    setError(null);
    try {
      onFiles([await fetchSample(file)]);
    } catch {
      setError(`Nie udało się pobrać pliku ${file.name}.`);
    } finally {
      setLoading(null);
    }
  };

  const pickAll = async (form: SampleForm) => {
    setLoading(form.form);
    setError(null);
    try {
      onFiles(await Promise.all(form.files.map(fetchSample)));
    } catch {
      setError(`Nie udało się pobrać plików formularza ${form.form}.`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <details
      className={styles.picker}
      onToggle={(e) => {
        if ((e.currentTarget as HTMLDetailsElement).open) load();
      }}
    >
      <summary>Przykładowe blankiety z materiałów COI</summary>
      {state === "loading" ? <p className={styles.hint}>Wczytuję listę…</p> : null}
      {state === "failed" ? (
        <p className={styles.error}>Lista przykładów jest niedostępna.</p>
      ) : null}
      <p className={styles.hint}>
        Wybierz format, a plik trafi do kolejki tak jak wgrany z dysku. „Wszystkie formaty” wysyła
        cały formularz jako wsad.
      </p>
      <ul className={styles.list}>
        {forms.map((form) => (
          <li key={form.form} className={styles.form}>
            <p className={styles.title}>
              <span className="mono">{form.form}.</span> {form.title}
              {form.reference ? <span className={styles.tag}>referencja</span> : null}
            </p>
            <div className={styles.formats}>
              {form.files.map((file) => (
                <button
                  key={file.path}
                  type="button"
                  className={`${buttons.secondary} ${buttons.small}`}
                  disabled={loading !== null}
                  aria-busy={loading === file.path}
                  aria-label={`${file.format}: ${file.name}`}
                  onClick={() => void pick(file)}
                >
                  {file.format}
                </button>
              ))}
              <button
                type="button"
                className={`${buttons.secondary} ${buttons.small}`}
                disabled={loading !== null}
                aria-busy={loading === form.form}
                onClick={() => void pickAll(form)}
              >
                Wszystkie formaty
              </button>
            </div>
          </li>
        ))}
      </ul>
      <p className={styles.error} role="status" aria-live="polite">
        {error ?? ""}
      </p>
    </details>
  );
}
