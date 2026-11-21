import { type DragEvent, useId, useState } from "react";
import { FORMAT_LABELS, MAX_UPLOAD_MB } from "../api/validate";
import buttons from "../renderer/buttons.module.css";
import styles from "./Upload.module.css";

interface Props {
  onFiles: (files: File[]) => void;
  onDemo: () => void;
  busy: boolean;
}

/** Drop zone plus a plain "choose files" button; several files form a batch. */
export function Upload({ onFiles, onDemo, busy }: Props) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length > 0) onFiles([...e.dataTransfer.files]);
  };

  return (
    <section
      className={styles.zone}
      data-dragging={dragging}
      aria-labelledby={`${inputId}-title`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <h2 id={`${inputId}-title`}>Wgraj blankiet</h2>
      <p>
        Przeciągnij tutaj plik z blankietem formularza albo wybierz go z dysku. Możesz dodać kilka
        plików naraz.
      </p>
      <dl className={styles.rules}>
        <dt>Formaty</dt>
        <dd>{FORMAT_LABELS}</dd>
        <dt>Limit</dt>
        <dd>{MAX_UPLOAD_MB} MB na plik</dd>
      </dl>
      <input
        id={inputId}
        type="file"
        multiple
        className="visually-hidden"
        accept=".pdf,.doc,.docx,.ods,.xlsx,.jpg,.jpeg,.png"
        onChange={(e) => {
          if (e.target.files) onFiles([...e.target.files]);
          e.target.value = "";
        }}
      />
      <div className={styles.buttons}>
        <label
          htmlFor={inputId}
          className={`${buttons.primary} ${styles.pick}`}
          aria-disabled={busy}
        >
          Wybierz pliki
        </label>
        <button type="button" className={buttons.secondary} onClick={onDemo}>
          Wczytaj dane przykładowe
        </button>
      </div>
      <p className={styles.privacy}>Plik nie jest zapisywany na serwerze.</p>
    </section>
  );
}
