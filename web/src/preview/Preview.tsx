import { type DragEvent, useState } from "react";
import { AppHeader } from "../brand/AppHeader";
import { ConfigError, parseConfig } from "../form/parse";
import type { FormConfig } from "../form/types";
import buttons from "../renderer/buttons.module.css";
import { FormRenderer } from "../renderer/FormRenderer";
import styles from "./Preview.module.css";

/** Copies of the two reference configurations from Docs/, served from public/examples. */
export const EXAMPLES = [
  { label: "Przykład 1", file: "przyklad-1.json" },
  { label: "Przykład 5", file: "przyklad-5.json" },
];

const MAX_BYTES = 5 * 1024 * 1024;

interface Loaded {
  config: FormConfig;
  /** Bumped on every load so the renderer starts with fresh state. */
  version: number;
}

function describeError(error: unknown): string {
  if (error instanceof ConfigError) return error.message;
  return "Nie udało się wczytać pliku.";
}

/** /podglad: load any configuration JSON and fill it in as an e-form. */
export function Preview() {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const show = (text: string) => {
    try {
      const config = parseConfig(text);
      setLoaded((prev) => ({ config, version: (prev?.version ?? 0) + 1 }));
      setError(null);
    } catch (e) {
      setError(describeError(e));
    }
  };

  const loadFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_BYTES) {
      setError("Plik jest większy niż 5 MB. To nie wygląda na konfigurację formularza.");
      return;
    }
    show(await file.text());
  };

  const loadExample = async (file: string) => {
    try {
      const response = await fetch(`/examples/${file}`);
      if (!response.ok) throw new Error(String(response.status));
      show(await response.text());
    } catch {
      setError("Nie udało się wczytać przykładu.");
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    void loadFile(e.dataTransfer.files[0]);
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: page-wide drop target; the file input is the keyboard path.
    <div
      className={styles.preview}
      data-dragging={dragging}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={onDrop}
    >
      <AppHeader>
        <div className={styles.loaders}>
          <input
            id="config-file"
            type="file"
            accept=".json,application/json"
            className="visually-hidden"
            onChange={(e) => {
              void loadFile(e.target.files?.[0]);
              e.target.value = "";
            }}
          />
          <label htmlFor="config-file" className={`${buttons.secondary} ${styles.fileButton}`}>
            Wczytaj plik JSON
          </label>
          {EXAMPLES.map((example) => (
            <button
              key={example.file}
              type="button"
              className={buttons.secondary}
              onClick={() => void loadExample(example.file)}
            >
              {example.label}
            </button>
          ))}
        </div>
      </AppHeader>

      <main className={styles.main}>
        {error ? (
          <div className={styles.error} role="alert">
            <strong>Nie można wyświetlić formularza.</strong> {error}
          </div>
        ) : null}

        {loaded ? (
          <FormRenderer key={loaded.version} config={loaded.config} />
        ) : (
          <div className={styles.empty}>
            <h1>Podgląd e-formularza</h1>
            <p>
              Wczytaj plik JSON z konfiguracją formularza albo przeciągnij go w dowolne miejsce
              strony. Możesz też otworzyć jeden z przykładów referencyjnych.
            </p>
            <p className={styles.note}>
              Plik zostaje w przeglądarce. Podgląd niczego nie wysyła, a dane z rejestrów i
              słowników są przykładowe.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
