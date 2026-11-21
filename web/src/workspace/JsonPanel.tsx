import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import buttons from "../renderer/buttons.module.css";
import styles from "./JsonPanel.module.css";
import { JsonTree } from "./JsonTree";

const ICON = {
  size: 20,
  strokeWidth: 2,
  strokeLinecap: "square",
  strokeLinejoin: "miter",
} as const;

/** Read-only JSON view with copy and download; confirmation goes to an aria-live region. */
export function JsonPanel({ form, fileName }: { form: unknown; fileName: string }) {
  const text = useMemo(() => JSON.stringify(form, null, 2), [form]);
  const [message, setMessage] = useState("");
  const [mode, setMode] = useState<"tree" | "text">("tree");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setMessage("Skopiowano JSON do schowka.");
    } catch {
      setMessage("Nie udało się skopiować. Zaznacz tekst i skopiuj go ręcznie.");
    }
  };

  const download = () => {
    const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${fileName.replace(/\.[^.]+$/, "") || "formularz"}.json`;
    a.click();
    URL.revokeObjectURL(url);
    setMessage("Pobrano plik JSON.");
  };

  return (
    <section aria-labelledby="json-title" className={styles.panel}>
      <div className={styles.header}>
        <h2 id="json-title">JSON formularza</h2>
        <div className={styles.actions}>
          <button type="button" className={buttons.secondary} onClick={() => void copy()}>
            Kopiuj
          </button>
          <button type="button" className={buttons.primary} onClick={download}>
            Pobierz JSON
            <Download aria-hidden="true" {...ICON} />
          </button>
        </div>
      </div>
      <p className="visually-hidden" aria-live="polite">
        {message}
      </p>
      {message ? <p className={styles.message}>{message}</p> : null}
      <fieldset className={styles.switch}>
        <legend className="visually-hidden">Widok JSON</legend>
        {(["tree", "text"] as const).map((m) => (
          <button
            key={m}
            type="button"
            className={styles.switchButton}
            aria-pressed={mode === m}
            onClick={() => setMode(m)}
          >
            {m === "tree" ? "Drzewo" : "Tekst"}
          </button>
        ))}
      </fieldset>
      {mode === "tree" ? (
        <JsonTree key={text} value={form} />
      ) : (
        // biome-ignore lint/a11y/noNoninteractiveTabindex: scrollable region must be keyboard reachable.
        <section className={styles.code} tabIndex={0} aria-label="Treść pliku JSON">
          <pre>{text}</pre>
        </section>
      )}
    </section>
  );
}
