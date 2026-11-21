import { type DragEvent, useState } from "react";
import type { FileEntry } from "../../form/types";
import buttons from "../buttons.module.css";
import styles from "./Field.module.css";
import { FieldFrame } from "./frame";
import type { FieldProps } from "./types";

// Limits shown in the COI visualisation. The preview never uploads anything: it keeps
// only names and sizes in memory.
export const FILE_RULES = {
  accept: [".jpg", ".pdf", ".png", ".jpeg", ".doc", ".odt", ".docx", ".ods"],
  maxBytes: 10 * 1024 * 1024,
  maxFiles: 1,
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} kB`;
  return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
}

export function FileUploader(props: FieldProps) {
  const { id, value, onChange, readOnly, error } = props;
  const files = value as FileEntry[];
  const [problem, setProblem] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const add = (picked: File[]) => {
    const accepted: FileEntry[] = [];
    const problems: string[] = [];
    for (const file of picked) {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!FILE_RULES.accept.includes(ext)) problems.push(`${file.name}: niedozwolony format.`);
      else if (file.size > FILE_RULES.maxBytes)
        problems.push(`${file.name}: plik jest większy niż 10 MB.`);
      else accepted.push({ name: file.name, size: file.size });
    }
    const next = [...files, ...accepted];
    if (next.length > FILE_RULES.maxFiles) {
      problems.push(`Możesz dodać najwyżej ${FILE_RULES.maxFiles} plik.`);
    }
    setProblem(problems.length > 0 ? problems.join(" ") : null);
    if (accepted.length > 0) onChange(next.slice(-FILE_RULES.maxFiles));
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (!readOnly) add(Array.from(e.dataTransfer.files));
  };

  return (
    <FieldFrame {...props}>
      {(describedBy) => (
        <>
          {/* biome-ignore lint/a11y/noStaticElementInteractions: drop target; the file input stays the keyboard path. */}
          <div
            className={styles.dropzone}
            data-dragging={dragging}
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
          >
            <input
              id={id}
              type="file"
              className="visually-hidden"
              accept={FILE_RULES.accept.join(",")}
              multiple={FILE_RULES.maxFiles > 1}
              disabled={readOnly}
              onChange={(e) => {
                add(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
              aria-describedby={[describedBy, `${id}-rules`].filter(Boolean).join(" ")}
              aria-invalid={error ? true : undefined}
            />
            <label htmlFor={id} className={`${buttons.secondary} ${styles.pick}`}>
              Dodaj lub przeciągnij plik
            </label>
            <dl id={`${id}-rules`} className={styles.rules}>
              <dt>Dopuszczalny format pliku:</dt>
              <dd>{FILE_RULES.accept.join(", ")}</dd>
              <dt>Maksymalny rozmiar pliku:</dt>
              <dd>10 MB</dd>
              <dt>Maksymalna liczba plików:</dt>
              <dd>{FILE_RULES.maxFiles}</dd>
            </dl>
          </div>
          {problem ? (
            <p className={styles.error} role="alert">
              {problem}
            </p>
          ) : null}
          {files.length > 0 ? (
            <ul className={styles.files} aria-label="Dodane pliki">
              {files.map((file, i) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: picked files have no id; names may repeat.
                <li key={`${file.name}-${i}`}>
                  <span>
                    {file.name} ({formatSize(file.size)})
                  </span>
                  <button
                    type="button"
                    className={`${buttons.link} ${buttons.small}`}
                    onClick={() => onChange(files.filter((_, j) => j !== i))}
                    disabled={readOnly}
                  >
                    Usuń<span className="visually-hidden"> plik {file.name}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
    </FieldFrame>
  );
}
